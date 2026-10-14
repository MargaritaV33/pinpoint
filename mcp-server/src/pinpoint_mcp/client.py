"""The one place that talks HTTP to Pinpoint.

Everything the MCP server knows about authentication, timeouts and error
wording lives here, so the tests mock exactly one thing (httpx, via respx) and
the tool layer never sees a token, a password or a raw exception.

Rules this module enforces (see mcp-server/README.md):

* Auth precedence: PINPOINT_TOKEN, else PINPOINT_EMAIL + PINPOINT_PASSWORD
  (POST /auth/login, token kept in memory only), else every authenticated call
  fails with a message naming the variables. Empty strings count as unset.
* A 401 after the server logged in itself triggers one re-login and one retry.
  A 401 with PINPOINT_TOKEN is reported and never retried.
* Only GET requests, plus POST /auth/login. No other method exists here.
* Nothing secret leaves this module: every message is passed through
  ``_scrub`` and the client never logs.
"""

from __future__ import annotations

import asyncio
import os
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8100"
TIMEOUT_SECONDS = 10.0

_NO_CREDENTIALS = (
    "Pinpoint credentials are not configured. Set PINPOINT_TOKEN (a studio "
    "bearer token), or both PINPOINT_EMAIL and PINPOINT_PASSWORD, in the "
    "environment of the MCP server."
)


class PinpointError(Exception):
    """An error whose message is safe and useful to show to the assistant."""


def _env(name: str, environ: dict[str, str] | os._Environ[str]) -> str:
    """Return the variable stripped, with empty/whitespace meaning unset."""
    return (environ.get(name) or "").strip()


@dataclass
class PinpointClient:
    base_url: str = DEFAULT_BASE_URL
    token: str = field(default="", repr=False)
    email: str = ""
    password: str = field(default="", repr=False)
    timeout: float = TIMEOUT_SECONDS
    # (method, path) of every request made, newest last; lets tests and the
    # integration test assert the read-only guarantee without touching the net.
    request_log: deque[tuple[str, str]] = field(default_factory=lambda: deque(maxlen=200))
    _session_token: str = field(default="", init=False, repr=False)
    _login_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self.base_url = (self.base_url or "").strip().rstrip("/") or DEFAULT_BASE_URL
        self.token = (self.token or "").strip()
        self.email = (self.email or "").strip()
        # The password is deliberately not stripped: spaces can be part of it.
        self.password = self.password or ""

    @classmethod
    def from_env(cls, environ: dict[str, str] | os._Environ[str] | None = None) -> PinpointClient:
        env = os.environ if environ is None else environ
        return cls(
            base_url=_env("PINPOINT_BASE_URL", env) or DEFAULT_BASE_URL,
            token=_env("PINPOINT_TOKEN", env),
            email=_env("PINPOINT_EMAIL", env),
            password=env.get("PINPOINT_PASSWORD") or "",
        )

    # -- auth mode ---------------------------------------------------------

    @property
    def uses_login(self) -> bool:
        """True when the server logs in itself (no PINPOINT_TOKEN, full pair)."""
        return not self.token and bool(self.email) and bool(self.password)

    def _scrub(self, text: str) -> str:
        for secret in (self.token, self.password, self._session_token):
            if secret:
                text = text.replace(secret, "[redacted]")
        return text

    # -- public request helpers ---------------------------------------------

    async def get_json(self, path: str, *, auth: bool = True) -> Any:
        response = await self._get(path, auth=auth)
        try:
            return response.json()
        except ValueError:
            raise PinpointError(
                f"Pinpoint returned HTTP {response.status_code} for GET {path} but the "
                "body was not valid JSON."
            ) from None

    async def get_text(self, path: str, *, auth: bool = True) -> str:
        return (await self._get(path, auth=auth)).text

    # -- internals -----------------------------------------------------------

    async def _get(self, path: str, *, auth: bool) -> httpx.Response:
        headers: dict[str, str] = {}
        if auth:
            headers["Authorization"] = f"Bearer {await self._bearer()}"
        response = await self._send("GET", path, headers=headers)

        if response.status_code == 401 and auth:
            if not self.uses_login:
                raise PinpointError(
                    "Pinpoint rejected PINPOINT_TOKEN (HTTP 401): it is expired or invalid. "
                    "Studio tokens expire (60 minutes by default); sign in again and set a "
                    "fresh PINPOINT_TOKEN, or use PINPOINT_EMAIL and PINPOINT_PASSWORD so "
                    "the server can log in by itself."
                )
            # Our own session expired: log in once more and retry this call once.
            self._session_token = ""
            headers["Authorization"] = f"Bearer {await self._bearer()}"
            response = await self._send("GET", path, headers=headers)
            if response.status_code == 401:
                raise PinpointError(
                    "Pinpoint rejected the session right after a fresh login (HTTP 401). "
                    "Check PINPOINT_EMAIL and PINPOINT_PASSWORD."
                )
        return self._check(response, "GET", path)

    async def _bearer(self) -> str:
        if self.token:
            return self.token
        if not self.uses_login:
            raise PinpointError(_NO_CREDENTIALS)
        async with self._login_lock:
            if not self._session_token:
                self._session_token = await self._login()
            return self._session_token

    async def _login(self) -> str:
        response = await self._send(
            "POST", "/auth/login", json={"email": self.email, "password": self.password}
        )
        if response.status_code == 401:
            raise PinpointError(
                "Login to Pinpoint failed (HTTP 401): check PINPOINT_EMAIL and "
                "PINPOINT_PASSWORD."
            )
        response = self._check(response, "POST", "/auth/login")
        try:
            token = response.json()["token"]
        except (ValueError, KeyError, TypeError):
            raise PinpointError(
                "Pinpoint's login response did not contain a session token."
            ) from None
        if not isinstance(token, str) or not token:
            raise PinpointError("Pinpoint's login response did not contain a session token.")
        return token

    async def _send(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json: Any = None,
    ) -> httpx.Response:
        self.request_log.append((method, path))
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                return await http.request(
                    method, f"{self.base_url}{path}", headers=headers, json=json
                )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError):
            raise PinpointError(
                f"Cannot reach Pinpoint at {self.base_url}. Is it running? Start the "
                "stack with `make up` (it listens on http://localhost:8100), or set "
                "PINPOINT_BASE_URL (http://localhost:8091 for `make run`)."
            ) from None
        except httpx.HTTPError as exc:
            raise PinpointError(
                f"Request to Pinpoint at {self.base_url} failed: {type(exc).__name__}."
            ) from None

    def _check(self, response: httpx.Response, method: str, path: str) -> httpx.Response:
        """Turn any non-2xx response into a PinpointError with a readable message."""
        if response.is_success:
            return response
        detail = ""
        try:
            body = response.json()
            if isinstance(body, dict) and isinstance(body.get("detail"), str):
                detail = body["detail"]
        except ValueError:
            pass
        status = response.status_code
        if status >= 500:
            message = f"Pinpoint failed with HTTP {status} for {method} {path}."
        elif detail:
            message = f"{detail} (HTTP {status} for {method} {path})"
        else:
            message = f"Pinpoint returned HTTP {status} for {method} {path}."
        raise PinpointError(self._scrub(message))
