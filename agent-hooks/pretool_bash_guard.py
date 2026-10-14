#!/usr/bin/env python3
"""PreToolUse guard for Claude Code's Bash tool (Python standard library only).

Contract (see agent-hooks/README.md):
  stdin   Claude Code's PreToolUse JSON: tool_name, tool_input.command, cwd.
  exit 0  allow (no output).
  exit 2  deny; stderr says which rule fired, quotes the offending part of the
          command and says what to do instead. Claude Code feeds it to the agent.
  exit 1  internal problem. FAIL-OPEN: one warning line on stderr and the
          command is NOT blocked. Never exit 2 for an internal problem.

This is a guardrail against accidents, not a security boundary. It matches on
the shell string, so `bash -c "..."`, `eval`, a script written and then run, a
variable that holds a path, and `cd _local && rm x` are not caught. See
docs/permissions.md ("What the hooks cannot enforce").
"""

import fnmatch
import json
import ntpath
import os
import posixpath
import re
import shlex
import sys
from pathlib import Path

# The repo root comes from this file's location, never from the hook's cwd.
REPO_ROOT = Path(__file__).resolve().parent.parent
IS_WINDOWS = os.name == "nt"

SUB = "\x01SUB\x01"  # stands in for a $(...) / `...` / <(...) inside a word
PROTECTED_BRANCHES = ("main", "master")

RULE_NAMES = {
    1: "rule 1: no force push to main",
    2: "rule 2: _local/ is read-only for the shell",
    3: "rule 3: real .env files stay out of the shell",
    4: "rule 4: no recursive rm outside the repo",
    5: "rule 5: the Render deploy hook is CI's job",
}


class ParseError(Exception):
    """The command could not be parsed; the caller falls back to raw matching."""


class Command:
    """One simple command: its words and its file redirections."""

    def __init__(self, words, outs, ins):
        self.words = words  # shell words, quotes already removed
        self.outs = outs  # targets of > >> >| &> (write redirections)
        self.ins = ins  # targets of < (read redirections)


class Violation:
    def __init__(self, rule, quoted, instead):
        self.rule = rule
        self.quoted = quoted
        self.instead = instead


# --------------------------------------------------------------------------
# Parsing: a small quote-aware scanner, then shlex for the words.
# --------------------------------------------------------------------------


def normalize(command):
    """Make Windows spellings comparable. Analysis only; nothing is executed.

    A backslash before a path character becomes a slash, so `_local\\x` and
    `C:\\Users\\x` read like their POSIX forms. A backslash before a quote, a
    space or `$` keeps its shell meaning.
    """
    s = command.replace("\r\n", "\n").replace("\\\n", " ")
    return re.sub(r"\\(?=[A-Za-z0-9_.~-])", "/", s)


