"""Turn backend/uv.lock into a pinned requirements file for pip-audit.

Why this exists: `uv` is not available on every dev machine, and pip-audit may
not add anything to backend/pyproject.toml or backend/uv.lock. The lock file is
plain TOML, so the runtime dependency closure (what `uv sync --frozen --no-dev`
installs in the Dockerfile) can be computed with the standard library alone.

Usage:  python -I security/lock_to_requirements.py [--all] [backend/uv.lock]

Default output: `name==version` for every package reachable from the project's
non-dev dependencies (extras followed). `--all` prints every locked package,
marking the dev-only ones with a trailing `# dev-only` comment.

Environment markers are ignored on purpose: the closure is a superset of what
any one platform installs (for example `colorama` on Windows), never a subset.
"""

import sys
import tomllib
from pathlib import Path


def load(path: Path) -> dict[str, dict]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return {p["name"]: p for p in data["package"]}


def closure(pkgs: dict[str, dict], roots: list[dict]) -> set[str]:
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        dep = stack.pop()
        name = dep["name"]
        pkg = pkgs[name]
        # The same package can be reached with and without extras, so extras
        # are expanded every time instead of once per package name.
        for extra in dep.get("extra", []):
            stack.extend(pkg.get("optional-dependencies", {}).get(extra, []))
        if name in seen:
            continue
        seen.add(name)
        stack.extend(pkg.get("dependencies", []))
    return seen


def main(argv: list[str]) -> int:
    show_all = "--all" in argv
    args = [a for a in argv if a != "--all"]
    lock = Path(args[0]) if args else Path("backend/uv.lock")
    pkgs = load(lock)
    roots = [p for p in pkgs.values() if p.get("source", {}).get("virtual") == "."]
    if len(roots) != 1:
        print("expected exactly one virtual root package", file=sys.stderr)
        return 1
    root = roots[0]
    runtime = closure(pkgs, root.get("dependencies", []))
    dev_roots = [d for group in root.get("dev-dependencies", {}).values() for d in group]
    everything = runtime | closure(pkgs, dev_roots)
    names = sorted(everything if show_all else runtime)
    for name in names:
        suffix = "  # dev-only" if show_all and name not in runtime else ""
        print(f"{name}=={pkgs[name]['version']}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
