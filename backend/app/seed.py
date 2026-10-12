"""Seed data for the demo, matching `frontend/src/lib/api/mock-seed.ts` exactly
(same ids, demo credentials, rooms/images/pins/comments).

Plain functions and dataclasses only — no dependency on `store/memory.py` or
any storage mechanics, so both `InMemoryStore` (this issue) and the future
`SQLAlchemyStore` (issue #6) can import this module to populate themselves.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEMO_EMAIL = "demo@pinpoint.studio"
DEMO_PASSWORD = "pinpoint"

SEED_IMAGES_DIR = Path(__file__).parent / "seed_images"


@dataclass(frozen=True)
class SeedUser:
    id: str
    email: str
    name: str
    password: str  # plaintext demo password; the store hashes it on seeding


@dataclass(frozen=True)
class SeedRoom:
    id: str
    owner_id: str
    title: str
    client_name: str
    created_at: str  # ISO 8601
    status: str
    guest_token: str
    approved_at: str | None
    approved_by: str | None


@dataclass(frozen=True)
class SeedImage:
    id: str
    room_id: str
    title: str
    filename: str  # file under seed_images/
    content_type: str
    created_at: str


@dataclass(frozen=True)
class SeedPin:
    id: str
    image_id: str
    number: int
    x: float
    y: float
    type: str
    status: str | None
    created_at: str


@dataclass(frozen=True)
class SeedComment:
    id: str
    pin_id: str
    text: str
    author_name: str
    author_role: str
    created_at: str


def seed_users() -> list[SeedUser]:
    return [
        SeedUser(id="u_demo", email=DEMO_EMAIL, name="Studio Halden", password=DEMO_PASSWORD),
    ]


def seed_rooms() -> list[SeedRoom]:
    return [
        SeedRoom(
            id="r_lakeside",
            owner_id="u_demo",
            title="Lakeside Villa — Round 2",
            client_name="Marta Lind",
            created_at="2026-10-05T09:12:00.000Z",
            status="open",
            guest_token="lakeside-demo",
            approved_at=None,
            approved_by=None,
        ),
        SeedRoom(
            id="r_atrium",
            owner_id="u_demo",
            title="Harbour Office Atrium",
            client_name="Nordvik Properties",
            created_at="2026-09-21T14:30:00.000Z",
            status="approved",
            guest_token="atrium-demo",
            approved_at="2026-09-28T10:00:00.000Z",
            approved_by="Jonas Berg",
        ),
    ]


def seed_images() -> list[SeedImage]:
    return [
        SeedImage(
            id="i_facade",
            room_id="r_lakeside",
            title="Lake facade, golden hour",
            filename="lake-facade.jpg",
            content_type="image/jpeg",
            created_at="2026-10-05T09:15:00.000Z",
        ),
        SeedImage(
            id="i_living",
            room_id="r_lakeside",
            title="Living room",
            filename="living-room.jpg",
            content_type="image/jpeg",
            created_at="2026-10-05T09:16:00.000Z",
        ),
        SeedImage(
            id="i_atrium",
            room_id="r_atrium",
            title="Atrium, ground level",
            filename="atrium.jpg",
            content_type="image/jpeg",
            created_at="2026-09-21T14:35:00.000Z",
        ),
    ]


def seed_pins() -> list[SeedPin]:
    return [
        SeedPin(id="p1", image_id="i_facade", number=1, x=62.5, y=30.2, type="fix", status="open", created_at="2026-10-06T08:01:00.000Z"),
        SeedPin(id="p2", image_id="i_facade", number=2, x=25.4, y=63.8, type="question", status="open", created_at="2026-10-06T08:05:00.000Z"),
        SeedPin(id="p3", image_id="i_facade", number=3, x=84.1, y=58.9, type="like", status=None, created_at="2026-10-06T08:09:00.000Z"),
        SeedPin(id="p4", image_id="i_living", number=1, x=70.2, y=63.1, type="fix", status="resolved", created_at="2026-10-06T08:20:00.000Z"),
        SeedPin(id="p5", image_id="i_living", number=2, x=44.0, y=40.5, type="like", status=None, created_at="2026-10-06T08:22:00.000Z"),
        SeedPin(id="p6", image_id="i_atrium", number=1, x=55.0, y=22.0, type="like", status=None, created_at="2026-09-24T11:00:00.000Z"),
        SeedPin(id="p7", image_id="i_atrium", number=2, x=30.0, y=70.0, type="fix", status="resolved", created_at="2026-09-24T11:04:00.000Z"),
    ]


def seed_comments() -> list[SeedComment]:
    return [
        SeedComment(id="c1", pin_id="p1", text="Could the cladding on the upper floor be a shade darker? It reads too orange here.", author_name="Marta Lind", author_role="client", created_at="2026-10-06T08:01:00.000Z"),
        SeedComment(id="c2", pin_id="p1", text="Noted — we'll test a smoked oak finish in the next round.", author_name="Studio Halden", author_role="studio", created_at="2026-10-06T09:30:00.000Z"),
        SeedComment(id="c3", pin_id="p2", text="Is the jetty part of the scope, or just staging?", author_name="Marta Lind", author_role="client", created_at="2026-10-06T08:05:00.000Z"),
        SeedComment(id="c4", pin_id="p3", text="Love the outdoor fireplace and the reflections.", author_name="Marta Lind", author_role="client", created_at="2026-10-06T08:09:00.000Z"),
        SeedComment(id="c5", pin_id="p4", text="Please remove the throw from the sofa.", author_name="Marta Lind", author_role="client", created_at="2026-10-06T08:20:00.000Z"),
        SeedComment(id="c6", pin_id="p4", text="Done in the updated render.", author_name="Studio Halden", author_role="studio", created_at="2026-10-07T10:00:00.000Z"),
        SeedComment(id="c7", pin_id="p5", text="This view is exactly what we hoped for.", author_name="Marta Lind", author_role="client", created_at="2026-10-06T08:22:00.000Z"),
        SeedComment(id="c8", pin_id="p6", text="The timber roof is stunning.", author_name="Jonas Berg", author_role="client", created_at="2026-09-24T11:00:00.000Z"),
        SeedComment(id="c9", pin_id="p7", text="Add more planting along the left balustrade.", author_name="Jonas Berg", author_role="client", created_at="2026-09-24T11:04:00.000Z"),
    ]


def read_seed_image_bytes(filename: str) -> bytes:
    return (SEED_IMAGES_DIR / filename).read_bytes()