class Scanner:
    """Split a command string into simple commands.

    Separators `; & | ( ) newline` outside quotes end a command. `$(...)`,
    backticks and `<(...)` are scanned as commands of their own and leave the
    SUB marker in the outer word. Redirections are taken out of the word list.
    Heredoc bodies are skipped. Raises ParseError on unbalanced quotes.
    """

    def __init__(self, text):
        self.s = text
        self.i = 0
        self.segments = []  # (text, outs, ins)
        self.heredocs = []  # pending (delimiter, strip_tabs)

    def run(self):
        self._scan(in_sub=False)
        return self.segments

    def _read_word(self):
        """Read one raw word (quotes kept) for a redirection target."""
        s, n = self.s, len(self.s)
        while self.i < n and s[self.i] in " \t":
            self.i += 1
        start = self.i
        quote = None
        while self.i < n:
            c = s[self.i]
            if quote:
                if c == quote:
                    quote = None
            elif c in "'\"":
                quote = c
            elif c == "\\" and self.i + 1 < n:
                self.i += 1
            elif c in " \t\n;|&<>()":
                break
            self.i += 1
        if quote:
            raise ParseError("unbalanced quote in redirection target")
        return s[start : self.i]

    def _skip_heredoc_bodies(self):
        s, n = self.s, len(self.s)
        for delim, strip_tabs in self.heredocs:
            while self.i < n:
                end = s.find("\n", self.i)
                line = s[self.i : (n if end == -1 else end)].rstrip("\r")
                self.i = n if end == -1 else end + 1
                if (line.lstrip("\t") if strip_tabs else line) == delim:
                    break
        self.heredocs = []

    def _scan(self, in_sub):
        s, n = self.s, len(self.s)
        cur, outs, ins = [], [], []
        quote = None

        def flush():
            text = "".join(cur).strip()
            if text or outs or ins:
                self.segments.append((text, list(outs), list(ins)))
            del cur[:], outs[:], ins[:]

        def strip_fd_digits():
            j = len(cur)
            while j > 0 and cur[j - 1].isdigit():
                j -= 1
            if j < len(cur) and (j == 0 or cur[j - 1] in " \t"):
                del cur[j:]

        while self.i < n:
            c = s[self.i]
            nxt = s[self.i + 1] if self.i + 1 < n else ""

            if quote == "'":
                cur.append(c)
                if c == "'":
                    quote = None
                self.i += 1
                continue

            if c == "\\" and nxt:
                cur.append(c + nxt)
                self.i += 2
                continue

            if c == "`":
                end = self.i + 1
                while end < n and s[end] != "`":
                    end += 2 if s[end] == "\\" else 1
                if end >= n:
                    raise ParseError("unbalanced backtick")
                inner = Scanner(s[self.i + 1 : end])
                self.segments.extend(inner.run())
                cur.append(SUB)
                self.i = end + 1
                continue

            if c == "$" and nxt == "(":
                self.i += 2
                self._scan(in_sub=True)
                cur.append(SUB)
                continue

            if quote == '"':
                cur.append(c)
                if c == '"':
                    quote = None
                self.i += 1
                continue

            if c in "'\"":
                quote = c
                cur.append(c)
                self.i += 1
                continue

            if c in "<>" and nxt == "(":
                self.i += 2
                self._scan(in_sub=True)
                cur.append(SUB)
                continue

            if c == "#" and (not cur or cur[-1] in " \t"):
                while self.i < n and s[self.i] != "\n":
                    self.i += 1
                continue

            if c == ">" or (c == "&" and nxt == ">"):
                strip_fd_digits()
                self.i += 1 if c == ">" else 2
                if c == ">" and self.i < n and s[self.i] == "&":
                    self.i += 1
                    if self.i < n and (s[self.i].isdigit() or s[self.i] == "-"):
                        while self.i < n and (s[self.i].isdigit() or s[self.i] == "-"):
                            self.i += 1
                        continue  # `2>&1`: descriptor duplication, no file
                elif self.i < n and s[self.i] in ">|":
                    self.i += 1
                target = self._read_word()
                if target:
                    outs.append(target)
                continue

            if c == "<":
                strip_fd_digits()
                if s.startswith("<<<", self.i):
                    self.i += 3
                    self._read_word()
                    continue
                if s.startswith("<<", self.i):
                    self.i += 2
                    strip_tabs = self.i < n and s[self.i] == "-"
                    if strip_tabs:
                        self.i += 1
                    raw = self._read_word()
                    delim = raw.replace("'", "").replace('"', "").replace("\\", "")
                    if delim:
                        self.heredocs.append((delim, strip_tabs))
                    continue
                self.i += 1
                target = self._read_word()
                if target:
                    ins.append(target)
                continue

            if c == ")":
                flush()
                self.i += 1
                if in_sub:
                    return
                continue

            if c == "\n":
                flush()
                self.i += 1
                if self.heredocs:
                    self._skip_heredoc_bodies()
                continue

            if c in ";|&(":
                flush()
                self.i += 1
                continue

            cur.append(c)
            self.i += 1

        if quote:
            raise ParseError("unbalanced quote")
        if in_sub:
            raise ParseError("unterminated $(")
        flush()


def unquote(raw):
    try:
        parts = shlex.split(raw)
    except ValueError as exc:
        raise ParseError(str(exc))
    return "".join(parts)


