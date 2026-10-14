# AI code-review audit of a real change

Issue #26, rubric criterion 13.

## What was audited, and what was not

**This is a commit-range audit. No pull request exists**: all work in this
repository was pushed straight to `main`, and `main` is not protected (see
[`ai-tool-and-data-policy.md`](ai-tool-and-data-policy.md), "Review before
merge").

**Issue #16 is not the audited change.** Its commits are `e80988c` (sign-up
toggle in the login screen), `c15f635` (authenticated image fetch in the
frontend client), `400a48a` (a frontend README note) and `02cf7c2` (a usage-log
entry): frontend and documentation only, with no server-side auth, image
serving or upload code. The server-side code a security review of "auth, image
serving and uploads" needs was introduced by issue #4, commit **`220f89a`**
("Implement backend from the contract with an in-memory store"), so that is
the audited change, together with the client side of #16 and the stored-session
table of `6ef381a` (#6).

Audited, by reading the code as it is in each commit (`git show <commit>:<path>`):

| Commit | Files |
|---|---|
| `220f89a` | `backend/app/auth/dependencies.py`, `auth/hashing.py`, `auth/jwt.py`, `routers/auth.py`, `routers/guest.py`, `routers/images.py`, `routers/rooms.py`, `config.py`, `main.py` (CORS), `ids.py`, `serializers.py` (`image_file_response`), plus `seed.py` and `pyproject.toml` lines named below |
| `6ef381a` | `backend/app/store/sqlalchemy/models.py` (the `sessions` table) |
| `e80988c` | `frontend/src/routes/login.tsx`, `frontend/src/lib/auth-form.ts` |
| `c15f635` | `frontend/src/lib/api/http.ts`, `frontend/src/components/pinpoint/useImageSrc.ts` |
| `1d8418d` | `backend/app/main.py`, the SPA fallback only (for the "found fine" list) |

**Produced by an AI reviewer**: Claude Code, running as the Engineer subagent
of this repository's process (`_docs/process.md`), model `claude-sonnet-5-5`.
The findings are the reviewer's reading plus a few local experiments (named
where used); they were not independently confirmed by a human. The severities
are the reviewer's own ratings, not CVSS scores.

**Not reviewed**: everything outside the table above. In particular the
studio pin routes (`routers/pins.py`), the stores' query code
(`store/memory.py`, `store/sqlalchemy/db_store.py`), `export.py`, the Pydantic
schemas, the Dockerfile and Compose file (Semgrep only, see
[`semgrep-report.md`](semgrep-report.md)), the MCP server, the rest of the
frontend, and the live production service. No dynamic testing against
production was done; local experiments ran against the test suite's in-memory
database. A passing audit of these files says nothing about the rest.

Line numbers below are written `commit:path:line` and refer to that commit's
version of the file. Fix commits are on `main`; test names are in `backend/tests/`.

## Result

16 findings: 0 Critical, 0 High, 3 Medium, 9 Low, 4 Info. Fixed in this issue:
1 Medium and 3 Low (one of them, A-6, only for new rooms). The other two Medium
findings, and the Low findings that need a schema, contract or product
decision, have follow-up issues. **Three Medium and nine Low findings are real,
more than a handful; the cluster is "nothing limits abuse of the unauthenticated
and login surfaces" (A-3, A-4, A-5, A-9, A-11), which is why it is split into
issues instead of patched piecemeal here.** No finding is Critical or High, so
there is nothing in this public file that has to be withheld; none is described
with a working exploit.

## Findings

Severity: Critical, High, Medium, Low, Info, each with a one-line impact.
Disposition: **fixed** (commit and test), **accepted** (reason) or **false
positive** (reason). Real findings that are not fixed link their follow-up by
number.

