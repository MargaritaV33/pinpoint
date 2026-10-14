import pytest
from fastapi.testclient import TestClient

from app import config as config_module
from app.main import app


def test_health_returns_ok_with_no_commit_when_render_git_commit_is_unset() -> None:
    """Locally, in Compose, and in CI's own test jobs, RENDER_GIT_COMMIT is
    never set, so `commit` reports null — see issue #13."""
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "commit": None}


def test_health_reports_the_deployed_commit_when_render_git_commit_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On a real Render deploy, RENDER_GIT_COMMIT is injected automatically
    and /health must echo it back, for CI's `deploy` job to poll against
    `github.sha`."""
    monkeypatch.setattr(config_module.settings, "render_git_commit", "a" * 40)
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "commit": "a" * 40}