def parse_commands(command):
    """Parse with the scanner and shlex. Raises ParseError when it cannot."""
    commands = []
    for text, outs, ins in Scanner(normalize(command)).run():
        try:
            words = shlex.split(text)
        except ValueError as exc:
            raise ParseError(str(exc))
        commands.append(Command(words, [unquote(o) for o in outs], [unquote(i) for i in ins]))
    return commands


def parse_commands_raw(command):
    """Fallback for a command that cannot be parsed: crude split on the raw text.

    The same rules run over the pieces; only the splitting is rougher.
    """
    commands = []
    text = normalize(command)
    for piece in re.split(r"[;&|()\n`]|\$\(", text):
        outs = [o.strip("'\"") for o in re.findall(r"(?:^|[\s\d&])>>?\|?\s*([^\s<>]+)", piece)]
        ins = [i.strip("'\"") for i in re.findall(r"(?:^|[\s\d])<(?![<(])\s*([^\s<>]+)", piece)]
        piece = re.sub(r"(?:^|[\s\d&])>>?\|?\s*[^\s<>]+", " ", piece)
        piece = re.sub(r"(?:^|[\s\d])<(?![<(])\s*[^\s<>]+", " ", piece)
        words = [w for w in piece.replace('"', " ").replace("'", " ").split() if w]
        if words or outs or ins:
            commands.append(Command(words, outs, ins))
    return commands


# --------------------------------------------------------------------------
# Helpers shared by the rules.
# --------------------------------------------------------------------------

WRAPPERS = {
    "sudo", "doas", "env", "command", "builtin", "exec", "nohup", "time", "nice",
    "ionice", "setsid", "stdbuf", "xargs", "if", "then", "elif", "else", "while",
    "until", "do", "!", "{", "}",
}  # fmt: skip


def cmd_name(word):
    name = word.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def split_command(words):
    """Return (name, args) after skipping env assignments and wrapper commands."""
    i = 0
    while i < len(words):
        w = words[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", w):
            i += 1
        elif cmd_name(w) in WRAPPERS:
            i += 1
            while i < len(words) and words[i].startswith("-") and len(words[i]) > 1:
                i += 1
        else:
            break
    if i >= len(words):
        return None, []
    return cmd_name(words[i]), words[i + 1 :]


def show(words, limit=160):
    text = " ".join(words).replace(SUB, "$(...)")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def to_slashes(path):
    return path.replace("\\", "/")


def canon_path(path, cwd):
    """Normalise a path to a comparable absolute string, or None if unresolvable.

    No symlink resolution. Handles `C:\\x`, `C:/x`, Git Bash `/c/x`, `..` and
    relative paths (resolved against cwd). Windows paths compare case-blind.
    """
    p = to_slashes(path)
    if IS_WINDOWS:
        p = re.sub(r"^/([A-Za-z])(?=/|$)", r"\1:", p)
    if re.match(r"^[A-Za-z]:(?!/)", p):
        return None  # `C:foo`: drive-relative, cannot be resolved
    if re.match(r"^[A-Za-z]:/", p):
        out = ntpath.normpath(p).replace("\\", "/")
        return out.lower() if IS_WINDOWS else out
    if p.startswith("/"):
        out = posixpath.normpath(p)
        if out.startswith("//"):
            out = out[1:]
        return out.lower() if IS_WINDOWS else out
    base = canon_path(cwd, None) if cwd else None
    if base is None:
        return None
    return canon_path(base + "/" + p, None)


# --------------------------------------------------------------------------
# Rule 1: force push to main (and deleting main).
# --------------------------------------------------------------------------

GIT_GLOBAL_OPTS_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}
PUSH_OPTS_WITH_ARG = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}


def git_subcommand(args):
    i = 0
    while i < len(args):
        a = args[i]
        if a in GIT_GLOBAL_OPTS_WITH_ARG:
            i += 2
        elif a.startswith("-"):
            i += 1
        else:
            return a, args[i + 1 :]
    return None, []


def branch_of(ref):
    ref = ref.strip()
    for prefix in ("refs/heads/", "heads/"):
        if ref.startswith(prefix):
            return ref[len(prefix) :]
    return ref


