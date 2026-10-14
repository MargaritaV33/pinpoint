"""Tests for agent-hooks/posttool_test_reminder.py (run as a subprocess)."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HOOKS_DIR.parent
SCRIPT = HOOKS_DIR / "posttool_test_reminder.py"


def run_reminder(payload):
    if isinstance(payload, dict):
        payload = json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], input=payload.encode("utf-8"), capture_output=True, timeout=30
    )
    return proc.returncode, proc.stdout.decode(), proc.stderr.decode()


def edit(file_path, tool="Edit", cwd=None):
    payload = {"tool_name": tool, "tool_input": {"file_path": file_path}, "tool_response": {"success": True}}
    if cwd is not None:
        payload["cwd"] = cwd
    return run_reminder(payload)


def context_of(stdout):
    """The text the model receives: hookSpecificOutput.additionalContext."""
    data = json.loads(stdout)
    out = data["hookSpecificOutput"]
    assert out["hookEventName"] == "PostToolUse"
    return out["additionalContext"]


class PostToolReminder(unittest.TestCase):
    def test_backend_names_make_test(self):
        for tool in ("Edit", "Write", "MultiEdit"):
            with self.subTest(tool=tool):
                code, out, err = edit("backend/app/main.py", tool=tool)
                self.assertEqual(code, 0)
                self.assertEqual(err, "")
                self.assertIn("`make test`", context_of(out))
                self.assertNotIn("frontend-test", context_of(out))

    def test_absolute_backend_path(self):
        code, out, _ = edit(str(REPO_ROOT / "backend" / "tests" / "test_x.py"))
        self.assertEqual(code, 0)
        self.assertIn("`make test`", context_of(out))

    def test_frontend_path_with_backslashes(self):
        code, out, _ = edit("frontend\\src\\lib\\api\\client.ts")
        self.assertEqual(code, 0)
        self.assertIn("`make frontend-test`", context_of(out))
        self.assertNotIn("`make test`", context_of(out))

    def test_absolute_frontend_path_with_backslashes(self):
        path = str(REPO_ROOT / "frontend" / "src" / "App.tsx").replace("/", "\\")
        code, out, _ = edit(path)
        self.assertEqual(code, 0)
        self.assertIn("`make frontend-test`", context_of(out))

    def test_absolute_and_windows_spellings_agree(self):
        a = edit(str(REPO_ROOT / "backend" / "app" / "x.py"))[1]
        b = edit("backend\\app\\x.py")[1]
        c = edit(str(REPO_ROOT / "backend" / "app" / "x.py").replace("/", "\\"))[1]
        self.assertEqual(a, b)
        self.assertEqual(a, c)

    def test_relative_path_resolves_against_cwd(self):
        code, out, _ = edit("src/App.tsx", cwd=str(REPO_ROOT / "frontend"))
        self.assertEqual(code, 0)
        self.assertIn("`make frontend-test`", context_of(out))

    def test_other_paths_print_nothing(self):
        for path in [
            "docs/x.md",
            "README.md",
            "mcp-server/src/server.py",
            "backend-notes/x.md",
            "agent-hooks/run.sh",
            str(REPO_ROOT / "docs" / "x.md"),
            "/somewhere/else/backend/x.py",
            "..\\backend\\x.py",
        ]:
            with self.subTest(path=path):
                self.assertEqual(edit(path, cwd=str(REPO_ROOT)), (0, "", ""))

    def test_other_tools_print_nothing(self):
        for tool in ("Read", "Bash", "Grep"):
            with self.subTest(tool=tool):
                payload = {"tool_name": tool, "tool_input": {"file_path": "backend/app/main.py"}}
                self.assertEqual(run_reminder(payload), (0, "", ""))

    def test_it_never_blocks(self):
        for payload in ["not json", "", "[]", {"tool_name": "Edit"}, {"tool_name": "Edit", "tool_input": {"file_path": 3}}]:
            with self.subTest(payload=payload):
                self.assertIn(run_reminder(payload)[0], (0, 1))

    def test_malformed_json_exits_1_with_a_one_line_warning(self):
        code, out, err = run_reminder("not json")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
