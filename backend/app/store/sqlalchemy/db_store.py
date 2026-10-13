"""`SQLAlchemyStore(Store)` — the concrete store the running app uses from
issue #6 onward. Same contract as `app.store.memory.InMemoryStore`, backed by
a real database via `app.store.sqlalchemy.engine`.

Every method opens a short-lived `Session`, does its work, commits, and
converts ORM rows to the frozen dataclasses in `app.store.interface` before
returning — no SQLAlchemy type ever crosses out of this module.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as SqlSession

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
from app.store.sqlalchemy.engine import build_engine, build_session_factory
from app.store.sqlalchemy.models import (
    Base,
    Comment,
    Image,
    Pin,
    Room,
    Session as SessionModel,
    StudioUser,
)

# Hashing the demo password is the slow part of seeding (bcrypt); compute it
# once per process instead of on every `reset()` call (tests reset often) —
# same approach as `InMemoryStore`.
_DEMO_PASSWORD_HASH = hash_password(seed.DEMO_PASSWORD)


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _user_record(row: StudioUser) -> UserRecord:
    return UserRecord(id=row.id, email=row.email, name=row.name, password_hash=row.password_hash)


def _room_record(row: Room) -> RoomRecord:
    return RoomRecord(
        id=row.id,
        owner_id=row.owner_id,
        title=row.title,
        client_name=row.client_name,
        created_at=row.created_at,
        status=row.status,
        guest_token=row.guest_token,
        approved_at=row.approved_at,
        approved_by=row.approved_by,
    )


def _image_record(row: Image) -> ImageRecord:
    return ImageRecord(
        id=row.id,
        room_id=row.room_id,
        title=row.title,
        content_type=row.content_type,
        data=row.data,
        superseded=row.superseded,
        created_at=row.created_at,
    )


def _pin_record(row: Pin) -> PinRecord:
    return PinRecord(
        id=row.id,
        image_id=row.image_id,
        number=row.number,
        x=row.x,
        y=row.y,
        type=row.type,
        status=row.status,
        created_at=row.created_at,
    )


def _comment_record(row: Comment) -> CommentRecord:
    return CommentRecord(
        id=row.id,
        pin_id=row.pin_id,
        text=row.text,
        author_name=row.author_name,
        author_role=row.author_role,
        created_at=row.created_at,
    )


class SQLAlchemyStore(Store):
    def __init__(self, database_url: str) -> None:
        self._engine = build_engine(database_url)
        Base.metadata.create_all(self._engine)
        self._Session = build_session_factory(self._engine)
        self._seed()

    def reset(self) -> None:
        with self._Session() as session:
            # Children before parents, to respect the foreign keys in
            # models.py (comments -> pins -> images -> rooms).
            session.execute(delete(Comment))
            session.execute(delete(Pin))
            session.execute(delete(Image))
            session.execute(delete(Room))
            session.execute(delete(SessionModel))
            session.execute(delete(StudioUser))
            session.commit()
        self._seed()

    def _seed(self) -> None:
        with self._Session() as session:
            for u in seed.seed_users():
                password_hash = (
                    _DEMO_PASSWORD_HASH if u.password == seed.DEMO_PASSWORD else hash_password(u.password)
                )
                session.add(StudioUser(id=u.id, email=u.email, name=u.name, password_hash=password_hash))
            for r in seed.seed_rooms():
                session.add(
                    Room(
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
                )
            for i in seed.seed_images():
                data = seed.read_seed_image_bytes(i.filename)
                session.add(
                    Image(
                        id=i.id,
                        room_id=i.room_id,
                        title=i.title,
                        content_type=i.content_type,
                        data=data,
                        superseded=False,
                        created_at=_parse_dt(i.created_at),
                    )
                )
            for p in seed.seed_pins():
                session.add(
                    Pin(
                        id=p.id,
                        image_id=p.image_id,
                        number=p.number,
                        x=p.x,
                        y=p.y,
                        type=p.type,
                        status=p.status,
                        created_at=_parse_dt(p.created_at),
                    )
                )
            for c in seed.seed_comments():
                session.add(
                    Comment(
                        id=c.id,
                        pin_id=c.pin_id,
                        text=c.text,
                        author_name=c.author_name,
                        author_role=c.author_role,
                        created_at=_parse_dt(c.created_at),
                    )
                )
            session.commit()

    # -- Users ---------------------------------------------------------------
    def create_user(self, *, id: str, email: str, name: str, password_hash: str) -> UserRecord:
        with self._Session() as session:
            row = StudioUser(id=id, email=email, name=name, password_hash=password_hash)
            session.add(row)
            session.commit()
            return _user_record(row)

    def get_user_by_email(self, email: str) -> UserRecord | None:
        needle = email.lower()
        with self._Session() as session:
            row = session.scalars(select(StudioUser).where(func.lower(StudioUser.email) == needle)).first()
            return _user_record(row) if row is not None else None

    def get_user_by_id(self, user_id: str) -> UserRecord | None:
        with self._Session() as session:
            row = session.get(StudioUser, user_id)
            return _user_record(row) if row is not None else None

    # -- Sessions --------------------------------------------------------------
    def create_session(self, token: str, user_id: str) -> None:
        with self._Session() as session:
            session.merge(SessionModel(token=token, user_id=user_id))
            session.commit()

    def get_session_user_id(self, token: str) -> str | None:
        with self._Session() as session:
            row = session.get(SessionModel, token)
            return row.user_id if row is not None else None

    def delete_session(self, token: str) -> None:
        with self._Session() as session:
            session.execute(delete(SessionModel).where(SessionModel.token == token))
            session.commit()

    # -- Rooms -------------------------------------------------------------------
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
        with self._Session() as session:
            row = Room(
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
            session.add(row)
            session.commit()
            return _room_record(row)

    def get_room_by_id(self, room_id: str) -> RoomRecord | None:
        with self._Session() as session:
            row = session.get(Room, room_id)
            return _room_record(row) if row is not None else None

    def get_room_owned(self, room_id: str, owner_id: str) -> RoomRecord | None:
        with self._Session() as session:
            row = session.get(Room, room_id)
            if row is None or row.owner_id != owner_id:
                return None
            return _room_record(row)

    def get_room_by_guest_token(self, guest_token: str) -> RoomRecord | None:
        with self._Session() as session:
            row = session.scalars(select(Room).where(Room.guest_token == guest_token)).first()
            return _room_record(row) if row is not None else None

    def list_rooms_by_owner(self, owner_id: str) -> list[RoomRecord]:
        with self._Session() as session:
            rows = session.scalars(
                select(Room).where(Room.owner_id == owner_id).order_by(Room.created_at.asc(), Room.id.asc())
            ).all()
            return [_room_record(r) for r in rows]

    def set_room_status(
        self,
        room_id: str,
        status: str,
        *,
        approved_at: datetime | None = None,
        approved_by: str | None = None,
    ) -> RoomRecord:
        with self._Session() as session:
            row = session.get(Room, room_id)
            assert row is not None
            row.status = status
            if approved_at is not None:
                row.approved_at = approved_at
            if approved_by is not None:
                row.approved_by = approved_by
            session.commit()
            return _room_record(row)

    # -- Images --------------------------------------------------------------------
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
        with self._Session() as session:
            row = Image(
                id=id,
                room_id=room_id,
                title=title,
                content_type=content_type,
                data=data,
                superseded=False,
                created_at=created_at,
            )
            session.add(row)
            session.commit()
            return _image_record(row)

    def get_image_by_id(self, image_id: str) -> ImageRecord | None:
        with self._Session() as session:
            row = session.get(Image, image_id)
            return _image_record(row) if row is not None else None

    def get_image_in_room(self, image_id: str, room_id: str) -> ImageRecord | None:
        with self._Session() as session:
            row = session.get(Image, image_id)
            if row is None or row.room_id != room_id:
                return None
            return _image_record(row)

    def list_images_by_room(self, room_id: str) -> list[ImageRecord]:
        with self._Session() as session:
            rows = session.scalars(
                select(Image).where(Image.room_id == room_id).order_by(Image.created_at.asc(), Image.id.asc())
            ).all()
            return [_image_record(r) for r in rows]

    def set_image_superseded(self, image_id: str, superseded: bool) -> ImageRecord:
        with self._Session() as session:
            row = session.get(Image, image_id)
            assert row is not None
            row.superseded = superseded
            session.commit()
            return _image_record(row)

    def get_room_for_image(self, image_id: str) -> RoomRecord | None:
        with self._Session() as session:
            image = session.get(Image, image_id)
            if image is None:
                return None
            room = session.get(Room, image.room_id)
            return _room_record(room) if room is not None else None

    # -- Pins ------------------------------------------------------------------------
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
        with self._Session() as session:
            row = Pin(
                id=id,
                image_id=image_id,
                number=number,
                x=x,
                y=y,
                type=type,
                status=status,
                created_at=created_at,
            )
            session.add(row)
            session.commit()
            return _pin_record(row)

    def get_pin_by_id(self, pin_id: str) -> PinRecord | None:
        with self._Session() as session:
            row = session.get(Pin, pin_id)
            return _pin_record(row) if row is not None else None

    def list_pins_by_image(self, image_id: str) -> list[PinRecord]:
        with self._Session() as session:
            rows = session.scalars(
                select(Pin).where(Pin.image_id == image_id).order_by(Pin.created_at.asc(), Pin.id.asc())
            ).all()
            return [_pin_record(r) for r in rows]

    def list_pins_by_room(self, room_id: str) -> list[PinRecord]:
        with self._Session() as session:
            image_ids = select(Image.id).where(Image.room_id == room_id)
            rows = session.scalars(
                select(Pin).where(Pin.image_id.in_(image_ids)).order_by(Pin.created_at.asc(), Pin.id.asc())
            ).all()
            return [_pin_record(r) for r in rows]

    def next_pin_number(self, image_id: str) -> int:
        with self._Session() as session:
            max_number = session.scalar(select(func.max(Pin.number)).where(Pin.image_id == image_id))
            return (max_number or 0) + 1

    def set_pin_status(self, pin_id: str, status: str | None) -> PinRecord:
        with self._Session() as session:
            row = session.get(Pin, pin_id)
            assert row is not None
            row.status = status
            session.commit()
            return _pin_record(row)

    def get_room_for_pin(self, pin_id: str) -> RoomRecord | None:
        with self._Session() as session:
            pin = session.get(Pin, pin_id)
            if pin is None:
                return None
            image = session.get(Image, pin.image_id)
            if image is None:
                return None
            room = session.get(Room, image.room_id)
            return _room_record(room) if room is not None else None

    def get_image_for_pin(self, pin_id: str) -> ImageRecord | None:
        with self._Session() as session:
            pin = session.get(Pin, pin_id)
            if pin is None:
                return None
            image = session.get(Image, pin.image_id)
            return _image_record(image) if image is not None else None

    # -- Comments --------------------------------------------------------------------
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
        with self._Session() as session:
            row = Comment(
                id=id,
                pin_id=pin_id,
                text=text,
                author_name=author_name,
                author_role=author_role,
                created_at=created_at,
            )
            session.add(row)
            session.commit()
            return _comment_record(row)

    def list_comments_by_pin(self, pin_id: str) -> list[CommentRecord]:
        with self._Session() as session:
            rows = session.scalars(
                select(Comment).where(Comment.pin_id == pin_id).order_by(Comment.created_at.asc(), Comment.id.asc())
            ).all()
            return [_comment_record(r) for r in rows]