def rule1_git_push(args):
    sub, rest = git_subcommand(args)
    if sub != "push":
        return []
    force = delete = False
    has_all = False
    positionals = []
    i, after_dd = 0, False
    while i < len(rest):
        a = rest[i]
        if after_dd or not a.startswith("-") or a == "-":
            positionals.append(a)
        elif a == "--":
            after_dd = True
        elif a.startswith("--"):
            name = a.split("=", 1)[0]
            if name in ("--force", "--force-with-lease", "--force-if-includes"):
                force = True
            elif name == "--delete":
                delete = True
            elif name == "--mirror":
                force = has_all = True
            elif name in ("--all", "--branches"):
                has_all = True
            elif name in PUSH_OPTS_WITH_ARG and "=" not in a:
                i += 1
        else:
            letters = a[1:]
            if "f" in letters:
                force = True
            if "d" in letters:
                delete = True
            if a == "-o":
                i += 1
        i += 1
    refspecs = positionals[1:]  # positionals[0] is the remote
    shown = "git " + show(["push"] + rest)
    out = []
    forced_msg = "Name a feature branch instead: git push --force-with-lease origin feature/x."

    def deny(why, instead):
        out.append(Violation(1, f'{shown}  ({why})', instead))

    if force and not refspecs:
        deny(
            "force push with no explicit refspec; it may target the current branch, which may be main",
            forced_msg,
        )
    if force and has_all:
        deny("forced push of all branches includes main", forced_msg)
    for spec in refspecs:
        plus = spec.startswith("+")
        body = spec.lstrip("+")
        has_colon = ":" in body
        src, dst = body.split(":", 1) if has_colon else (body, body)
        dst_branch = branch_of(dst)
        is_protected = dst_branch in PROTECTED_BRANCHES
        if delete and branch_of(body) in PROTECTED_BRANCHES:
            deny("deleting " + branch_of(body), "Never delete main; ask the repo owner.")
        elif has_colon and src == "" and is_protected:
            deny("deleting " + dst_branch, "Never delete main; ask the repo owner.")
        elif (force or plus) and is_protected:
            deny("force push to " + dst_branch, forced_msg)
        elif (force or plus) and (dst_branch in ("HEAD", "@") or "*" in dst_branch):
            deny(
                "force push whose target may resolve to main",
                forced_msg,
            )
    return out


# --------------------------------------------------------------------------
# Rule 2: _local/ is read-only for the shell.
# --------------------------------------------------------------------------

LOCAL_RE = re.compile(r"(^|[/=:])_local(/|$)", re.I)
LOCAL_WRITERS = {
    "rm", "mv", "touch", "truncate", "tee", "shred", "rmdir", "mkdir", "ln",
    "unlink", "dd", "install",
}  # fmt: skip
GIT_LOCAL_SUBS = {"clean", "checkout", "restore", "rm", "mv"}


def refers_to_local(word):
    p = to_slashes(word).replace(SUB, "")
    if LOCAL_RE.search(p):
        return True
    for comp in p.split("/"):  # `_loc*`, `_l?cal`; a bare `*` is not treated as _local
        if comp not in ("", "*") and any(ch in comp for ch in "*?[") and fnmatch.fnmatchcase("_local", comp.lower()):
            return True
    return False


def is_inplace_sed(args):
    for a in args:
        if a == "--in-place" or a.startswith("--in-place="):
            return True
        if re.match(r"^-[A-Za-z]*i", a) and not a.startswith("--"):
            return True
    return False


def cp_destinations(args):
    dests, positional, i = [], [], 0
    while i < len(args):
        a = args[i]
        if a in ("-t", "--target-directory") and i + 1 < len(args):
            dests.append(args[i + 1])
            i += 1
        elif a.startswith("--target-directory="):
            dests.append(a.split("=", 1)[1])
        elif not a.startswith("-"):
            positional.append(a)
        i += 1
    if positional:
        dests.append(positional[-1])
    return dests


