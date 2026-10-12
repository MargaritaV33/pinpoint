"""FastAPI application entry point.

Only wires up routers and CORS; no product logic lives here.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, guest, health, images, pins, rooms

app = FastAPI(title="Pinpoint API")

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
