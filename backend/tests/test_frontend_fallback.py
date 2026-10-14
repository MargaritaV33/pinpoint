"""Tests for the static frontend serving + SPA fallback added in issue #8.

`app.main.FRONTEND_DIST` points at `/app/frontend_dist` in the Docker image,
which does not exist in this test environment — so these tests monkeypatch
it to a small fixture directory instead of requiring a real `npm run build`,
and exercise `app.main.serve_frontend` through the same `TestClient` the
other backend tests use.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app


@pytest.fixture()
def frontend_dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    dist = tmp_path / "frontend_dist"
    dist.mkdir()
    (dist / "_shell.html").write_text("<html><body>shell</body></html>")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.abc123.js").write_text("console.log('hi');")
    monkeypatch.setattr(main_module, "FRONTEND_DIST", dist)
    return dist


def test_unmatched_path_serves_spa_shell(frontend_dist: Path) -> None:
    client = TestClient(app)

    response = client.get("/foo/bar")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "shell" in response.text


def test_real_asset_is_served_from_disk(frontend_dist: Path) -> None:
    client = TestClient(app)

    response = client.get("/assets/app.abc123.js")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(("text/javascript", "application/javascript"))
    assert "console.log" in response.text


def test_pins_without_id_is_a_real_404_not_the_shell(frontend_dist: Path) -> None:
    client = TestClient(app)

    response = client.get("/pins")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Not Found"}


def test_unmatched_rooms_subpath_is_a_real_404_not_the_shell(frontend_dist: Path) -> None:
    client = TestClient(app)

    response = client.get("/rooms/does-not-exist/nonexistent-subpath")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Not Found"}


def test_health_is_unaffected(frontend_dist: Path) -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "commit": None}


def test_without_a_frontend_build_unmatched_paths_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Local, non-Docker dev has no frontend_dist at all — the fallback
    route must not error, just 404 like any other unmatched path."""
    monkeypatch.setattr(main_module, "FRONTEND_DIST", tmp_path / "does-not-exist")
    client = TestClient(app)

    response = client.get("/foo/bar")

    assert response.status_code == 404


# -- the SPA fallback never serves a file outside the build (issue #26 audit) -------
# `serve_frontend` resolves the requested path and requires it to stay inside
# FRONTEND_DIST (`is_relative_to`). Without that guard a request for
# `../secret.txt` would return a file next to the build directory. These pin the
# guard; they passed before the audit too (no code change), they exist so a
# later refactor of the fallback cannot drop it unnoticed.

@pytest.mark.parametrize("path", ["/..%2fsecret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt"])
def test_path_traversal_does_not_leave_the_build_directory(frontend_dist: Path, path: str) -> None:
    (frontend_dist.parent / "secret.txt").write_text("outside-the-build")
    client = TestClient(app)

    response = client.get(path)

    assert "outside-the-build" not in response.text
    # Falls back to the shell (200) or 404s; both are fine, leaking is not.
    assert response.status_code in (200, 404)
