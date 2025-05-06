from __future__ import annotations

from fastapi import APIRouter

from . import beatmaps
from . import screenshots

static_router = APIRouter()

static_router.include_router(beatmaps.router, prefix="/d")
static_router.include_router(screenshots.router, prefix="/ss")
