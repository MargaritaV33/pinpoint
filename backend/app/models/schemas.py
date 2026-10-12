"""One Pydantic model per schema in `openapi.yaml`'s `components/schemas`.

Request-body models deliberately use plain `str`/`float` fields with no
pydantic-level constraints (no `EmailStr`, no `Field(min_length=1)`, no
`Field(ge=0, le=100)`): the contract's error responses for blank/invalid
input are `400` with an `Error` body, not FastAPI's default `422`. Routers
validate these by hand and raise `HTTPException(400, ...)` so the status
code matches the contract; see `routers/`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

RoomStatus = Literal["open", "approved", "closed"]
PinType = Literal["fix", "question", "like"]
PinStatusValue = Literal["open", "resolved"]
AuthorRole = Literal["studio", "client"]


class ErrorResponse(BaseModel):
    detail: str


class StudioUser(BaseModel):
    id: str
    email: str
    name: str


class Session(BaseModel):
    token: str
    user: StudioUser


class AuthCredentials(BaseModel):
    email: str
    password: str


class Room(BaseModel):
    id: str
    title: str
    clientName: str
    createdAt: datetime
    status: RoomStatus
    guestToken: str
    approvedAt: datetime | None
    approvedBy: str | None


class RoomSummary(Room):
    openPinCount: int


class CreateRoomInput(BaseModel):
    title: str
    clientName: str


class RenderImage(BaseModel):
    id: str
    roomId: str
    title: str
    url: str
    superseded: bool
    createdAt: datetime


class SetImageSupersededInput(BaseModel):
    superseded: bool


class Comment(BaseModel):
    id: str
    pinId: str
    text: str
    authorName: str
    authorRole: AuthorRole
    createdAt: datetime


class Pin(BaseModel):
    id: str
    imageId: str
    number: int
    x: float
    y: float
    type: PinType
    status: PinStatusValue | None
    createdAt: datetime
    comments: list[Comment]


class CreatePinInput(BaseModel):
    imageId: str
    x: float
    y: float
    type: PinType
    text: str
    authorName: str


class SetPinStatusInput(BaseModel):
    status: PinStatusValue


class AddStudioCommentInput(BaseModel):
    text: str


class AddGuestCommentInput(BaseModel):
    text: str
    authorName: str


class ApproveRoundInput(BaseModel):
    authorName: str


class RoomDetail(BaseModel):
    room: Room
    images: list[RenderImage]
    pins: list[Pin]
