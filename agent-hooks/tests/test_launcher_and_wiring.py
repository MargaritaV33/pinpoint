"""Tests for agent-hooks/run.sh and for the hook wiring in .claude/settings.json.

The launcher is POSIX sh; these tests need a `sh` on PATH (Git Bash on Windows,
any Linux). Without one they are skipped, and the skip says why.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HOOKS_DIR.parent
RUN_SH = HOOKS_DIR / "run.sh"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
SH = shutil.which("sh")

DENY = {"tool_name": "Bash", "tool_input": {"command": "git push --force origin main"}, "cwd": str(REPO_ROOT)}
ALLOW = {"tool_name": "Bash", "tool_input": {"command": "git status"}, "cwd": str(REPO_ROOT)}


def sh_path(p):
    return str(p).replace("\\", "/")


def run_sh(args, payload, env=None):
    return subprocess.run(
        [SH] + args,
        input=json.dumps(payload).encode(),
        capture_output=True,
        env=env,
        timeout=60,
    )


def write_exe(path, body):
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@unittest.skipUnless(SH, "no `sh` on PATH: the launcher cannot be run here")
class Launcher(unittest.TestCase):
    def test_launcher_runs_the_guard_and_passes_stdin_and_exit_code_through(self):
        denied = run_sh([sh_path(RUN_SH), "pretool_bash_guard.py"], DENY)
        self.assertEqual(denied.returncode, 2, denied.stderr.decode())
        self.assertIn(b"rule 1:", denied.stderr)
        allowed = run_sh([sh_path(RUN_SH), "pretool_bash_guard.py"], ALLOW)
        self.assertEqual((allowed.returncode, allowed.stdout, allowed.stderr), (0, b"", b""))

    def test_launcher_runs_the_posttool_script(self):
        payload = {"tool_name": "Write", "tool_input": {"file_path": "backend/x.py"}}
        proc = run_sh([sh_path(RUN_SH), "posttool_test_reminder.py"], payload)
        self.assertEqual(proc.returncode, 0)
        self.assertIn(b"make test", proc.stdout)

    def test_launcher_works_from_a_folder_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="dir with spaces ") as tmp:
            dest = Path(tmp) / "agent-hooks"
            shutil.copytree(HOOKS_DIR, dest, ignore=shutil.ignore_patterns("tests", "__pycache__"))
            proc = run_sh([sh_path(dest / "run.sh"), "pretool_bash_guard.py"], DENY)
            self.assertEqual(proc.returncode, 2, proc.stderr.decode())

    def _env_with_path(self, directory):
        env = dict(os.environ)
        env["PATH"] = sh_path(directory)
        return env

    def test_store_stub_python3_is_skipped_and_python_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            # Like the Windows Store stub: present on PATH, does not run Python.
            write_exe(tmp / "python3", "echo 'Python was not found; run without arguments to install from the Microsoft Store' >&2\nexit 9\n")
            write_exe(tmp / "python", f'exec "{sh_path(sys.executable)}" "$@"\n')
            proc = run_sh([sh_path(RUN_SH), "pretool_bash_guard.py"], DENY, env=self._env_with_path(tmp))
            self.assertEqual(proc.returncode, 2, proc.stderr.decode())
            self.assertIn(b"rule 1:", proc.stderr)

    def test_python_below_3_8_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write_exe(tmp / "python3", "exit 1\n")  # what a failing version probe looks like
            write_exe(tmp / "python", "exit 1\n")
            proc = run_sh([sh_path(RUN_SH), "pretool_bash_guard.py"], DENY, env=self._env_with_path(tmp))
            self.assertEqual(proc.returncode, 1)

    def test_no_interpreter_is_fail_open_with_a_clear_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_sh([sh_path(RUN_SH), "pretool_bash_guard.py"], DENY, env=self._env_with_path(tmp))
            self.assertEqual(proc.returncode, 1)  # never 2: a missing Python must not block every command
            self.assertEqual(proc.stdout, b"")
            err = proc.stderr.decode()
            self.assertIn("NOT active", err)
            self.assertIn("Install Python", err)

    def test_missing_script_argument_is_fail_open(self):
        proc = run_sh([sh_path(RUN_SH)], DENY)
        self.assertEqual(proc.returncode, 1)
        self.assertIn(b"NOT active", proc.stderr)


class Wiring(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads(SETTINGS.read_text(encoding="utf-8"))

    def test_attribution_is_unchanged(self):
        self.assertEqual(self.settings["attribution"], {"commit": "", "pr": "", "sessionUrl": False})
        # byte-for-byte: the line is still there exactly as it was
        self.assertIn(
            '  "attribution": { "commit": "", "pr": "", "sessionUrl": false }\n',
            SETTINGS.read_text(encoding="utf-8"),
        )

    def _hooks(self, event):
        entries = self.settings["hooks"][event]
        self.assertEqual(len(entries), 1)
        self.assertEqual(len(entries[0]["hooks"]), 1)
        return entries[0]["matcher"], entries[0]["hooks"][0]

    def test_pretool_entry(self):
        matcher, hook = self._hooks("PreToolUse")
        self.assertEqual(matcher, "Bash")
        self.assertEqual(hook["type"], "command")
        self.assertEqual(hook["command"], 'sh "$CLAUDE_PROJECT_DIR/agent-hooks/run.sh" pretool_bash_guard.py')

    def test_posttool_entry(self):
        matcher, hook = self._hooks("PostToolUse")
        self.assertEqual(matcher, "Edit|Write|MultiEdit")
        self.assertEqual(hook["command"], 'sh "$CLAUDE_PROJECT_DIR/agent-hooks/run.sh" posttool_test_reminder.py')

    @unittest.skipUnless(SH, "no `sh` on PATH")
    def test_the_command_line_works_as_claude_code_runs_it(self):
        """Run the exact settings.json command through `sh -c` with CLAUDE_PROJECT_DIR set.

        On the dev machine the repo path contains a space, so this also proves the quoting.
        """
        for event, payload, expected in [
            ("PreToolUse", DENY, 2),
            ("PreToolUse", ALLOW, 0),
            ("PostToolUse", {"tool_name": "Edit", "tool_input": {"file_path": "backend/a.py"}}, 0),
        ]:
            command = self.settings["hooks"][event][0]["hooks"][0]["command"]
            env = dict(os.environ, CLAUDE_PROJECT_DIR=str(REPO_ROOT))
            with self.subTest(event=event, expected=expected):
                proc = subprocess.run(
                    [SH, "-c", command], input=json.dumps(payload).encode(), capture_output=True, env=env, timeout=60
                )
                self.assertEqual(proc.returncode, expected, proc.stderr.decode())


if __name__ == "__main__":
    unittest.main()
