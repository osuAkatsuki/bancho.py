# type: ignore
from __future__ import annotations

from fastapi import APIRouter

from . import players


apiv2_router = APIRouter(tags=["API-v2"], prefix="/v2")

apiv2_router.include_router(players.router)
