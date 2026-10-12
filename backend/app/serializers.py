"""Converts `Store` records (plain dataclasses, no HTTP/JSON concerns) into
the Pydantic response models defined by `openapi.yaml`."""

from __future__ import annotations

from typing import Callable

from fastapi import Response

from app.models.schemas import Comment, Pin, RenderImage, Room, RoomDetail, RoomSummary
from app.store.interface import CommentRecord, ImageRecord, PinRecord, RoomRecord, Store


def room_to_schema(room: RoomRecord) -> Room:
    return Room(
        id=room.id,
        title=room.title,
        clientName=room.client_name,
        createdAt=room.created_at,
        status=room.status,
        guestToken=room.guest_token,
        approvedAt=room.approved_at,
        approvedBy=room.approved_by,
    )


def room_summary_to_schema(room: RoomRecord, open_pin_count: int) -> RoomSummary:
    return RoomSummary(**room_to_schema(room).model_dump(), openPinCount=open_pin_count)


def image_to_schema(image: ImageRecord, url: str) -> RenderImage:
    return RenderImage(
        id=image.id,
        roomId=image.room_id,
        title=image.title,
        url=url,
        superseded=image.superseded,
        createdAt=image.created_at,
    )


def comment_to_schema(comment: CommentRecord) -> Comment:
    return Comment(
        id=comment.id,
        pinId=comment.pin_id,
        text=comment.text,
        authorName=comment.author_name,
        authorRole=comment.author_role,
        createdAt=comment.created_at,
    )


def pin_to_schema(pin: PinRecord, comments: list[CommentRecord]) -> Pin:
    return Pin(
        id=pin.id,
        imageId=pin.image_id,
        number=pin.number,
        x=pin.x,
        y=pin.y,
        type=pin.type,
        status=pin.status,
        createdAt=pin.created_at,
        comments=[comment_to_schema(c) for c in comments],
    )


def build_room_detail(
    store: Store,
    room: RoomRecord,
    image_url: Callable[[ImageRecord], str],
) -> RoomDetail:
    images = sorted(store.list_images_by_room(room.id), key=lambda i: i.created_at)
    pins = sorted(store.list_pins_by_room(room.id), key=lambda p: (p.image_id, p.number))
    return RoomDetail(
        room=room_to_schema(room),
        images=[image_to_schema(i, image_url(i)) for i in images],
        pins=[pin_to_schema(p, store.list_comments_by_pin(p.id)) for p in pins],
    )


def image_file_response(image: ImageRecord) -> Response:
    etag = f'"{image.id}-{int(image.created_at.timestamp())}"'
    return Response(
        content=image.data,
        media_type=image.content_type,
        headers={"ETag": etag, "Cache-Control": "public, max-age=86400"},
    )
