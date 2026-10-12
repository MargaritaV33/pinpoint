"""Studio pins: `setPinStatus`, `addStudioComment`.

A studio reply (`addStudioComment`) never changes a pin's status — only
`addGuestComment` (in `guest.py`) can reopen a resolved pin.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.ids import new_id
from app.models.schemas import AddStudioCommentInput, Comment, Pin, SetPinStatusInput, StudioUser
from app.serializers import comment_to_schema, pin_to_schema
from app.store import Store, get_store
from app.store.interface import PinRecord, RoomRecord

router = APIRouter(tags=["Studio pins"])

_NOT_FOUND = "No such pin, or its room belongs to a different studio user."


def _owned_pin(store: Store, pin_id: str, user: StudioUser) -> tuple[PinRecord, RoomRecord]:
    pin = store.get_pin_by_id(pin_id)
    room = store.get_room_for_pin(pin_id) if pin is not None else None
    if pin is None or room is None or room.owner_id != user.id:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return pin, room


@router.patch("/pins/{pinId}", response_model=Pin)
def set_pin_status(
    pinId: str,
    body: SetPinStatusInput,
    user: StudioUser = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> Pin:
    pin, room = _owned_pin(store, pinId, user)
    if room.status == "closed":
        raise HTTPException(status_code=403, detail="The pin's room is closed")
    if pin.type == "like":
        raise HTTPException(status_code=400, detail="like pins have no status")

    updated = store.set_pin_status(pinId, body.status)
    comments = store.list_comments_by_pin(pinId)
    return pin_to_schema(updated, comments)


@router.post("/pins/{pinId}/comments", status_code=201, response_model=Comment)
def add_studio_comment(
    pinId: str,
    body: AddStudioCommentInput,
    user: StudioUser = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> Comment:
    _, room = _owned_pin(store, pinId, user)
    if room.status == "closed":
        raise HTTPException(status_code=403, detail="The pin's room is closed")

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Comment cannot be empty")

    comment = store.create_comment(
        id=new_id("c"),
        pin_id=pinId,
        text=text,
        author_name=user.name,
        author_role="studio",
        created_at=datetime.now(timezone.utc),
    )
    return comment_to_schema(comment)
