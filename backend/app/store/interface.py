"""The storage contract every backing store (in-memory now, SQLAlchemy in
issue #6) must implement.

This is an `abc.ABC`, not a `typing.Protocol`, on purpose: an ABC fails
loudly — `TypeError` at instantiation — if a concrete store forgets to
implement one of these methods, whereas a `Protocol` would silently allow a
half-implemented store to be used anywhere `Store` is expected until the
missing method is actually called. Routers, `auth/`, and tests depend only
on this type, obtained via the `get_store` FastAPI dependency in
`store/__init__.py`.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UserRecord:
    id: str
    email: str
    name: str
    password_hash: str


@dataclass(frozen=True)
class RoomRecord:
    id: str
    owner_id: str
    title: str
    client_name: str
    created_at: datetime
    status: str  # "open" | "approved" | "closed"
    guest_token: str
    approved_at: datetime | None
    approved_by: str | None


@dataclass(frozen=True)
class ImageRecord:
    id: str
    room_id: str
    title: str
    content_type: str
    data: bytes
    superseded: bool
    created_at: datetime


@dataclass(frozen=True)
class PinRecord:
    id: str
    image_id: str
    number: int
    x: float
    y: float
    type: str  # "fix" | "question" | "like"
    status: str | None  # "open" | "resolved" | None (like pins)
    created_at: datetime


@dataclass(frozen=True)
class CommentRecord:
    id: str
    pin_id: str
    text: str
    author_name: str
    author_role: str  # "studio" | "client"
    created_at: datetime


class Store(abc.ABC):
    """Storage operations the routers need. No HTTP concerns in here."""

    # -- Users ---------------------------------------------------------
    @abc.abstractmethod
    def create_user(self, *, id: str, email: str, name: str, password_hash: str) -> UserRecord: ...

    @abc.abstractmethod
    def get_user_by_email(self, email: str) -> UserRecord | None: ...

    @abc.abstractmethod
    def get_user_by_id(self, user_id: str) -> UserRecord | None: ...

    # -- Sessions (server-side record so logout can truly revoke a token) --
    @abc.abstractmethod
    def create_session(self, token: str, user_id: str) -> None: ...

    @abc.abstractmethod
    def get_session_user_id(self, token: str) -> str | None: ...

    @abc.abstractmethod
    def delete_session(self, token: str) -> None: ...

    # -- Rooms -----------------------------------------------------------
    @abc.abstractmethod
    def create_room(
        self,
        *,
        id: str,
        owner_id: str,
        title: str,
        client_name: str,
        created_at: datetime,
        status: str,
        guest_token: str,
        approved_at: datetime | None,
        approved_by: str | None,
    ) -> RoomRecord: ...

    @abc.abstractmethod
    def get_room_by_id(self, room_id: str) -> RoomRecord | None: ...

    @abc.abstractmethod
    def get_room_owned(self, room_id: str, owner_id: str) -> RoomRecord | None: ...

    @abc.abstractmethod
    def get_room_by_guest_token(self, guest_token: str) -> RoomRecord | None: ...

    @abc.abstractmethod
    def list_rooms_by_owner(self, owner_id: str) -> list[RoomRecord]: ...

    @abc.abstractmethod
    def set_room_status(
        self,
        room_id: str,
        status: str,
        *,
        approved_at: datetime | None = None,
        approved_by: str | None = None,
    ) -> RoomRecord:
        """Update a room's status. Pass `approved_at`/`approved_by` only when
        approving; otherwise they are left as already stored."""
        ...

    # -- Images ------------------------------------------------------------
    @abc.abstractmethod
    def create_image(
        self,
        *,
        id: str,
        room_id: str,
        title: str,
        content_type: str,
        data: bytes,
        created_at: datetime,
    ) -> ImageRecord: ...

    @abc.abstractmethod
    def get_image_by_id(self, image_id: str) -> ImageRecord | None: ...

    @abc.abstractmethod
    def get_image_in_room(self, image_id: str, room_id: str) -> ImageRecord | None: ...

    @abc.abstractmethod
    def list_images_by_room(self, room_id: str) -> list[ImageRecord]: ...

    @abc.abstractmethod
    def set_image_superseded(self, image_id: str, superseded: bool) -> ImageRecord: ...

    @abc.abstractmethod
    def get_room_for_image(self, image_id: str) -> RoomRecord | None: ...

    # -- Pins ----------------------------------------------------------------
    @abc.abstractmethod
    def create_pin(
        self,
        *,
        id: str,
        image_id: str,
        number: int,
        x: float,
        y: float,
        type: str,
        status: str | None,
        created_at: datetime,
    ) -> PinRecord: ...

    @abc.abstractmethod
    def get_pin_by_id(self, pin_id: str) -> PinRecord | None: ...

    @abc.abstractmethod
    def list_pins_by_image(self, image_id: str) -> list[PinRecord]: ...

    @abc.abstractmethod
    def list_pins_by_room(self, room_id: str) -> list[PinRecord]: ...

    @abc.abstractmethod
    def next_pin_number(self, image_id: str) -> int:
        """Sequential per image, starting at 1, independent of other images."""
        ...

    @abc.abstractmethod
    def set_pin_status(self, pin_id: str, status: str | None) -> PinRecord: ...

    @abc.abstractmethod
    def get_room_for_pin(self, pin_id: str) -> RoomRecord | None: ...

    @abc.abstractmethod
    def get_image_for_pin(self, pin_id: str) -> ImageRecord | None: ...

    # -- Comments ------------------------------------------------------------
    @abc.abstractmethod
    def create_comment(
        self,
        *,
        id: str,
        pin_id: str,
        text: str,
        author_name: str,
        author_role: str,
        created_at: datetime,
    ) -> CommentRecord: ...

    @abc.abstractmethod
    def list_comments_by_pin(self, pin_id: str) -> list[CommentRecord]: ...

    # -- Test support ----------------------------------------------------
    @abc.abstractmethod
    def reset(self) -> None:
        """Clear all state and reseed the demo data. Used between tests so
        each test starts from the same known state without any test
        importing `InMemoryStore` directly."""
        ...
