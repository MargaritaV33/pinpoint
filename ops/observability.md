# Observability

What the backend records about its own traffic, and what it does not. Code:
`backend/app/access_log.py`, wired in `backend/app/main.py`. Tests:
`backend/tests/test_access_log.py`. The header is part of the contract
(`openapi.yaml`: `components/headers/XRequestId`). Where to look when
production misbehaves: [`runbook.md`](runbook.md).

## What exists

### One JSON access-log line per request

Written to **stdout** with the standard library `logging` module and a small
JSON formatter (no extra dependency). One object per line:

```json
{"ts":"2026-10-15T07:03:10.123Z","level":"INFO","request_id":"6a1bb916dd6749caa0c931db57be49fc","method":"GET","path":"/guest/{guestToken}","status":200,"duration_ms":28.118}
```

| Field | Type | Meaning |
|---|---|---|
| `ts` | string | UTC, ISO 8601, millisecond precision, ends in `Z` |
| `level` | string | `INFO`, or `ERROR` when `status` is 500 or above |
| `request_id` | string | the request id (below) |
| `method` | string | HTTP method |
| `path` | string | the **route template**, e.g. `/rooms/{roomId}`, or `unmatched` |
| `status` | integer | HTTP status sent; `0` if the client went away before any response |
| `duration_ms` | number | time spent in the app, at most 3 decimals |

`path` is the template, never the concrete URL, because guest and share tokens
are path segments (`/guest/{guestToken}/...`). When no route matched, or only
the single-page-app catch-all did (an unknown URL, a static file, a deep link
into the frontend), `path` is the fixed word `unmatched`: an unmatched path is
whatever the client typed or pasted and can contain a token.

**Never logged:** the query string, any request or response header (so no
`Authorization` and no cookies), any request or response body, any user id or
e-mail. A test asserts that a guest request with a token and `?token=...`, and
a studio request with a bearer token, leave neither value in the output.

The line carries no stack trace. For an unhandled exception the access line
says `status: 500`, `level: ERROR`, and the traceback goes to uvicorn's normal
error log, on stderr, next to it.

uvicorn's own access log is switched off in the app: it prints the concrete URL
with the query string (so, the guest token), which would undo the above.

### Request id

- Every response carries `X-Request-Id`: `200`, `404`, `405`, `422`, `500`,
  CORS preflights, static files and the frontend fallback included.
- A request without the header gets a fresh id (UUID4 as 32 lowercase hex
  characters). Two requests never share one by accident.
- A request **with** the header keeps its value if, and only if, it is 1 to 64
  characters from `A-Z a-z 0-9 . _ -`. The same value comes back in the
  response header and is written to the log line.
- Anything else (empty, longer than 64, spaces, control characters, quotes,
  braces, non-ASCII) is not an error. It is discarded, a fresh id is used,
  and the rejected value is never echoed or logged, so a client cannot inject
  text into the log through this header.

### `/health` is logged like any other request

There is no exclusion. Render calls `/health` itself as the service's health
check (`healthCheckPath` in `render.yaml`), so those probes **appear in the
logs** as ordinary lines with `path: "/health"`. They are kept on purpose: the
first question in an outage is "did Render reach the app, and what did it get?",
and a log that hides the probes cannot answer it. A gap in the probe lines is
itself a signal. The cost is noise; filter it out when reading (below).

### Where the log goes

- **Local, `make run`:** the terminal.
- **Docker Compose:** `docker compose logs app` (service `app`).
- **Render:** the **Logs** tab of the `pinpoint` web service in the dashboard.
  Only the repository owner has dashboard access (`docs/permissions.md`).

### Finding one request by id

Take the id from the response header (`curl -i`) or from the caller's own
`X-Request-Id`, then:

```sh
docker compose logs app | grep '"request_id":"6a1bb916dd6749caa0c931db57be49fc"'
```

On Render, search the Logs tab for the id (the owner does this; agents cannot).
To leave the probe lines out locally:
`docker compose logs app | grep -v '"path":"/health"'`.

## What does not exist

- No metrics (no request counters, no latency histograms).
- No tracing: the request id is not propagated to other services and there is
  no span data.
- No log shipping or aggregation, and no retention of our own. How long Render
  keeps the service's logs is not recorded here (owner to confirm).
- No alerting on error rate or latency. A person has to look.
- No user id, e-mail or session id in the log.
- No request or response bodies, no headers, no query strings.

These were left out on purpose; they are parked for after the MVP.
