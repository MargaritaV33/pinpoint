# Semgrep scan report

Issue #26, rubric criterion 13. Date of the scan: 2026-10-14. Audited commit:
`586936d85bdd116b50a6cbef1427cfbeebd976be` (the commit that added the `security`
CI job; the scanned tree is the tracked-file export of that commit). Raw
output: [`semgrep.json`](semgrep.json). Dependency audits:
[`dependency-audit.md`](dependency-audit.md).

Why Semgrep exists here: criterion 13 asks for deterministic scanning. It is a
scanner run from a pinned Docker image (locally) and from the same image in CI;
it is not part of the product's dependency graph (nothing was added to
`backend/pyproject.toml` or `frontend/package.json`). The image is a
third-party container that sees the files it scans, which is why only a clean
export of the tracked files is ever mounted (see "How to reproduce").

## Result in one paragraph

232 files scanned with 298 rules (602 loaded) from the four rulesets
`p/python`, `p/typescript`, `p/secrets`, `p/owasp-top-ten`: **19 findings: 1
ERROR, 2 MEDIUM, 16 WARNING; 0 from `p/secrets`; 0 in application code**
(backend, frontend, mcp-server, e2e and integration tests are all scanned).
All 19 are in CI configuration, the `Dockerfile` and two `pyproject.toml`
files. None is fixed in this issue; all are accepted with a reason, and the
real ERROR is tracked in #30. Semgrep labels the two
`uv-missing-dependency-cooldown` rows `MEDIUM`, not WARNING; neither is `ERROR`,
so neither gates.

## Re-run at the end of issue #26

After the application fixes, the audits and the other four documents were
committed, the scan was run again on an export of commit `d147808` (the last
commit before this paragraph): **the same 19 findings** (same rule, file and
line, compared programmatically), 238 files scanned (232 plus the six files of
`security/`), and the exact CI gate command exited **0**. The committed
`semgrep.json` is therefore still the current result; the fixes of this issue
did not touch a line any finding points at.

## How to reproduce

Pinned image: `semgrep/semgrep:1.180.0` (digest
`sha256:529ee8a277ec8adc5b534d7c74eea0a47e9de21d62852b6ba7ac6ba9566845c3` on
2026-10-14; never `latest`). Flags: `--metrics=off --disable-version-check`.
Metrics stayed off the whole time: the registry rulesets load fine with
metrics off, so the fallback to local ruleset files was not needed.

**The scanner never reads `.env` or `_local/`.** Mechanism: scan a clean export
of the tracked files only (`git archive` of `HEAD`, written to a tar file first
and extracted into a scratch directory outside the repository), mounted
**read-only** (`:ro`), with a separate writable mount only for the output file.
Untracked and ignored files (`.env`, `_local/`, `node_modules`,
`backend/pinpoint.db`) are never in that directory. On top of that `--exclude`
names them explicitly.

One deviation from the usual exclude list: `.env.*` is **not** excluded,
because `.env.example` is tracked, public, and meant to be scanned (it is where
a secret would be pasted by mistake). Excluded instead: `.env`, `.env.local`,
`.env.*.local`. So the path check below allows `.env.example` and nothing else
starting with `.env`.

### Git Bash

```bash
S=/path/outside/the/repo/scratch            # any scratch directory
mkdir -p "$S/src" "$S/out"
git archive --format=tar -o "$S/tracked.tar" HEAD   # file first, no pipe
(cd "$S/src" && tar -xf ../tracked.tar)
# MSYS_NO_PATHCONV=1 stops Git Bash from rewriting /src into C:/Program Files/Git/src
MSYS_NO_PATHCONV=1 docker run --rm -v "$S/src:/src:ro" -v "$S/out:/out" -w /src \
  semgrep/semgrep:1.180.0 semgrep scan --metrics=off --disable-version-check \
  --config p/python --config p/typescript --config p/secrets --config p/owasp-top-ten \
  --exclude .env --exclude .env.local --exclude '.env.*.local' --exclude _local \
  --exclude node_modules --exclude .venv --exclude dist --exclude .output --exclude '*.db' \
  --json --output /out/semgrep.json .
```

