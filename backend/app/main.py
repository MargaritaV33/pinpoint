"""FastAPI application entry point.

Only wires up routers; no product logic lives here. See AGENTS.md and
product-spec.md for what comes later.
"""

from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="Pinpoint API")

app.include_router(health.router)
