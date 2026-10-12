"""Plain-text "open pins" export, grouped by image. Mirrors the shape of
`frontend/src/lib/api/export.ts`'s `formatOpenPinsExport` (not required to
match byte-for-byte — the frontend isn't wired to this backend until #5 —
but there is no reason to diverge)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.schemas import RoomDetail


def format_open_pins_export(detail: RoomDetail, exported_at: datetime | None = None) -> str:
    exported_at = exported_at or datetime.now(timezone.utc)
    lines = [
        "Pinpoint — open pins",
        f"Room: {detail.room.title}",
        f"Client: {detail.room.clientName}",
        f"Exported: {exported_at.strftime('%Y-%m-%d %H:%M')}",
        "",
    ]
    total = 0
    for image in detail.images:
        open_pins = sorted(
            (p for p in detail.pins if p.imageId == image.id and p.status == "open" and p.type != "like"),
            key=lambda p: p.number,
        )
        if not open_pins:
            continue
        suffix = " (superseded)" if image.superseded else ""
        lines.append(f"== {image.title}{suffix} ==")
        for pin in open_pins:
            first = pin.comments[0] if pin.comments else None
            replies = len(pin.comments) - 1 if pin.comments else 0
            text = first.text if first else "(no comment)"
            author = f" — {first.authorName}" if first else ""
            reply_note = ""
            if replies > 0:
                reply_note = f" ({replies} {'reply' if replies == 1 else 'replies'})"
            lines.append(f"#{pin.number} [{pin.type}] {text}{author}{reply_note}")
            total += 1
        lines.append("")
    if total == 0:
        lines.append("No open pins.")
    return "\n".join(lines).rstrip() + "\n"