(`//src`-style container paths are the alternative to `MSYS_NO_PATHCONV=1`; use
one of the two, otherwise Git Bash rewrites the container path.)

### PowerShell (Windows PowerShell 5.1)

The repository path contains a space (`Pinpoint_AI Dev Tools`), hence the
double-quoted `-v` arguments. `git archive` writes to a file (`-o`) first:
piping it into `tar` in PowerShell 5.1 corrupts binary data.

```powershell
$s = "$env:TEMP\pinpoint-semgrep"
New-Item -ItemType Directory -Force "$s\src", "$s\out" | Out-Null
git archive --format=tar -o "$s\tracked.tar" HEAD
tar -xf "$s\tracked.tar" -C "$s\src"
docker run --rm -v "${s}\src:/src:ro" -v "${s}\out:/out" -w /src `
  semgrep/semgrep:1.180.0 semgrep scan --metrics=off --disable-version-check `
  --config p/python --config p/typescript --config p/secrets --config p/owasp-top-ten `
  --exclude .env --exclude .env.local --exclude '.env.*.local' --exclude _local `
  --exclude node_modules --exclude .venv --exclude dist --exclude .output --exclude '*.db' `
  --json --output /out/semgrep.json .
```

Both forms were run on 2026-10-14 against the same commit and gave the same
result (19 findings, 232 files). The committed `semgrep.json` comes from the
Git Bash run. The brief's original one-liner (`-v "${PWD}:/src"` with the output
written into the mounted repository) is not used: it is read-write on the
repository and PowerShell-only.

`.semgrepignore` (repository root) lists `*.jpg` and `*.ico` only: the seed
images, the e2e render fixture and the favicon, 8 binary files that no text
rule can match. Without any `.semgrepignore`, Semgrep falls back to built-in
default patterns that skip every `tests/` directory; the file exists so that
tests, e2e and integration code are scanned too.

### The same scan in CI

`.github/workflows/ci.yml`, job `security` (`runs-on: ubuntu-latest`,
`permissions: contents: read`, no `needs`, `container: image:
semgrep/semgrep:1.180.0`) runs the identical `--config` list and `--exclude`
list in two steps:

1. report: all severities, no `--error`; writes the JSON to `$RUNNER_TEMP`
   (outside the checkout, so the gate cannot scan it) and uploads it with
   `actions/upload-artifact@v4` under `if: always()`;
2. gate: the same command plus `--severity ERROR --error --exclude-rule
   dockerfile.security.missing-user.missing-user`.

There is no `|| true` and no `continue-on-error`: if the registry or the network
is down, Semgrep exits 2 and the job is red.

Limitation: the registry rulesets are fetched when the job runs and are **not
pinned by the image tag**. A rule update can turn a green tree red without any
code change. The `security` job is therefore not in `deploy.needs` (still
`[stack]`); whether it should gate the deploy is the owner's decision, tracked
in #27. Nothing in this repository enforces that a red `security` job is looked
at.

## What "new finding" means (decided once)

A finding fails the build unless it is **fixed** or **suppressed inline at its
line** with `# nosemgrep: <rule-id>` (`// nosemgrep: <rule-id>` in TypeScript),
with the reason in a normal comment on the line above (the text after the rule
id is not reliably parsed). There is **no baseline file** and no
`--baseline-commit`: both would hide pre-existing findings without a trace in
the code. Only ERROR fails the build; WARNING, INFO and the `MEDIUM` rows are
reported in the artifact and in the table below.

Consequence for `nosemgrep` markers: they belong on accepted or false-positive
**ERROR** rows. There is exactly one ERROR row (F17) and it cannot carry one
(see below), so `git grep -n nosemgrep -- ':!security' ':!.github'` returns
**0 markers** in tracked code (count: 0). The word also appears in this report
and in the `ci.yml` comments, where it describes the rule.

