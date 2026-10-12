"""Guest (client) side: `getGuestRoom`, `createGuestPin`, `addGuestComment`,
`approveRound`, `getGuestImageFile`. No account — a display name plus the
room's guest token, carried as a path segment (never a header or query
parameter, and never stored as a guest account).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import get_guest_room
from app.ids import new_id
from app.models.schemas import (
    AddGuestCommentInput,
    ApproveRoundInput,
    Comment,
    CreatePinInput,
    Pin,
    Room,
    RoomDetail,
)
from app.serializers import build_room_detail, comment_to_schema, image_file_response, pin_to_schema, room_to_schema
from app.store import Store, get_store
from app.store.interface import RoomRecord

router = APIRouter(prefix="/guest", tags=["Guest"])


def _assert_open(room: RoomRecord) -> None:
    if room.status == "closed":
        raise HTTPException(status_code=403, detail="This room is closed")


@router.get("/{guestToken}", response_model=RoomDetail)
def get_guest_room_detail(
    guestToken: str,
    room: RoomRecord = Depends(get_guest_room),
    store: Store = Depends(get_store),
) -> RoomDetail:
    return build_room_detail(store, room, lambda image: f"/guest/{guestToken}/images/{image.id}/file")


@router.post("/{guestToken}/pins", status_code=201, response_model=Pin)
def create_guest_pin(
    guestToken: str,
    body: CreatePinInput,
    room: RoomRecord = Depends(get_guest_room),
    store: Store = Depends(get_store),
) -> Pin:
    _assert_open(room)

    image = store.get_image_in_room(body.imageId, room.id)
    if image is None:
        raise HTTPException(status_code=404, detail="`imageId` does not belong to this room.")
    if image.superseded:
        raise HTTPException(status_code=409, detail="This render has been replaced")

    author_name = body.authorName.strip()
    text = body.text.strip()
    if not author_name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not text:
        raise HTTPException(status_code=400, detail="Comment cannot be empty")
    for value in (body.x, body.y):
        if not math.isfinite(value) or value < 0 or value > 100:
            raise HTTPException(status_code=400, detail="Pin position out of range")

    number = store.next_pin_number(image.id)
    status = None if body.type == "like" else "open"
    pin = store.create_pin(
        id=new_id("p"),
        image_id=image.id,
        number=number,
        x=body.x,
        y=body.y,
        type=body.type,
        status=status,
        created_at=datetime.now(timezone.utc),
    )
    store.create_comment(
        id=new_id("c"),
        pin_id=pin.id,
        text=text,
        author_name=author_name,
        author_role="client",
        created_at=datetime.now(timezone.utc),
    )

    # New feedback (not a `like`) after approval re-opens the round.
    if room.status == "approved" and body.type != "like":
        store.set_room_status(room.id, "open")

    comments = store.list_comments_by_pin(pin.id)
    return pin_to_schema(pin, comments)


@router.post("/{guestToken}/pins/{pinId}/comments", status_code=201, response_model=Comment)
def add_guest_comment(
    guestToken: str,
    pinId: str,
    body: AddGuestCommentInput,
    room: RoomRecord = Depends(get_guest_room),
    store: Store = Depends(get_store),
) -> Comment:
    _assert_open(room)

    pin = store.get_pin_by_id(pinId)
    pin_room = store.get_room_for_pin(pinId) if pin is not None else None
    if pin is None or pin_room is None or pin_room.id != room.id:
        raise HTTPException(status_code=404, detail="The pin does not belong to this room.")

    author_name = body.authorName.strip()
    text = body.text.strip()
    if not author_name:
        raise HTTPException(status_code=400, detail="Name is required")
    if not text:
        raise HTTPException(status_code=400, detail="Comment cannot be empty")

    comment = store.create_comment(
        id=new_id("c"),
        pin_id=pinId,
        text=text,
        author_name=author_name,
        author_role="client",
        created_at=datetime.now(timezone.utc),
    )

    # A guest reply reopens a pin the studio resolved (fix/question only —
    # like pins have no status and never reach this branch). A studio reply
    # (`addStudioComment`) never does this.
    if pin.status == "resolved":
        store.set_pin_status(pinId, "open")

    return comment_to_schema(comment)


@router.post("/{guestToken}/approve", response_model=Room)
def approve_round(
    guestToken: str,
    body: ApproveRoundInput,
    room: RoomRecord = Depends(get_guest_room),
    store: Store = Depends(get_store),
) -> Room:
    # `get_guest_room` already 404s on an unknown token, for every guest
    # route including this one — fixing the gap documented in `openapi.yaml`
    # (`approveRound` only writes down 200/403) without touching the file.
    _assert_open(room)
    approved_by = body.authorName.strip() or None
    updated = store.set_room_status(room.id, "approved", approved_at=datetime.now(timezone.utc), approved_by=approved_by)
    return room_to_schema(updated)


@router.get("/{guestToken}/images/{imageId}/file")
def get_guest_image_file(
    guestToken: str,
    imageId: str,
    room: RoomRecord = Depends(get_guest_room),
    store: Store = Depends(get_store),
) -> Response:
    image = store.get_image_in_room(imageId, room.id)
    if image is None:
        raise HTTPException(
            status_code=404,
            detail="No such image, the guest token does not match any room, or the image does not belong to that room.",
        )
    return image_file_response(image)
