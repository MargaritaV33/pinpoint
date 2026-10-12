"""Id generation for new rows, mirroring the mock's `prefix_<random>` scheme
(`u_demo`, `r_lakeside`, etc. are seed ids; runtime ids just need to be
unique and carry the same readable prefix)."""

from __future__ import annotations

import uuid


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