**One deviation, stated plainly.** F17 is a real ERROR on the `Dockerfile`. The
inline marker is the documented mechanism, but issue #26 forbids editing the
`Dockerfile`, and a `.semgrepignore` entry is limited to files nobody should
scan. So the gate step carries `--exclude-rule
dockerfile.security.missing-user.missing-user` (one rule id, nothing else), the
report step does not, and #30 removes the exclusion together with the fix. This
is the only check the gate does not make.

## Findings

All 19 results of `semgrep.json` (`jq '.results | length' semgrep.json` is 19;
this table has 19 rows). Short rule names stand for these full ids:
`yaml.github-actions.security.github-actions-mutable-action-tag.github-actions-mutable-action-tag`,
`dockerfile.security.missing-user.missing-user`,
`package_managers.uv.uv-missing-dependency-cooldown.uv-missing-dependency-cooldown`.
Matched code is not in the JSON: Semgrep OSS writes `requires login` into
`extra.lines` for registry rules.

| Id | Rule | Where | Severity | Disposition |
|---|---|---|---|---|
| F1 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:34` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F2 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:36` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F3 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:40` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F4 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:54` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F5 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:56` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F6 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:78` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F7 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:80` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F8 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:107` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F9 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:121` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F10 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:135` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F11 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:137` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F12 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:141` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F13 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:159` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F14 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:161` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F15 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:210` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F16 | `github-actions-mutable-action-tag` | `.github/workflows/ci.yml:222` | WARNING | accepted: WARNING, report-only. Tag-pinned actions are the repo's existing convention; SHA pinning needs an update mechanism, tracked in #31 |
| F17 | `missing-user` | `Dockerfile:61` | ERROR | accepted (ERROR, real): the container runs as root. The Dockerfile is outside the whitelist of #26, so neither a fix nor an inline `nosemgrep` is possible here; tracked in #30. Excluded from the CI gate by rule id until #30 lands |
| F18 | `uv-missing-dependency-cooldown` | `backend/pyproject.toml:24` | MEDIUM | accepted: supply-chain hardening, not a defect. Installs use `uv sync --frozen` against hashes in `uv.lock`, so a new upstream release is never picked up without an explicit `uv lock`; the cooldown would only matter then. File is on the do-not-touch list |
| F19 | `uv-missing-dependency-cooldown` | `integration/pyproject.toml:11` | MEDIUM | accepted: supply-chain hardening, not a defect. Installs use `uv sync --frozen` against hashes in `uv.lock`, so a new upstream release is never picked up without an explicit `uv lock`; the cooldown would only matter then. File is on the do-not-touch list |

Fixed in this issue: none of these. Application fixes made in this issue come
from the review in [`pr-audit.md`](pr-audit.md), not from Semgrep.

## Candidates the task expected, and what happened

Semgrep reported nothing for any of these; each was checked by hand and
`semgrep.json` therefore has no row for them. They are not "clean because
unscanned": all of them are in the scanned file list.

- `.env.example` (scanned; only placeholders. `JWT_SECRET=local-development-secret-change-me`
  is the documented public default, see `pr-audit.md`).
- `docker-compose.yaml` defaults (`POSTGRES_PASSWORD:-pinpoint`, the JWT default
  secret): local-development defaults, documented in `.env.example`; production
  gets its secret from `render.yaml`.
- Test fixtures and the demo password (`backend/app/seed.py`, `DEMO_PASSWORD`,
  published in `README.md`): documented demo data, no real credential.
- `frontend/src/components/ui/chart.tsx:73` `dangerouslySetInnerHTML`: not
  reported by the four rulesets. Checked: it injects a `<style>` block built only
  from the developer-supplied chart `config` (colour strings), never from user
  or server data, and nothing imports the component (`grep -rn "ui/chart"
  frontend/src` has no importer). Accepted, unused generated UI component.

## Errors and skipped files

- `errors` in `semgrep.json`: 1 entry, level `warn`, type `PartialParsing`.
  Rule `gha-curl-pipe-shell` parses shell snippets of workflow `run:` steps with
  its Bash parser and cannot parse GitHub's `${{ github.sha }}` expression in the
  `deploy` job's script (`ci.yml:246`). Only that one rule's check of that one
  snippet is incomplete; the rest of the file was scanned. No file was skipped
  for a parse error or a timeout.
- `paths.skipped` is absent from the JSON (Semgrep writes it only with
  `--verbose`). The skipped set is known: the 8 binary files matched by
  `.semgrepignore`. Tracked files total 240; scanned 232; 240 - 232 = 8.
- Path check, run on the committed JSON: no scanned path starts with `_local/`,
  `node_modules/` or `.venv/`, none ends in `.db`, and the only path starting
  with `.env` is `.env.example`.

## Not covered by these rulesets

Not implied to be clean:

- `docker-compose.yaml`, `render.yaml` (only generic and YAML rules ran; no
  rule for compose or Render blueprints is in these four rulesets).
- `Dockerfile`: only 4 Dockerfile rules ran (F17 came from them); no
  `p/dockerfile`.
- `.github/workflows/ci.yml`: the four rulesets include a handful of GitHub
  Actions rules (F1 to F16), not `p/github-actions` as a whole.
- Shell scripts (`scripts/*.sh`, `agent-hooks/run.sh`) beyond one Bash rule,
  Markdown, authorization logic, business logic.
- Extra rulesets (`p/dockerfile`, `p/github-actions`) were deliberately not
  added (owner-question default for issue #26).
- Dependencies: not Semgrep's job; see `dependency-audit.md`.

## Secret and path check of the committed outputs

Run on 2026-10-14 over every committed output in `security/` (the bracketed
forms keep the patterns from matching their own text in this file):

```bash
grep -nE 'render[.]com/deploy|RENDER_DEPLOY_HOOK_URL[=]|[e]yJ|BEGIN [A-Z ]*PRIVATE KEY|postgres(ql)?(\+psycopg)?://[^ ]*:[^ @]+@' semgrep.json semgrep-report.md dependency-audit.md pr-audit.md
grep -nE 'C:\Users|/[c]/Users|[/]Users[/]' semgrep.json semgrep-report.md dependency-audit.md pr-audit.md
```

Result: no output from either command (grep exit status 1 = no match), over every
file in `security/` (the JSON, the five documents and the helper script),
re-run after the last edit of those files.

Redaction of `p/secrets` matched text: **not needed**, and not done. There were
0 `p/secrets` findings, and every `extra.lines` value in the JSON is the literal
string `requires login`, so no matched source text is stored at all. The check
that confirmed it:
`python -c "import json;d=json.load(open('semgrep.json'));print({r['extra']['lines'] for r in d['results']})"`
prints `{'requires login'}`. The check is on the outputs; an agent cannot read
the real `.env` (hook rule 3 in `docs/permissions.md`), so there was no
comparison with it.

## The gate, proven in both directions

Run locally on 2026-10-14 with the exact gate command of the `security` job
(Git Bash form of the docker command above, plus `--severity ERROR --error
--exclude-rule dockerfile.security.missing-user.missing-user`).

| Tree | Result | Exit code |
|---|---|---|
| Export of the committed tree (`586936d`) | 0 findings (126 rules, 232 files) | **0** |
| Same export without the `--exclude-rule` | 1 finding: F17 | **1** |
| Scratch copy (outside the repository) with a flagged snippet added: `jwt.decode(token, options={"verify_signature": False})` in a new `backend/app/flagged_snippet.py`. Registry rule `python.jwt.security.unverified-jwt-decode.unverified-jwt-decode`, severity ERROR | 1 finding | **1** |
| Same scratch copy with `# nosemgrep: python.jwt.security.unverified-jwt-decode.unverified-jwt-decode` on that line and the reason in the comment above | 0 findings | **0** |

The scratch copy was a plain directory copy of the export; the repository was
never modified for this test and no red commit exists. The CI side of the proof
(the `security` job green on the `main` run) is checked after the push and is
recorded in the issue comments, not here.
