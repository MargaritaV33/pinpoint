"""Studio rooms: `listRooms`, `createRoom`, `getRoom`, `closeRoom`,
`exportOpenPins`."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import get_current_user
from app.export import format_open_pins_export
from app.ids import new_guest_token, new_id
from app.models.schemas import CreateRoomInput, Room, RoomDetail, RoomSummary, StudioUser
from app.serializers import build_room_detail, room_summary_to_schema, room_to_schema
from app.store import Store, get_store
from app.store.interface import RoomRecord

router = APIRouter(tags=["Studio rooms"])

_NOT_FOUND = "No such room, or it belongs to a different studio user."


def _owned_room(store: Store, room_id: str, user: StudioUser) -> RoomRecord:
    room = store.get_room_owned(room_id, user.id)
    if room is None:
        raise HTTPException(status_code=404, detail=_NOT_FOUND)
    return room


@router.get("/rooms", response_model=list[RoomSummary])
def list_rooms(user: StudioUser = Depends(get_current_user), store: Store = Depends(get_store)) -> list[RoomSummary]:
    summaries: list[RoomSummary] = []
    for room in store.list_rooms_by_owner(user.id):
        open_count = sum(1 for p in store.list_pins_by_room(room.id) if p.status == "open")
        summaries.append(room_summary_to_schema(room, open_count))
    return summaries


@router.post("/rooms", status_code=201, response_model=Room)
def create_room(
    body: CreateRoomInput,
    user: StudioUser = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> Room:
    title = body.title.strip()
    client_name = body.clientName.strip()
    if not title or not client_name:
        raise HTTPException(status_code=400, detail="Title and client name are required")

    room = store.create_room(
        id=new_id("r"),
        owner_id=user.id,
        title=title,
        client_name=client_name,
        created_at=datetime.now(timezone.utc),
        status="open",
        guest_token=new_guest_token(),
        approved_at=None,
        approved_by=None,
    )
    return room_to_schema(room)


@router.get("/rooms/{roomId}", response_model=RoomDetail)
def get_room(
    roomId: str,
    user: StudioUser = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> RoomDetail:
    room = _owned_room(store, roomId, user)
    return build_room_detail(store, room, lambda image: f"/rooms/{room.id}/images/{image.id}/file")


@router.post("/rooms/{roomId}/close", response_model=Room)
def close_room(
    roomId: str,
    user: StudioUser = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> Room:
    room = _owned_room(store, roomId, user)
    updated = store.set_room_status(room.id, "closed")
    return room_to_schema(updated)


@router.get("/rooms/{roomId}/export")
def export_open_pins(
    roomId: str,
    user: StudioUser = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> Response:
    room = _owned_room(store, roomId, user)
    detail = build_room_detail(store, room, lambda image: f"/rooms/{room.id}/images/{image.id}/file")
    text = format_open_pins_export(detail)
    return Response(content=text, media_type="text/plain")
