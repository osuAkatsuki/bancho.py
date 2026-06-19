from __future__ import annotations

from fastapi import APIRouter

from . import users

bancho_router = APIRouter(tags=["Bancho"])

bancho_router.include_router(users.router)
