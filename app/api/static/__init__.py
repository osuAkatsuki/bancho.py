from __future__ import annotations

from fastapi import APIRouter

from . import beatmaps
from . import screenshots

web_router = APIRouter()

web_router.include_router(beatmaps.router, prefix="/d")
web_router.include_router(screenshots.router, prefix="/ss")