def rule2_local(name, args, cmd):
    hits = []
    if name in LOCAL_WRITERS:
        hits = [a for a in args if refers_to_local(a)]
    elif name == "cp":
        hits = [d for d in cp_destinations(args) if refers_to_local(d)]
    elif name in ("sed", "gsed") and is_inplace_sed(args):
        hits = [a for a in args if refers_to_local(a)]
    elif name in ("awk", "gawk") and "inplace" in args:
        hits = [a for a in args if refers_to_local(a)]
    elif name == "git":
        sub, rest = git_subcommand(args)
        if sub in GIT_LOCAL_SUBS:
            hits = [a for a in rest if refers_to_local(a)]
    out = []
    if hits:
        out.append(
            Violation(
                2,
                show([name] + args),
                "_local/ holds the owner's parked notes; read it with cat/ls/grep, "
                "and ask the repo owner for any change (the PM appends rows to "
                "_local/make-it-better.md with the Edit/Write tools).",
            )
        )
    for target in cmd.outs:
        if refers_to_local(target):
            out.append(
                Violation(
                    2,
                    f"redirection into {target}",
                    "_local/ is read-only for the shell; ask the repo owner, or use the Edit/Write tools for the one documented file.",
                )
            )
    return out


# --------------------------------------------------------------------------
# Rule 3: real .env files.
# --------------------------------------------------------------------------

ENV_BASE_RE = re.compile(r"^\.env(\.[A-Za-z0-9_-]+)*$", re.I)
ENV_TEMPLATE_SUFFIXES = {"example", "sample", "template", "dist"}
ENV_GLOB_CANDIDATES = [".env", ".env.local", ".env.production", ".env.development", ".env.test"]
# Commands that mention a file without printing or changing its contents.
ENV_NONPRINTING = {
    "ls", "dir", "stat", "test", "[", "[[", "file", "wc", "du", "realpath", "readlink",
    "dirname", "basename", "chmod", "chown", "cd", "git", "docker", "docker-compose",
    "make", "uv", "npm", "npx",
}  # fmt: skip


def real_env_name(word):
    """Return the file name if `word` points at a real env file, else None."""
    p = to_slashes(word).replace(SUB, "")
    for cand in (p, p.split("=", 1)[1] if "=" in p else ""):
        base = cand.rstrip("/").rsplit("/", 1)[-1]
        if not base:
            continue
        if any(ch in base for ch in "*?["):
            if base.startswith(".") and any(fnmatch.fnmatchcase(c, base.lower()) for c in ENV_GLOB_CANDIDATES):
                return base
            continue
        if ENV_BASE_RE.match(base) and base.rsplit(".", 1)[-1].lower() not in ENV_TEMPLATE_SUFFIXES:
            return base
    return None


def rule3_env(name, args, cmd):
    instead = (
        "Real env files hold secrets and are the owner's. Read .env.example for the "
        "variable names, or ask the repo owner. Do not print values."
    )
    out = []
    if name and name not in ENV_NONPRINTING:
        for a in args:
            hit = real_env_name(a)
            if hit:
                out.append(Violation(3, f'{name} {hit}  (only the file name is quoted)', instead))
                break
    for kind, targets in (("write to", cmd.outs), ("read from", cmd.ins)):
        for t in targets:
            hit = real_env_name(t)
            if hit:
                out.append(Violation(3, f'redirection: {kind} {hit}  (only the file name is quoted)', instead))
    return out


# --------------------------------------------------------------------------
# Rule 4: recursive rm outside the repo.
# --------------------------------------------------------------------------


def rule4_rm(name, args, cwd):
    if name != "rm":
        return []
    recursive, targets, after_dd = False, [], False
    for a in args:
        if after_dd or not a.startswith("-") or a == "-":
            targets.append(a)
        elif a == "--":
            after_dd = True
        elif a.startswith("--"):
            recursive = recursive or a == "--recursive"
        elif "r" in a[1:] or "R" in a[1:]:
            recursive = True
    if not recursive:
        return []
    root = canon_path(str(REPO_ROOT), None)
    shown = show(["rm"] + args)
    instead = (
        "Recursive rm is only allowed on targets inside the repo "
        f"({REPO_ROOT.name}); name each target explicitly as a relative path inside it, "
        "or ask the repo owner."
    )
    if not targets:
        return [Violation(4, shown + "  (no explicit target: it may come from another command)", instead)]
    out = []
    for t in targets:
        why = None
        if SUB in t or "$" in t or "`" in t:
            why = f"target {t.replace(SUB, '$(...)')!r} contains a variable or command substitution that cannot be resolved"
        elif "{" in t:
            why = f"target {t!r} contains brace expansion that cannot be resolved"
        else:
            expanded = os.path.expanduser(t) if t == "~" or t.startswith(("~/", "~\\")) else t
            if expanded.startswith("~"):
                why = f"target {t!r} refers to another user's home"
            else:
                resolved = canon_path(expanded, cwd)
                if resolved is None or root is None:
                    why = f"target {t!r} cannot be resolved"
                elif resolved == root:
                    why = f"target {t!r} is the repo root itself"
                elif not resolved.startswith(root + "/"):
                    why = f"target {t!r} resolves outside the repo ({resolved})"
        if why:
            out.append(Violation(4, f"{shown}  ({why})", instead))
    return out


