"""Dry run of the CI `deploy` job's two steps against local stubs (issue #38, part 3).

Extracts the exact `run:` text of "Trigger Render deploy" and "Wait for /health
to report this commit" from .github/workflows/ci.yml, swaps the three GitHub
expressions for placeholders that point at 127.0.0.1, and runs each step with
`bash -e` (the shell GitHub uses) against a tiny HTTP stub. It prints each
case's output and exit code and exits 1 if any case does not behave as the
issue requires.

Never touches Render: the hook and PUBLIC_URL are local placeholders, and the
real RENDER_DEPLOY_HOOK_URL is not read from anywhere.

Usage (needs bash, curl and PyYAML; backend/.venv has PyYAML):

    backend/.venv/Scripts/python.exe ops/dry-run-deploy-hint.py

`jq` is replaced by a shim that implements only `jq -r '.commit // empty'`, so
the run also works on a machine without jq (the GitHub runner has the real one).
The loop is shortened with WAIT_ATTEMPTS=3 WAIT_INTERVAL=1 for this run only.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml

CI = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
SHA = "0123456789abcdef0123456789abcdef01234567"
OTHER_SHA = "fedcba9876543210fedcba9876543210fedcba98"
HOOK_TOKEN = "placeholder-hook-token"  # must never show up in a step's output

JQ_SHIM = '''import json, sys
args = [a for a in sys.argv[1:] if a not in ("-r",)]
assert args[0] == ".commit // empty", args
data = open(args[1], encoding="utf-8").read() if len(args) > 1 else sys.stdin.read()
try:
    value = json.loads(data).get("commit")
except Exception:
    sys.exit(4)
if value:
    print(value)
'''


def free_closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Stub(ThreadingHTTPServer):
    def __init__(self, status: int, commit: str | None):
        self.status, self.commit = status, commit
        super().__init__(("127.0.0.1", 0), self._handler())

    def _handler(self):
        outer = self

        class H(BaseHTTPRequestHandler):
            def _answer(self):
                body = json.dumps({"status": "ok", "commit": outer.commit} if outer.status == 200
                                  else {"detail": f"stub says {outer.status}"}).encode()
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = do_POST = _answer

            def log_message(self, *a):  # keep the output clean
                pass

        return H

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"


def steps() -> dict[str, str]:
    job = yaml.safe_load(CI.read_text(encoding="utf-8"))["jobs"]["deploy"]
    return {s["name"]: s["run"] for s in job["steps"]}


def render(script: str, hook_url: str, public_url: str) -> str:
    out = (script.replace("${{ secrets.RENDER_DEPLOY_HOOK_URL }}", hook_url)
                 .replace("${{ vars.PUBLIC_URL }}", public_url)
                 .replace("${{ github.sha }}", SHA))
    assert "${{" not in out, "an unexpected GitHub expression is left in the step"
    return out


def find_bash() -> str:
    """Git Bash on Windows (a bare `bash` there may be WSL), else the one on PATH."""
    if os.environ.get("BASH"):
        return os.environ["BASH"]
    for candidate in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files (x86)\Git\bin\bash.exe"):
        if os.path.exists(candidate):
            return candidate
    return shutil.which("bash") or "bash"


def run_step(script: str, workdir: Path, env: dict[str, str]) -> tuple[int, str]:
    f = workdir / "step.sh"
    f.write_text(script, encoding="utf-8", newline="\n")
    p = subprocess.run([find_bash(), "-e", str(f)], env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
    return p.returncode, p.stdout


# case id, description, hook ("500"|"404"|"200"|"closed"), health (None | "match" | "other" | "closed" | "503" | "404")
CASES = [
    ("a", "hook answers 500", "500", None),
    ("b", "hook unreachable (closed port)", "closed", None),
    ("c", "hook answers 404", "404", None),
    ("d", "hook 200, /health returns the matching sha", "200", "match"),
    ("e", "hook 200, /health unreachable for the whole budget", "200", "closed"),
    ("f", "hook 200, /health returns a different commit", "200", "other"),
    ("g", "(extra) hook 200, /health answers 503 all the way", "200", "503"),
    ("h", "(extra) hook 200, /health answers 404 all the way", "200", "404"),
]

# Text that must appear in the output, so a case cannot pass for the wrong reason.
MARKER = {"a": "HTTP status 500", "b": "curl exit 7", "c": "HTTP status 404", "d": "matches",
          "e": "Timed out", "f": "Timed out", "g": "Timed out", "h": "Timed out"}

# (hook step must fail, wait step must run, wait must succeed, HINT expected, NOTE expected)
EXPECT = {
    "a": (True, False, None, True, False),
    "b": (True, False, None, True, False),
    "c": (True, False, None, False, False),
    "d": (False, True, True, False, False),
    "e": (False, True, False, True, False),
    "f": (False, True, False, False, True),
    "g": (False, True, False, True, False),
    "h": (False, True, False, False, True),
}


def main() -> int:
    scripts = steps()
    hook_script = scripts["Trigger Render deploy"]
    wait_script = scripts["Wait for /health to report this commit"]
    failures = 0
    # The committed workflow keeps 60 attempts x 10 s; only this run shortens it.
    defaults_ok = "${WAIT_ATTEMPTS:-60}" in wait_script and "${WAIT_INTERVAL:-10}" in wait_script
    print(f"workflow defaults are 60 attempts x 10 s: {'ok' if defaults_ok else 'FAIL'}")
    print()
    failures += not defaults_ok
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "bin").mkdir()
        (work / "bin" / "shim.py").write_text(JQ_SHIM, encoding="utf-8", newline="\n")
        jq = work / "bin" / "jq"
        jq.write_text(f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" "{(work / "bin" / "shim.py").as_posix()}" "$@"\n',
                      encoding="utf-8", newline="\n")
        env = dict(os.environ, WAIT_ATTEMPTS="3", WAIT_INTERVAL="1",
                   PATH=str(work / "bin") + os.pathsep + os.environ["PATH"])
        for cid, desc, hook, health in CASES:
            servers: list[Stub] = []

            def start(status: int, commit: str | None = None) -> str:
                s = Stub(status, commit)
                threading.Thread(target=s.serve_forever, daemon=True).start()
                servers.append(s)
                return s.url

            closed = f"http://127.0.0.1:{free_closed_port()}"
            hook_base = closed if hook == "closed" else start(int(hook))
            hook_url = f"{hook_base}/deploy/{HOOK_TOKEN}"
            public = {None: closed, "closed": closed, "match": None, "other": None}.get(health)
            if health == "match":
                public = start(200, SHA)
            elif health == "other":
                public = start(200, OTHER_SHA)
            elif health in ("503", "404"):
                public = start(int(health))
            public = public or closed

            print(f"=== case ({cid}) {desc}")
            code1, out1 = run_step(render(hook_script, hook_url, public), work, env)
            print("--- step: Trigger Render deploy")
            print("\n".join("    " + l for l in out1.rstrip().splitlines()) or "    (no output)")
            print(f"    exit code: {code1}")
            code2, out2 = None, ""
            if code1 == 0:
                code2, out2 = run_step(render(wait_script, hook_url, public), work, env)
                print("--- step: Wait for /health to report this commit")
                print("\n".join("    " + l for l in out2.rstrip().splitlines()))
                print(f"    exit code: {code2}")
            for s in servers:
                s.shutdown()
                s.server_close()

            hook_fail, wait_runs, wait_ok, hint, note = EXPECT[cid]
            out = out1 + out2
            checks = {
                "hook step " + ("fails" if hook_fail else "succeeds"): (code1 != 0) == hook_fail,
                "wait step " + ("runs" if wait_runs else "does not run"): (code2 is not None) == wait_runs,
                "HINT line " + ("printed" if hint else "absent"): ("HINT:" in out) == hint,
                "NOTE line " + ("printed" if note else "absent"): ("NOTE:" in out) == note,
                f"output contains '{MARKER[cid]}'": MARKER[cid] in out,
                "hook URL token not in output": HOOK_TOKEN not in out,
            }
            if wait_runs:
                checks["wait step " + ("exits 0" if wait_ok else "exits non-zero")] = (code2 == 0) == wait_ok
            verdict = all(checks.values())
            failures += not verdict
            print("--- checks: " + "; ".join(f"{k}: {'ok' if v else 'FAIL'}" for k, v in checks.items()))
            print(f"--- case ({cid}): {'PASS' if verdict else 'FAIL'}\n")
    print("ALL CASES PASS" if not failures else f"{failures} CASE(S) FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
