"""JSON access log and `X-Request-Id` (issue #38, part 5).

One pure ASGI middleware (not `BaseHTTPMiddleware`: it must see the matched
route after routing, and it must also cover unhandled exceptions). For every
HTTP request it

- resolves a request id: the incoming `X-Request-Id` if it is valid, else a
  fresh UUID4 hex string, and puts it on the response, whatever the response is
  (200, 404, 422, 500, a static file, the SPA fallback);
- writes ONE JSON object to stdout through the stdlib `logging` module:
  `ts`, `level`, `request_id`, `method`, `path`, `status`, `duration_ms`.

What is deliberately NOT logged: the query string, any header (so no
`Authorization`, no cookies), any body, and the concrete path. `path` is the
matched route template (`/guest/{guestToken}/pins`), because guest and share
tokens are path segments. When no route matched, or only the SPA catch-all did,
`path` is the fixed placeholder `unmatched`: an unmatched path is whatever the
client typed and can hold a token. See `ops/observability.md`.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-Id"
UNMATCHED_PATH = "unmatched"

# 1-64 characters, A-Z a-z 0-9 . _ - only. Matched with `fullmatch`: a `^...$`
# pattern would accept "abc\n" because `$` also matches before a trailing newline.
_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")

_LOGGER_NAME = "pinpoint.access"


def is_valid_request_id(value: str | None) -> bool:
    return value is not None and _REQUEST_ID.fullmatch(value) is not None


def resolve_request_id(incoming: str | None) -> str:
    """The incoming id if it is acceptable, else a new one. A rejected id is
    never returned, so it can never reach a header or a log line."""
    if is_valid_request_id(incoming):
        return incoming  # type: ignore[return-value]
    return uuid.uuid4().hex


class JsonFormatter(logging.Formatter):
    """Renders the `access` dict attached to a record as one JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds")
        payload: dict[str, Any] = {"ts": ts.replace("+00:00", "Z"), "level": record.levelname}
        payload.update(getattr(record, "access", {}))
        return json.dumps(payload, separators=(",", ":"))


class _StdoutHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """StreamHandler that looks `sys.stdout` up on every write (so tests can
    capture it) and flushes each line (so `docker logs` and Render show it
    immediately)."""

    def __init__(self) -> None:
        logging.Handler.__init__(self)

    @property
    def stream(self) -> Any:  # type: ignore[override]
        return sys.stdout

    @stream.setter
    def stream(self, value: Any) -> None:  # StreamHandler.setStream is not used
        pass


def _access_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        handler = _StdoutHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        # Our own handler is the only destination: no duplicate line if some
        # other code configures the root logger.
        logger.propagate = False
    return logger


def _route_template(scope: Scope) -> str:
    """The matched route's template, or `unmatched`. FastAPI stores the matched
    route in `scope["route"]` while routing, so this is read after the app ran."""
    route = scope.get("route")
    template = getattr(route, "path", None)
    # The SPA fallback is a `/{full_path:path}` catch-all: it "matches" every
    # path, so its template says nothing and the raw path must not be logged.
    if not isinstance(template, str) or ":path}" in template:
        return UNMATCHED_PATH
    return template


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.logger = _access_logger()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        incoming: str | None = None
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                incoming = value.decode("latin-1")
                break
        request_id = resolve_request_id(incoming)
        status: int | None = None

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        failed = False
        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            # Log, then let it propagate: the server keeps writing the
            # traceback to its own error log, and nothing here prints it.
            failed = True
            raise
        finally:
            if status is None:
                # 500 if the app raised before any response; 0 if the client
                # went away and no response was sent.
                status = 500 if failed else 0
            self.logger.log(
                logging.ERROR if status >= 500 else logging.INFO,
                "access",
                extra={
                    "access": {
                        "request_id": request_id,
                        "method": scope["method"],
                        "path": _route_template(scope),
                        "status": status,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    }
                },
            )


def install_access_log(app: Any) -> None:
    """Put the middleware OUTSIDE everything else, including Starlette's
    ServerErrorMiddleware. `app.add_middleware` would place it inside that one,
    and the 500 response for an unhandled exception is sent by
    ServerErrorMiddleware, so it would have neither the request id nor a
    status in the log. Wrapping the built stack covers it."""
    # uvicorn's own access log prints the concrete URL, query string included
    # (`"GET /guest/<token>?x=1 HTTP/1.1" 200`), which would put guest tokens in
    # the log next to our sanitised line. Ours replaces it. uvicorn configures
    # its loggers before it imports the app, so this is not undone afterwards.
    logging.getLogger("uvicorn.access").disabled = True

    build = app.build_middleware_stack

    def build_with_access_log() -> ASGIApp:
        return AccessLogMiddleware(build())

    app.build_middleware_stack = build_with_access_log