# --------------------------------------------------------------------------
# Rule 5: the Render deploy hook.
# --------------------------------------------------------------------------

HTTP_TOOLS = {"curl", "wget", "invoke-webrequest", "iwr", "invoke-restmethod", "irm"}
DEPLOY_URL_RE = re.compile(r"(?<![a-z0-9])render\.com/deploy", re.I)
DEPLOY_VAR_RE = re.compile(r"RENDER_DEPLOY_HOOK_URL", re.I)


def rule5_render(name, args):
    if name not in HTTP_TOOLS:
        return []
    joined = to_slashes(" ".join(args))
    what = None
    if DEPLOY_URL_RE.search(joined):
        what = "a render.com/deploy URL"
    elif DEPLOY_VAR_RE.search(joined):
        what = "RENDER_DEPLOY_HOOK_URL"
    if not what:
        return []
    return [
        Violation(
            5,
            f"{name} with {what}  (the URL is a secret and is not echoed)",
            "Deploys are CI's job, see docs/release-process.md: push to main and the "
            "deploy job calls the hook after a green run. A manual redeploy is the "
            "repo owner's, from the Render dashboard.",
        )
    ]


# --------------------------------------------------------------------------
# Driver.
# --------------------------------------------------------------------------


def check_command(command, cwd):
    """Return (violations, parsed_ok)."""
    parsed_ok = True
    try:
        commands = parse_commands(command)
    except ParseError:
        parsed_ok = False
        commands = parse_commands_raw(command)
    violations = []
    for cmd in commands:
        name, args = split_command(cmd.words)
        if name == "git":
            violations += rule1_git_push(args)
        violations += rule2_local(name, args, cmd)
        violations += rule3_env(name, args, cmd)
        violations += rule4_rm(name, args, cwd)
        violations += rule5_render(name, args)
    return violations, parsed_ok


def format_denial(violations, parsed_ok):
    lines = []
    for v in violations:
        lines.append(f"pinpoint guard: BLOCKED by {RULE_NAMES[v.rule]}.")
        lines.append(f"  Offending part: {v.quoted}")
        lines.append(f"  Instead: {v.instead}")
    lines.append("  See agent-hooks/README.md and docs/permissions.md. This is a guardrail against accidents, not a security boundary.")
    if not parsed_ok:
        lines.append("  (The command could not be parsed, so it was matched on its raw text.)")
    return "\n".join(lines)


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("stdin JSON is not an object")
        tool = data.get("tool_name")
        if not isinstance(tool, str):
            raise ValueError("no tool_name in the hook input")
        if tool != "Bash":
            return 0
        tool_input = data.get("tool_input")
        command = tool_input.get("command") if isinstance(tool_input, dict) else None
        if not isinstance(command, str):
            raise ValueError("no tool_input.command in the hook input")
        cwd = data.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            cwd = os.getcwd()
        violations, parsed_ok = check_command(command, cwd)
    except Exception as exc:  # fail-open: never exit 2 for an internal problem
        msg = f"{type(exc).__name__}: {exc}".replace("\n", " ")[:200]
        print(f"pinpoint guard: internal problem ({msg}); this command was NOT checked.", file=sys.stderr)
        return 1
    if violations:
        print(format_denial(violations, parsed_ok), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
