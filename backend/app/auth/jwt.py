"""Bearer token encode/decode (PyJWT). The JWT alone isn't enough to decide
whether a token is still valid, since JWTs can't be revoked — see
`auth/dependencies.py`, which also checks the store's active-session record.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from app.config import settings

ALGORITHM = "HS256"


class TokenError(Exception):
    """Raised for a missing, malformed, or expired token."""


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    """Returns the user id (`sub` claim), or raises `TokenError`."""
    try:
        payload = pyjwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except pyjwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise TokenError("Token has no subject")
    return sub
