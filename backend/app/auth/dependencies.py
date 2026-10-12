"""The two FastAPI auth dependencies routers use: a bearer token resolved to
the owning `StudioUser`, and a `guestToken` path segment resolved to its
`Room`.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import TokenError, decode_access_token
from app.models.schemas import StudioUser
from app.store import Store, get_store
from app.store.interface import RoomRecord

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    store: Store = Depends(get_store),
) -> str:
    """Validates the bearer token (signature, expiry, and that it is still
    an active session) and returns the raw token string. `/auth/logout`
    needs the raw token itself (to delete the session record); other
    studio routes use `get_current_user` instead."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = credentials.credentials

    try:
        user_id = decode_access_token(token)
    except TokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None

    # A well-formed, unexpired JWT is not enough: it must also still be an
    # active session, so `/auth/logout` can actually revoke it.
    if store.get_session_user_id(token) != user_id:
        raise HTTPException(status_code=401, detail="Session has been logged out")

    return token


def get_current_user(
    token: str = Depends(get_current_token),
    store: Store = Depends(get_store),
) -> StudioUser:
    user_id = store.get_session_user_id(token)
    user = store.get_user_by_id(user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    return StudioUser(id=user.id, email=user.email, name=user.name)


def get_guest_room(
    guestToken: str,
    store: Store = Depends(get_store),
) -> RoomRecord:
    room = store.get_room_by_guest_token(guestToken)
    if room is None:
        raise HTTPException(status_code=404, detail="This review link is not valid")
    return room
