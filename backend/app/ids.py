"""Id generation for new rows, mirroring the mock's `prefix_<random>` scheme
(`u_demo`, `r_lakeside`, etc. are seed ids; runtime ids just need to be
unique and carry the same readable prefix)."""

from __future__ import annotations

import secrets
import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def new_guest_token() -> str:
    """A guest (share link) token. It is the only credential on the link, so
    it is 128 bits from the OS random source, not the 48 bits `new_id` keeps.
    `token_urlsafe` uses only `A-Z a-z 0-9 - _`, which is safe in a path
    segment. Existing tokens (seeded demo tokens, rooms created before this
    change) are unaffected: nothing parses the token's format."""
    return f"g_{secrets.token_urlsafe(16)}"
