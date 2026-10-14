"""Tests for agent-hooks/pretool_bash_guard.py.

Every case runs the script as a subprocess with real stdin JSON and asserts the
exit code and stderr, so the exit-code contract is what is tested.
Run: python -m unittest discover -s agent-hooks/tests
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = HOOKS_DIR.parent
GUARD = HOOKS_DIR / "pretool_bash_guard.py"


def run_guard(payload, cwd=None):
    """Run the guard on `payload` (dict or raw string). Returns (code, stdout, stderr)."""
    if isinstance(payload, dict):
        payload = json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=payload.encode("utf-8"),
        capture_output=True,
        cwd=cwd,
        timeout=30,
    )
    return proc.returncode, proc.stdout.decode(), proc.stderr.decode()


def bash(command, cwd=None):
    return run_guard(
        {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd or str(REPO_ROOT)}
    )


class GuardTestCase(unittest.TestCase):
    def assertDenied(self, command, rule, cwd=None):
        code, out, err = bash(command, cwd)
        self.assertEqual(code, 2, f"expected deny for {command!r}, got {code}: {err}")
        self.assertIn(f"rule {rule}:", err, f"wrong rule for {command!r}: {err}")
        self.assertIn("Offending part:", err)
        self.assertIn("Instead:", err)
        self.assertEqual(out, "")
        return err

    def assertAllowed(self, command, cwd=None):
        code, out, err = bash(command, cwd)
        self.assertEqual(code, 0, f"expected allow for {command!r}, got {code}: {err}")
        self.assertEqual(out, "")
        self.assertEqual(err, "")


class Rule1ForcePush(GuardTestCase):
    def test_denied(self):
        for command in [
            "git push --force origin main",
            "git push -f origin main",
            "git push --force-with-lease origin main",
            "git push origin +main",
            "git push --force origin HEAD:main",
            "git push --force origin refs/heads/main",
            "git push -f origin master",
            "git push origin +master",
            "git push origin main --force",
            "git push -fu origin main",
            "git -C . push --force origin main",
            "git push --force",
            "git push -f origin",
            "git push --force-with-lease",
            "git push origin --delete main",
            "git push origin -d main",
            "git push origin :main",
            "git push origin :refs/heads/master",
            "git push --force origin HEAD",
            "git push --force --all origin",
            "git status && git push --force origin main",
            "FOO=1 git push -f origin main",
        ]:
            with self.subTest(command=command):
                self.assertDenied(command, 1)

    def test_allowed(self):
        for command in [
            "git push origin main",
            "git push",
            "git push --force-with-lease origin feature/x",
            "git push -f origin my-branch",
            "git push origin HEAD:main",
            "git push -u origin feature/x",
            "git push origin --delete feature/old",
            "git log --oneline | head -3",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_message_names_a_feature_branch(self):
        err = self.assertDenied("git push --force origin", 1)
        self.assertIn("feature branch", err)


class Rule2LocalReadOnly(GuardTestCase):
    def test_denied(self):
        root = REPO_ROOT.as_posix()
        for command in [
            "rm _local/x",
            "rm ./_local/x",
            'rm "_local/x"',
            "rm '_local/x'",
            "rm _local\\x",
            f"rm {root}/_local/x",
            f'rm "{root}/_local/x"',
            "rm -rf _local",
            "mv _local/a.md _local/b.md",
            "mv _local/a.md /tmp/",
            "cp notes.md _local/",
            "cp -r a b _local/",
            "touch _local/new.md",
            "truncate -s 0 _local/make-it-better.md",
            "sed -i s/a/b/ _local/make-it-better.md",
            "sed -i.bak s/a/b/ _local/make-it-better.md",
            "sed --in-place s/a/b/ _local/make-it-better.md",
            "echo x | tee _local/make-it-better.md",
            "echo x | tee -a _local/make-it-better.md",
            "echo x > _local/make-it-better.md",
            "echo x >> _local/make-it-better.md",
            "echo x >>_local/make-it-better.md",
            'echo x >> "_local/make-it-better.md"',
            "echo x 2>/dev/null >> ./_local/make-it-better.md",
            "git clean -fd _local",
            "git checkout -- _local/make-it-better.md",
            "git restore _local/make-it-better.md",
            "ls && rm _local/x",
            "dd if=/dev/zero of=_local/x",
            "rm _loc*",
        ]:
            with self.subTest(command=command):
                self.assertDenied(command, 2)

    def test_allowed(self):
        for command in [
            "cat _local/make-it-better.md",
            "ls _local",
            "ls -la _local/",
            "grep -n foo _local/make-it-better.md",
            "cp _local/make-it-better.md /tmp/copy.md",
            "sed -n 1,5p _local/make-it-better.md",
            "wc -l < _local/make-it-better.md",
            "rm local_notes.txt",
            "rm my_local/x",
            "touch docs/_local_not.md",
            "echo x > docs/note.md",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)


class Rule3EnvFiles(GuardTestCase):
    def test_denied(self):
        root = REPO_ROOT.as_posix()
        for command in [
            "cat .env",
            "cat ./.env",
            "cat backend/.env",
            'cat "$PWD/.env"',
            f"cat {root}/.env",
            "cat .env.local",
            "cat .env.production",
            "type .env",
            "head -n 3 .env",
            "tail .env",
            "less .env",
            "more .env",
            "grep JWT .env",
            "sed -n 1p .env",
            "awk '{print}' .env",
            "Get-Content .env",
            "echo SECRET=1 > .env",
            "echo SECRET=1 >> .env",
            "echo SECRET=1 >> backend/.env",
            "printf x | tee .env",
            "mv foo .env",
            "cat < .env",
            "cat .e*",
            "cat .env && echo done",
            "echo hi; cat ./.env",
            "source .env",
            ". ./.env",
        ]:
            with self.subTest(command=command):
                self.assertDenied(command, 3)

    def test_allowed(self):
        for command in [
            "cat .env.example",
            "grep -n JWT .env.example",
            "head .env.example",
            "docker compose up",
            "make up",
            "ls -la .env",
            "test -f .env",
            "git check-ignore .env",
            "echo hello",
            "cat docs/environment.md",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    # Issue #23: the owner's decision is that an agent may create .env from a
    # template with cp, and nothing else may write it.

    def test_allowed_cp_from_a_template_to_dot_env(self):
        for command in [
            "cp .env.example .env",  # the README's first setup step
            "cp ./.env.example ./.env",
            "cp .env.example backend/.env",
            "cp -n .env.example .env",
            'cp .env.example ".env"',
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_allowed_template_copies_and_readers(self):
        for command in [
            "cp .env.example .env.example.bak",
            "cp .env.example.bak .env.example",
            "cp .env.local.example .env.example",
            "cat .env.example",
            "cat .env.example.bak",
            "head .env.example",
            "grep -n JWT .env.example",
            "grep -n JWT .env.example.bak",
            "cat .env.local.example",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_allowed_grep_family_pattern_mentions(self):
        for command in [
            'grep -rn ".env" docs',
            'grep -rn "\\.env" docs',
            "grep -rn .env docs",
            "ls -a | grep -E '^\\.env'",
            "grep -e .env docs",
            "grep --regexp=.env docs",
            'rg ".env" docs',
            "egrep '^\\.env' README.md",
            "grep -n .env .env.example",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_allowed_find_name_patterns(self):
        for command in [
            'find . -name ".env*"',
            'find . -iname ".env.*"',
            "find . -name .env -type f",
            'find . -path "*/.env*"',
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_allowed_loop_word_lists_and_echo_text(self):
        for command in [
            'for f in ".env" ".env.local"; do echo "$f"; done',
            'for f in .env .env.example; do test -f "$f" && echo yes; done',
            "echo .env",
            'echo "see .env"',
            "printf '%s\\n' .env",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_denied_cp_and_mv_with_real_env_files(self):
        for command in [
            "cp .env .env.bak",
            "cp .env /tmp/x",
            "cp backend/.env x",
            "cp .env.local x",
            "cp foo .env",
            "cp /tmp/x .env",
            "cp .env.example .env.local",
            "cp .env.example .env.production",
            "cp .env.example .env.bak",
            "cp .env.example foo .env",  # not exactly one template source
            "cp -t . .env",
            "cp -r . .env",
            "mv .env.example .env",
            "mv .env .env.bak",
        ]:
            with self.subTest(command=command):
                self.assertDenied(command, 3)

    def test_denied_other_ways_to_write_dot_env(self):
        for command in [
            "cat .env.example > .env",
            "cp .env.example .env && cat .env",
            "sed -i 's/a/b/' .env",
            "sed -i s/a/b/ .env.local",
            "tee .env.production",
            "echo .env > .env",
            "printf x >> .env.local",
        ]:
            with self.subTest(command=command):
                self.assertDenied(command, 3)

    def test_denied_non_template_look_alikes(self):
        for command in ["cat .env.bak", "cat .env.example.local", "cp .env.bak x"]:
            with self.subTest(command=command):
                self.assertDenied(command, 3)

    def test_denied_grep_family_with_a_real_file_operand(self):
        for command in [
            "grep -e JWT .env",
            "grep -f .env foo",  # -f reads the patterns from the file
            "grep -rn JWT docs .env",
            "rg -n JWT .env",
            'grep -r JWT --include=".env*" .',
            'grep -r --include ".env*" JWT .',
            'rg --hidden -g ".env*" JWT',
        ]:
            with self.subTest(command=command):
                self.assertDenied(command, 3)

    def test_denied_find_that_can_print_contents(self):
        for command in [
            'find . -name ".env*" -exec cat {} +',
            "find . -name .env -execdir cat {} \\;",
            'find . -name ".env*" -fprint out.txt',
        ]:
            with self.subTest(command=command):
                self.assertDenied(command, 3)

    def test_denied_loop_that_touches_the_file_for_real(self):
        self.assertDenied("for f in .env; do cat .env; done", 3)

    def test_denied_by_default_for_other_commands(self):
        for command in ["source .env", "base64 .env", "cut -d= -f1 .env", "sort .env"]:
            with self.subTest(command=command):
                self.assertDenied(command, 3)

    def test_denial_still_points_at_the_template(self):
        err = self.assertDenied("cat .env", 3)
        self.assertIn(".env.example", err)
        self.assertIn("ask the repo owner", err)

    def test_message_quotes_only_the_file_name(self):
        err = self.assertDenied("echo SECRET_VALUE_12345 >> .env", 3)
        self.assertNotIn("SECRET_VALUE_12345", err)
        self.assertIn(".env", err)
        err = self.assertDenied("grep SECRET_VALUE_12345 .env", 3)
        self.assertNotIn("SECRET_VALUE_12345", err)


class Rule4RecursiveRm(GuardTestCase):
    def test_denied(self):
        for command in [
            "rm -rf /",
            "rm -rf ~",
            "rm -rf $HOME",
            'rm -rf "$HOME"',
            "rm -rf ..",
            "rm -rf ../x",
            "rm -rf ../other",
            "rm -rf /tmp/x",
            "rm -rf C:\\Users\\x",
            "rm -rf C:/Users/x",
            "rm -rf /c/Users/x",
            "rm -fr /tmp/x",
            "rm -r /tmp/x",
            "rm -R /tmp/x",
            "rm --recursive /tmp/x",
            "rm -r -f /tmp/x",
            "rm -f -r /tmp/x",
            "rm -rf node_modules /tmp/x",
            "rm -rf $(pwd)/x",
            "rm -rf `pwd`/x",
            "rm -rf $SOMEDIR/x",
            "rm -rf ${SOMEDIR}",
            "rm -rf {a,/tmp/b}",
            "rm -rf .",
            "rm -rf frontend/../..",
            "sudo rm -rf /tmp/x",
            "ls && rm -rf /tmp/x",
            "ls | xargs rm -rf",
        ]:
            with self.subTest(command=command):
                self.assertDenied(command, 4)

    def test_allowed(self):
        for command in [
            "rm -rf node_modules",
            "rm -rf ./frontend/dist",
            "rm -rf backend/.pytest_cache",
            "rm -rf frontend/node_modules backend/.pytest_cache",
            "rm file.txt",
            "rm /tmp/plain-file-outside-the-repo",
            "rm -f /tmp/plain-file-outside-the-repo",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_relative_targets_resolve_against_cwd(self):
        frontend = str(REPO_ROOT / "frontend")
        self.assertAllowed("rm -rf node_modules", cwd=frontend)
        self.assertAllowed("rm -rf ../backend/.pytest_cache", cwd=frontend)
        self.assertDenied("rm -rf ../..", 4, cwd=frontend)
        # A relative target in a cwd outside the repo is outside the repo.
        outside = str(REPO_ROOT.parent)
        self.assertDenied("rm -rf node_modules", 4, cwd=outside)

    def test_repo_root_comes_from_the_script_not_from_cwd(self):
        # cwd claims to be the parent of the repo; ".." must still be outside.
        self.assertDenied("rm -rf ../x", 4, cwd=str(REPO_ROOT.parent))

    def test_message_says_why_for_unresolvable_targets(self):
        err = self.assertDenied("rm -rf $SOMEDIR/x", 4)
        self.assertIn("variable", err)


class Rule5RenderDeployHook(GuardTestCase):
    def test_denied(self):
        for command in [
            'curl -X POST "$RENDER_DEPLOY_HOOK_URL"',
            "curl -X POST $RENDER_DEPLOY_HOOK_URL",
            'curl -X POST "${RENDER_DEPLOY_HOOK_URL}"',
            "curl.exe -X POST %RENDER_DEPLOY_HOOK_URL%",
            "wget https://api.render.com/deploy/srv-abc123?key=SECRETKEY",
            "curl https://api.render.com/deploy/srv-abc123?key=SECRETKEY",
            "Invoke-WebRequest -Uri https://api.render.com/deploy/srv-abc",
            "iwr $env:RENDER_DEPLOY_HOOK_URL",
            "Invoke-RestMethod -Method Post $env:RENDER_DEPLOY_HOOK_URL",
            "irm https://api.render.com/deploy/srv-abc",
            "echo go && curl -sS -X POST $RENDER_DEPLOY_HOOK_URL",
        ]:
            with self.subTest(command=command):
                self.assertDenied(command, 5)

    def test_allowed(self):
        for command in [
            "curl http://localhost:8100/health",
            "curl https://pinpoint.onrender.com/health",
            "curl https://something.onrender.com/deploy-notes",
            "gh run list",
        ]:
            with self.subTest(command=command):
                self.assertAllowed(command)

    def test_the_deploy_url_is_not_echoed_back(self):
        err = self.assertDenied("curl https://api.render.com/deploy/srv-abc123?key=SECRETKEY", 5)
        self.assertNotIn("SECRETKEY", err)
        self.assertNotIn("srv-abc123", err)
        self.assertIn("docs/release-process.md", err)


class FailOpenAndContract(GuardTestCase):
    def test_non_bash_tool_is_allowed(self):
        code, out, err = run_guard(
            {"tool_name": "Write", "tool_input": {"command": "git push --force origin main"}, "cwd": str(REPO_ROOT)}
        )
        self.assertEqual((code, out, err), (0, "", ""))

    def test_malformed_json_exits_1_not_2(self):
        code, out, err = run_guard("this is not json")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("NOT checked", err)

    def test_empty_stdin_exits_1(self):
        self.assertEqual(run_guard("")[0], 1)

    def test_json_that_is_not_an_object_exits_1(self):
        self.assertEqual(run_guard("[1, 2]")[0], 1)

    def test_bash_without_a_command_exits_1(self):
        for payload in [
            {"tool_name": "Bash", "tool_input": {}, "cwd": str(REPO_ROOT)},
            {"tool_name": "Bash", "cwd": str(REPO_ROOT)},
            {"tool_name": "Bash", "tool_input": {"command": 42}},
        ]:
            with self.subTest(payload=payload):
                code, _, err = run_guard(payload)
                self.assertEqual(code, 1)
                self.assertEqual(len(err.strip().splitlines()), 1)

    def test_missing_tool_name_exits_1(self):
        self.assertEqual(run_guard({"tool_input": {"command": "ls"}})[0], 1)

    def test_internal_exception_is_fail_open(self):
        # A non-string cwd that cannot be used must not produce exit 2.
        code, _, _ = run_guard({"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": 5})
        self.assertIn(code, (0, 1))

    def test_unparseable_command_is_matched_on_the_raw_text(self):
        for command, rule in [
            ('git push --force origin main "unbalanced', 1),
            ("cat .env 'unbalanced", 3),
            ('rm -rf /tmp/x "unbalanced', 4),
            ('echo "unbalanced; rm _local/x', 2),
            ('curl -X POST "$RENDER_DEPLOY_HOOK_URL', 5),
        ]:
            with self.subTest(command=command):
                err = self.assertDenied(command, rule)
                self.assertIn("raw text", err)

    def test_unparseable_harmless_command_is_allowed(self):
        self.assertAllowed('echo "unbalanced')

    def test_heredoc_body_is_data_not_commands(self):
        self.assertAllowed("cat > /tmp/note.txt <<'EOF'\ngit push --force origin main\ncat .env\nEOF")

    def test_quoted_text_is_not_a_command(self):
        self.assertAllowed('git commit -m "never git push --force origin main or cat .env"')
        self.assertAllowed("echo 'rm -rf /'")

    def test_comment_is_not_a_command(self):
        self.assertAllowed("ls # git push --force origin main")

    def test_command_substitution_is_scanned(self):
        self.assertDenied("echo $(git push --force origin main)", 1)
        self.assertDenied('echo "`rm -rf /tmp/x`"', 4)

    def test_every_deny_message_is_short(self):
        err = self.assertDenied("git push --force origin main", 1)
        self.assertLess(len(err.splitlines()), 8)


class Imports(unittest.TestCase):
    def test_only_the_standard_library_is_imported(self):
        import ast

        allowed = {"fnmatch", "json", "ntpath", "os", "posixpath", "re", "shlex", "sys", "pathlib"}
        for name in ("pretool_bash_guard.py", "posttool_test_reminder.py"):
            tree = ast.parse((HOOKS_DIR / name).read_text(encoding="utf-8"))
            found = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    found |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom):
                    found.add((node.module or "").split(".")[0])
            with self.subTest(script=name):
                self.assertLessEqual(found, allowed)


if __name__ == "__main__":
    unittest.main()
