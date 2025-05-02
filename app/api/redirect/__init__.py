from __future__ import annotations

from fastapi import APIRouter

from . import beatmaps
from . import difficulty_rating

redirect_router = APIRouter()

redirect_router.include_router(beatmaps.router)
redirect_router.include_router(difficulty_rating.router)
