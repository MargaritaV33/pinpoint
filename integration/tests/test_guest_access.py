"""Guest access and permission boundaries.

Three independent checks:
  - an unknown guest token 404s
  - a *static* read of `openapi.yaml` confirming the Guest-tagged paths are
    exactly the five intended ones (no HTTP call — there is no endpoint for
    a guest to even attempt resolving a pin, uploading an image, or closing
    a room through, so there is nothing to call to prove that)
  - cross-studio room access 404s, not 403s (the contract's existing
    convention for "not yours")
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx

from conftest import create_room, create_studio, get_room

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "openapi.yaml"


def test_unknown_guest_token_returns_404(client: httpx.Client) -> None:
    response = client.get("/guest/this-token-does-not-exist")
    assert response.status_code == 404, response.text


def test_guest_tagged_paths_are_exactly_the_five_named_ones() -> None:
    text = OPENAPI_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()

    path_re = re.compile(r"^  (/\S+):$")
    method_re = re.compile(r"^    (get|post|put|patch|delete):$")
    tags_re = re.compile(r"^\s*tags:\s*\[(.+?)\]")

    current_path: str | None = None
    current_method: str | None = None
    guest_operations: set[tuple[str, str]] = set()

    for line in lines:
        path_match = path_re.match(line)
        if path_match:
            current_path = path_match.group(1)
            current_method = None
            continue

        method_match = method_re.match(line)
        if method_match:
            current_method = method_match.group(1)
            continue

        tags_match = tags_re.match(line)
        if tags_match and current_path is not None and current_method is not None:
            tags = [t.strip() for t in tags_match.group(1).split(",")]
            if "Guest" in tags:
                guest_operations.add((current_method.upper(), current_path))

    expected = {
        ("GET", "/guest/{guestToken}"),
        ("POST", "/guest/{guestToken}/pins"),
        ("POST", "/guest/{guestToken}/pins/{pinId}/comments"),
        ("POST", "/guest/{guestToken}/approve"),
        ("GET", "/guest/{guestToken}/images/{imageId}/file"),
    }
    assert guest_operations == expected


def test_cross_studio_room_access_returns_404_not_403(client: httpx.Client) -> None:
    studio_a = create_studio(client)
    room = create_room(client, studio_a["token"])

    studio_b = create_studio(client)
    response = get_room(client, studio_b["token"], room["id"])
    assert response.status_code == 404, response.text
