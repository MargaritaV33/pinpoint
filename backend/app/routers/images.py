"""Studio images: `uploadImage`, `setImageSuperseded`, `getRoomImageFile`.

`413`/`415` for upload come from the contract (`openapi.yaml`), not the
frontend mock's `400` — see decisions in issue #4.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from app.auth import get_current_user
from app.config import settings
from app.ids import new_id
from app.models.schemas import RenderImage, SetImageSupersededInput, StudioUser
from app.serializers import image_file_response, image_to_schema
from app.store import Store, get_store

router = APIRouter(tags=["Studio images"])

ALLOWED_RENDER_TYPES = {"image/jpeg", "image/png"}


@router.post("/rooms/{roomId}/images", status_code=201, response_model=RenderImage)
async def upload_image(
    roomId: str,
    title: str = Form(...),
    file: UploadFile = File(...),
    user: StudioUser = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> RenderImage:
    room = store.get_room_owned(roomId, user.id)
    if room is None:
        raise HTTPException(status_code=404, detail="No such room, or it belongs to a different studio user.")
    if room.status == "closed":
        raise HTTPException(status_code=403, detail="This room is closed")

    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="Title is required")

    content_type = file.content_type or ""
    if content_type not in ALLOWED_RENDER_TYPES:
        raise HTTPException(status_code=415, detail="File must be a JPG or PNG.")

    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"File is larger than {settings.max_upload_mb} MB.")

    image = store.create_image(
        id=new_id("i"),
        room_id=roomId,
        title=clean_title,
        content_type=content_type,
        data=data,
        created_at=datetime.now(timezone.utc),
    )
    return image_to_schema(image, f"/rooms/{roomId}/images/{image.id}/file")


@router.patch("/images/{imageId}", response_model=RenderImage)
def set_image_superseded(
    imageId: str,
    body: SetImageSupersededInput,
    user: StudioUser = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> RenderImage:
    image = store.get_image_by_id(imageId)
    room = store.get_room_for_image(imageId) if image is not None else None
    if image is None or room is None or room.owner_id != user.id:
        raise HTTPException(status_code=404, detail="No such image, or its room belongs to a different studio user.")
    if room.status == "closed":
        raise HTTPException(status_code=403, detail="The image's room is closed")

    updated = store.set_image_superseded(imageId, body.superseded)
    return image_to_schema(updated, f"/rooms/{room.id}/images/{imageId}/file")


@router.get("/rooms/{roomId}/images/{imageId}/file")
def get_room_image_file(
    roomId: str,
    imageId: str,
    user: StudioUser = Depends(get_current_user),
    store: Store = Depends(get_store),
) -> Response:
    room = store.get_room_owned(roomId, user.id)
    if room is None:
        raise HTTPException(status_code=404, detail="No such image in this room.")
    image = store.get_image_in_room(imageId, roomId)
    if image is None:
        raise HTTPException(status_code=404, detail="No such image in this room.")
    return image_file_response(image, authenticated=True)
