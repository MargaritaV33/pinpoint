"""Studio auth: `signup`, `login`, `logout`, `getCurrentUser`."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import create_access_token, get_current_token, get_current_user, hash_password, verify_password
from app.ids import new_id
from app.models.schemas import AuthCredentials, Session, StudioUser
from app.store import Store, get_store

router = APIRouter(prefix="/auth", tags=["Studio auth"])

_EMAIL_RE = re.compile(r"^\S+@\S+\.\S+$")


def _start_session(store: Store, user_id: str) -> str:
    token = create_access_token(user_id)
    store.create_session(token, user_id)
    return token


@router.post("/signup", status_code=201, response_model=Session)
def signup(body: AuthCredentials, store: Store = Depends(get_store)) -> Session:
    email = body.email.strip()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="A valid email is required")
    if not body.password:
        raise HTTPException(status_code=400, detail="Password is required")
    if store.get_user_by_email(email) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    name = email.split("@")[0] or email
    user = store.create_user(id=new_id("u"), email=email, name=name, password_hash=hash_password(body.password))
    token = _start_session(store, user.id)
    return Session(token=token, user=StudioUser(id=user.id, email=user.email, name=user.name))


@router.post("/login", response_model=Session)
def login(body: AuthCredentials, store: Store = Depends(get_store)) -> Session:
    user = store.get_user_by_email(body.email.strip())
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")

    token = _start_session(store, user.id)
    return Session(token=token, user=StudioUser(id=user.id, email=user.email, name=user.name))


@router.post("/logout", status_code=204)
def logout(token: str = Depends(get_current_token), store: Store = Depends(get_store)) -> Response:
    store.delete_session(token)
    return Response(status_code=204)


@router.get("/me", response_model=StudioUser)
def get_me(user: StudioUser = Depends(get_current_user)) -> StudioUser:
    return user