| Id | Severity and impact | Where | What the code does | Disposition |
|---|---|---|---|---|
| A-1 | **Medium.** A shared cache (proxy, CDN) may store an authenticated response and replay a client's render without the token. | `220f89a:backend/app/serializers.py:86`, used by the studio route at `220f89a:backend/app/routers/images.py:93` | `image_file_response` sends `Cache-Control: public, max-age=86400` for every image, including the studio route that requires a bearer token. RFC 9111 allows a shared cache to store a response to an `Authorization` request only when it says `public`, so the header explicitly permitted it. Whether Render puts a shared cache in front of the service was not checked. | **fixed** in `77264ac` (contract first in `f580916`): studio route is `private`, guest route unchanged. Tests `test_studio_image_file_is_private_not_public` (fails before), `test_guest_image_file_stays_cacheable` (pins unchanged behaviour). |
| A-2 | **Medium.** A copy of the database holds live bearer tokens for up to 60 minutes; the table grows with every login and is never trimmed. | `6ef381a:backend/app/store/sqlalchemy/models.py:34` (token is the primary key), `220f89a:backend/app/routers/auth.py:19-22` (`_start_session` stores the raw JWT) | The `sessions` row key is the JWT itself. The only deletion is `220f89a:backend/app/routers/auth.py:53` (logout). Expired tokens fail signature/expiry checks (`jwt.py:34`) but their rows stay. | **accepted for now, follow-up #33** (needs a storage and schema decision; there is no migration tool). |
| A-3 | **Medium.** Passwords of studio accounts, including the known demo account, can be guessed without limit. | `220f89a:backend/app/routers/auth.py:41-48` (login), `:25-38` (signup) | No attempt counter, delay, lockout or rate limit on either route. | **accepted for now, follow-up #32.** |
| A-4 | Low. Very weak passwords are accepted. | `220f89a:backend/app/routers/auth.py:30` | The only password rule is "not empty". | **accepted for now, follow-up #32** (needs a contract change and a decision about seeded and test passwords). |
| A-5 | Low. Which emails have an account can be learned: by the `409` at sign-up, and by timing at login. | `220f89a:backend/app/routers/auth.py:32-33` (409), `:43-45` (login returns 401 for an unknown email before any hash is computed) | Sign-up says the address is taken; login skips `verify_password` when the user does not exist, so that answer is faster. | **accepted** (the `409` is a product behaviour the sign-up form shows, `e80988c:frontend/src/lib/auth-form.ts:34`); the timing difference and the recorded decision are in **#32**. |
| A-6 | Low. The guest token is the only credential on a share link and had 48 random bits (about 2.8e14 values); online guessing is impractical but nothing slows it (A-3). | `220f89a:backend/app/ids.py:11`, `220f89a:backend/app/routers/rooms.py:57` | `new_id("g")` is `g_` plus `uuid4().hex[:12]`. | **fixed for new rooms** in `dd7b025`: `g_` plus `secrets.token_urlsafe(16)` (128 bits). Test `test_create_room_guest_token_has_at_least_128_bits` (fails before). **Not fixed for rooms that already exist**: their tokens keep the old length, and there is no rotate endpoint; the seeded demo tokens are unchanged on purpose (A-16). |
| A-7 | Low. If `JWT_SECRET` were missing in production the app would sign tokens with a secret everyone can read. The impact is bounded: a forged token is rejected because it has no `sessions` row. | `220f89a:backend/app/config.py:21` (default), `:25` (`environment`, not read anywhere), `220f89a:backend/app/auth/jwt.py:14,28` (HS256), `:34` | The default secret is accepted in every environment. Tokens are HS256 and last 60 minutes (`config.py:22`). `render.yaml` generates a real secret and sets `ENVIRONMENT=production`. | **fixed** in `6639bdd`: startup fails when `ENVIRONMENT=production` and the secret is still the default. Tests in `backend/tests/test_config.py` (`test_production_with_default_jwt_secret_refuses_to_start` fails before). The mitigating session check is pinned by `test_validly_signed_token_without_a_session_row_is_rejected` (`0d0a6e3`). The production secret itself could not be checked (no access). |
| A-8 | Low. A file is accepted on the client's word that it is a JPEG or PNG. | `220f89a:backend/app/routers/images.py:43-45` | Only the `Content-Type` header is checked against an allow-list; the bytes are never sniffed. Impact is limited: the stored type is one of two image types and the response now carries `nosniff` (A-10). | **accepted for now, follow-up #34** (checking bytes breaks the placeholder uploads in `integration/` and needs a contract change). |
| A-9 | Low. An authenticated user can make the server read an arbitrarily large upload before it is rejected. | `220f89a:backend/app/routers/images.py:47-49` | `await file.read()` first, `413` after. The multipart parser is expected to spool large bodies to a temporary file (not verified in this audit), which would bound memory but not disk or time. | **accepted for now, follow-up #34.** |
| A-10 | Low. A browser could reinterpret served bytes as another type. | `220f89a:backend/app/serializers.py:83-87` | No `X-Content-Type-Options` header on image responses. | **fixed** in `77264ac`: `nosniff` on both image routes. Test `test_image_files_are_served_with_nosniff` (fails before). |
| A-11 | Low. Anyone holding a guest link can store arbitrarily long names and comments, with no rate limit. | `220f89a:backend/app/routers/guest.py:61-66` (pin), `:115-120` (comment) | The text fields are stripped and checked for emptiness only. | **accepted for now, follow-up #34.** |
| A-12 | Low. Page JavaScript can read the studio token, so any future script injection would also steal sessions. No injection point was found in the audited files. | `c15f635:frontend/src/lib/api/http.ts:4,23,55,60` | The bearer token lives in `localStorage` under `pinpoint.token`. | **accepted, follow-up #35** (an owner decision: cookie sessions change the contract and the MCP server's login). |
| A-13 | Info. The client attaches the studio bearer token to whichever URL it is asked to fetch. | `c15f635:frontend/src/lib/api/http.ts:99-101` | `getImageObjectUrl(url)` sends `Authorization` to `url`. The value comes from the server's `RenderImage.url`, which is a relative path the client prefixes with its own base URL (`:13-15`); no user-controlled value reaches it. | **accepted** (no path from user input; revisit if the server ever returns absolute URLs). |
| A-14 | Info. CORS is credentialed with wildcard methods and headers. | `220f89a:backend/app/main.py:14-20` | `allow_origins` is the explicit list from `CORS_ORIGINS` (default: two localhost origins, also in production because `render.yaml` does not set it), `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`. Auth uses a bearer header, not cookies, so credentials mode is unnecessary but not exploitable, and the deployment is same-origin. | **accepted.** Would become a real finding only if `CORS_ORIGINS` were set to `*` or a hostile origin. |
| A-15 | Info. Password hashing uses `passlib` with `bcrypt` held below 4.1. | `220f89a:backend/pyproject.toml:7,9`, `220f89a:backend/app/auth/hashing.py:7` | The pin exists because bcrypt 5.0 broke passlib 1.7.4's self-test (`docs/ai-usage-report.md`, issue #4 entry). `pip-audit` reports no advisory for either ([`dependency-audit.md`](dependency-audit.md)). | **accepted**; a scheduled audit (#29) is what would notice a future advisory. |
| A-16 | Info. Production runs a documented demo account and two well-known guest links, writable by anyone. | `220f89a:backend/app/seed.py:15` (password), `:88`, `:99` (`lakeside-demo`, `atrium-demo`); `README.md` "Live demo" | The seed runs whenever the database is empty. Anyone can sign in as the demo user, create rooms and upload images in production, and anyone can post on the two demo rooms. | **accepted** (owner default for this issue: documented demo data, no real client data). Switching the production seed off would be a separate issue; the abuse surface is bounded only by A-3, A-9 and A-11. |

