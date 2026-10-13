"""Plain Python objects in memory — no persistence beyond the process's
lifetime. Unused by the running app since issue #6, which wired
`store/__init__.py`'s singleton to `SQLAlchemyStore` instead (the real store
needed so data survives a backend restart). Kept here as a correct `Store`
reference implementation and for anyone who wants a fast, DB-free test
double later.
"""

from __future__ import annotations

from datetime import datetime

from app import seed
from app.auth.hashing import hash_password
from app.store.interface import (
    CommentRecord,
    ImageRecord,
    PinRecord,
    RoomRecord,
    Store,
    UserRecord,
)

# Hashing the demo password is the slow part of seeding (bcrypt); compute it
# once per process instead of on every `reset()` call (tests reset often).
_DEMO_PASSWORD_HASH = hash_password(seed.DEMO_PASSWORD)


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class InMemoryStore(Store):
    def __init__(self) -> None:
        self._users: dict[str, UserRecord] = {}
        self._sessions: dict[str, str] = {}
        self._rooms: dict[str, RoomRecord] = {}
        self._images: dict[str, ImageRecord] = {}
        self._pins: dict[str, PinRecord] = {}
        self._comments: dict[str, CommentRecord] = {}
        self._seed()

    def reset(self) -> None:
        self._users.clear()
        self._sessions.clear()
        self._rooms.clear()
        self._images.clear()
        self._pins.clear()
        self._comments.clear()
        self._seed()

    def _seed(self) -> None:
        for u in seed.seed_users():
            password_hash = _DEMO_PASSWORD_HASH if u.password == seed.DEMO_PASSWORD else hash_password(u.password)
            self._users[u.id] = UserRecord(id=u.id, email=u.email, name=u.name, password_hash=password_hash)
        for r in seed.seed_rooms():
            self._rooms[r.id] = RoomRecord(
                id=r.id,
                owner_id=r.owner_id,
                title=r.title,
                client_name=r.client_name,
                created_at=_parse_dt(r.created_at),
                status=r.status,
                guest_token=r.guest_token,
                approved_at=_parse_dt(r.approved_at) if r.approved_at else None,
                approved_by=r.approved_by,
            )
        for i in seed.seed_images():
            data = seed.read_seed_image_bytes(i.filename)
            self._images[i.id] = ImageRecord(
                id=i.id,
                room_id=i.room_id,
                title=i.title,
                content_type=i.content_type,
                data=data,
                superseded=False,
                created_at=_parse_dt(i.created_at),
            )
        for p in seed.seed_pins():
            self._pins[p.id] = PinRecord(
                id=p.id,
                image_id=p.image_id,
                number=p.number,
                x=p.x,
                y=p.y,
                type=p.type,
                status=p.status,
                created_at=_parse_dt(p.created_at),
            )
        for c in seed.seed_comments():
            self._comments[c.id] = CommentRecord(
                id=c.id,
                pin_id=c.pin_id,
                text=c.text,
                author_name=c.author_name,
                author_role=c.author_role,
                created_at=_parse_dt(c.created_at),
            )

    # -- Users -------------------------------------------------------------
    def create_user(self, *, id: str, email: str, name: str, password_hash: str) -> UserRecord:
        user = UserRecord(id=id, email=email, name=name, password_hash=password_hash)
        self._users[id] = user
        return user

    def get_user_by_email(self, email: str) -> UserRecord | None:
        needle = email.lower()
        for user in self._users.values():
            if user.email.lower() == needle:
                return user
        return None

    def get_user_by_id(self, user_id: str) -> UserRecord | None:
        return self._users.get(user_id)

    # -- Sessions -----------------------------------------------------------
    def create_session(self, token: str, user_id: str) -> None:
        self._sessions[token] = user_id

    def get_session_user_id(self, token: str) -> str | None:
        return self._sessions.get(token)

    def delete_session(self, token: str) -> None:
        self._sessions.pop(token, None)

    # -- Rooms ----------------------------------------------------------------
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
    ) -> RoomRecord:
        room = RoomRecord(
            id=id,
            owner_id=owner_id,
            title=title,
            client_name=client_name,
            created_at=created_at,
            status=status,
            guest_token=guest_token,
            approved_at=approved_at,
            approved_by=approved_by,
        )
        self._rooms[id] = room
        return room

    def get_room_by_id(self, room_id: str) -> RoomRecord | None:
        return self._rooms.get(room_id)

    def get_room_owned(self, room_id: str, owner_id: str) -> RoomRecord | None:
        room = self._rooms.get(room_id)
        if room is None or room.owner_id != owner_id:
            return None
        return room

    def get_room_by_guest_token(self, guest_token: str) -> RoomRecord | None:
        for room in self._rooms.values():
            if room.guest_token == guest_token:
                return room
        return None

    def list_rooms_by_owner(self, owner_id: str) -> list[RoomRecord]:
        return [r for r in self._rooms.values() if r.owner_id == owner_id]

    def set_room_status(
        self,
        room_id: str,
        status: str,
        *,
        approved_at: datetime | None = None,
        approved_by: str | None = None,
    ) -> RoomRecord:
        room = self._rooms[room_id]
        updated = RoomRecord(
            id=room.id,
            owner_id=room.owner_id,
            title=room.title,
            client_name=room.client_name,
            created_at=room.created_at,
            status=status,
            guest_token=room.guest_token,
            approved_at=approved_at if approved_at is not None else room.approved_at,
            approved_by=approved_by if approved_by is not None else room.approved_by,
        )
        self._rooms[room_id] = updated
        return updated

    # -- Images ----------------------------------------------------------------
    def create_image(
        self,
        *,
        id: str,
        room_id: str,
        title: str,
        content_type: str,
        data: bytes,
        created_at: datetime,
    ) -> ImageRecord:
        image = ImageRecord(
            id=id,
            room_id=room_id,
            title=title,
            content_type=content_type,
            data=data,
            superseded=False,
            created_at=created_at,
        )
        self._images[id] = image
        return image

    def get_image_by_id(self, image_id: str) -> ImageRecord | None:
        return self._images.get(image_id)

    def get_image_in_room(self, image_id: str, room_id: str) -> ImageRecord | None:
        image = self._images.get(image_id)
        if image is None or image.room_id != room_id:
            return None
        return image

    def list_images_by_room(self, room_id: str) -> list[ImageRecord]:
        return [i for i in self._images.values() if i.room_id == room_id]

    def set_image_superseded(self, image_id: str, superseded: bool) -> ImageRecord:
        image = self._images[image_id]
        updated = ImageRecord(
            id=image.id,
            room_id=image.room_id,
            title=image.title,
            content_type=image.content_type,
            data=image.data,
            superseded=superseded,
            created_at=image.created_at,
        )
        self._images[image_id] = updated
        return updated

    def get_room_for_image(self, image_id: str) -> RoomRecord | None:
        image = self._images.get(image_id)
        if image is None:
            return None
        return self._rooms.get(image.room_id)

    # -- Pins --------------------------------------------------------------------
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
    ) -> PinRecord:
        pin = PinRecord(
            id=id,
            image_id=image_id,
            number=number,
            x=x,
            y=y,
            type=type,
            status=status,
            created_at=created_at,
        )
        self._pins[id] = pin
        return pin

    def get_pin_by_id(self, pin_id: str) -> PinRecord | None:
        return self._pins.get(pin_id)

    def list_pins_by_image(self, image_id: str) -> list[PinRecord]:
        return [p for p in self._pins.values() if p.image_id == image_id]

    def list_pins_by_room(self, room_id: str) -> list[PinRecord]:
        image_ids = {i.id for i in self._images.values() if i.room_id == room_id}
        return [p for p in self._pins.values() if p.image_id in image_ids]

    def next_pin_number(self, image_id: str) -> int:
        numbers = [p.number for p in self._pins.values() if p.image_id == image_id]
        return max(numbers, default=0) + 1

    def set_pin_status(self, pin_id: str, status: str | None) -> PinRecord:
        pin = self._pins[pin_id]
        updated = PinRecord(
            id=pin.id,
            image_id=pin.image_id,
            number=pin.number,
            x=pin.x,
            y=pin.y,
            type=pin.type,
            status=status,
            created_at=pin.created_at,
        )
        self._pins[pin_id] = updated
        return updated

    def get_room_for_pin(self, pin_id: str) -> RoomRecord | None:
        image = self.get_image_for_pin(pin_id)
        if image is None:
            return None
        return self._rooms.get(image.room_id)

    def get_image_for_pin(self, pin_id: str) -> ImageRecord | None:
        pin = self._pins.get(pin_id)
        if pin is None:
            return None
        return self._images.get(pin.image_id)

    # -- Comments -----------------------------------------------------------------
    def create_comment(
        self,
        *,
        id: str,
        pin_id: str,
        text: str,
        author_name: str,
        author_role: str,
        created_at: datetime,
    ) -> CommentRecord:
        comment = CommentRecord(
            id=id,
            pin_id=pin_id,
            text=text,
            author_name=author_name,
            author_role=author_role,
            created_at=created_at,
        )
        self._comments[id] = comment
        return comment

    def list_comments_by_pin(self, pin_id: str) -> list[CommentRecord]:
        comments = [c for c in self._comments.values() if c.pin_id == pin_id]
        comments.sort(key=lambda c: c.created_at)
        return comments
