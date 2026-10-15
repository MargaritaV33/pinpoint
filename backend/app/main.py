"""FastAPI application entry point.

Only wires up routers, CORS, and (new in issue #8) serving the built
frontend; no product logic lives here.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.access_log import install_access_log
from app.config import settings
from app.routers import auth, guest, health, images, pins, rooms

app = FastAPI(title="Pinpoint API")

# JSON access log + X-Request-Id on every response (issue #38, ops/observability.md).
install_access_log(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(images.router)
app.include_router(pins.router)
app.include_router(guest.router)

# --- Static frontend build + SPA fallback (issue #8) ------------------
#
# The Dockerfile copies the frontend's built `.output/public` to
# `/app/frontend_dist` (three levels above this file: app/ -> backend/ ->
# /app/). In local, non-Docker dev (`make run`) that directory does not
# exist — the frontend runs via its own Vite dev server instead (see root
# README's two-terminal recipe) — so the routes below simply 404 for
# anything that isn't a real API route, same as before this issue.
#
# Registered as a module-level name (not a constant baked into the route
# closure) so tests can point it at a fixture directory without a real
# frontend build.
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend_dist"

# The exact set of router prefixes in backend/app/routers/ (confirmed by
# reading every @router.get/post/patch decorator there). The SPA fallback
# below must never shadow a real API route, or a real API prefix with no
# matching sub-route — so any path whose first segment is one of these goes
# through FastAPI's normal "no route matched" 404 instead of the SPA shell.
_API_PREFIXES = ("/health", "/auth", "/rooms", "/images", "/pins", "/guest")


def _is_api_prefixed(path: str) -> bool:
    first_segment = path.strip("/").split("/", 1)[0]
    return f"/{first_segment}" in _API_PREFIXES


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str) -> FileResponse:
    """Serve a built frontend asset if one exists on disk, else fall back
    to the static SPA shell — unless the path belongs to a real API prefix,
    in which case it is a genuine 404, not a frontend route.

    Registered after every `app.include_router(...)` call above, so a real
    API route always matches first; this only ever runs for paths none of
    those routers claimed.
    """
    request_path = f"/{full_path}"
    if _is_api_prefixed(request_path):
        raise HTTPException(status_code=404)

    if not FRONTEND_DIST.is_dir():
        raise HTTPException(status_code=404)

    if full_path:
        candidate = (FRONTEND_DIST / full_path).resolve()
        dist_root = FRONTEND_DIST.resolve()
        if candidate.is_relative_to(dist_root) and candidate.is_file():
            return FileResponse(candidate)

    shell = FRONTEND_DIST / "_shell.html"
    if not shell.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(shell, media_type="text/html")