No finding is a **false positive**. The Semgrep results are triaged in
[`semgrep-report.md`](semgrep-report.md); none overlaps with the table above.

## Checked and found fine

Each of these was read in the cited commit; where a test pins the behaviour it
is named.

- **Studio ownership checks.** Every studio room route resolves the room through
  `store.get_room_owned(room_id, user.id)` and answers `404` for someone else's
  room, so existence is not leaked: `220f89a:backend/app/routers/rooms.py:23-27,70,80,91`,
  `images.py:33,71-72,87-92`. Tests: `test_get_room_cross_owner_is_404`,
  `test_upload_image_cross_owner_is_404`, `test_get_room_image_file_cross_room_is_404`.
- **Guest token scoping.** `get_guest_room` turns an unknown token into `404`
  (`220f89a:backend/app/auth/dependencies.py:56-63`), and the guest routes check
  that the image or pin belongs to that token's room
  (`guest.py:55,112,163`). Tests: `test_add_guest_comment_cross_room_token_is_404`,
  `test_get_guest_image_file_cross_room_token_is_404`.
- **JWT handling.** The algorithm is pinned on decode (`jwt.py:34`, no `alg`
  confusion), `exp` is always set (`jwt.py:26`), `sub` is validated
  (`jwt.py:37-39`), and a token must also match an active session row
  (`dependencies.py:36-39`, again in `get_current_user`, `:48-50`), so logout
  really revokes (`auth.py:53`; test `test_logout_invalidates_the_token`).
- **No password hash in responses.** `StudioUser` carries id, email and name
  only (`dependencies.py:53`, `auth.py:38,48`).
- **Upload guards that do exist.** Allow-list of two types (`images.py:22,43-45`),
  size cap (`:47-49`), closed rooms refuse uploads (`:36`).
- **SPA fallback path guard.** The requested path is resolved and must stay
  inside the build directory: `1d8418d:backend/app/main.py:78-80`
  (`candidate.is_relative_to(dist_root)`). It had no test; `41bbcc8` adds three
  encoded-traversal tests that fail when the condition is removed.
- **Frontend rendering.** Server error text is rendered as a React text node
  (`e80988c:frontend/src/routes/login.tsx:86`), not as HTML; object URLs created
  for images are revoked on change and unmount
  (`c15f635:frontend/src/components/pinpoint/useImageSrc.ts:37`). The only
  `dangerouslySetInnerHTML` in the repository is in an unused generated UI
  component (`semgrep-report.md`).

## What this audit does not claim

- It does not say the application is secure. It says what a reader of these
  files found, with the ratings above.
- It does not cover how the findings behave on the live service.
- Fixes change production behaviour at the next deploy (image headers, new
  guest tokens, startup check); they were verified only by the backend test
  suite and the contract test, plus the CI and `/health` checks recorded in the
  issue comments.
