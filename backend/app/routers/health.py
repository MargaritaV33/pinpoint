"""Health check endpoint, used to confirm the service is up and serving.

Also reports the deployed commit (`settings.render_git_commit`), which
Render sets from `RENDER_GIT_COMMIT` on a real deploy and which is `None`
everywhere else (local dev, Compose, CI's own test jobs) — see
`app/config.py` and issue #13. CI's `deploy` job polls this field after
calling the Render deploy hook, to confirm the live service is serving the
commit that triggered the run.
"""

from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health")
def get_health() -> dict[str, str | None]:
    return {"status": "ok", "commit": settings.render_git_commit}
