from __future__ import annotations

from fastapi import APIRouter

from . import clans
from . import maps
from . import players
from . import scores

apiv2_router = APIRouter(tags=["API v2"], prefix="/v2")

apiv2_router.include_router(clans.router)
apiv2_router.include_router(maps.router)
apiv2_router.include_router(players.router)
apiv2_router.include_router(scores.router)
