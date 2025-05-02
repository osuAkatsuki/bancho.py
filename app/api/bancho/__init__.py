from __future__ import annotations

from fastapi import APIRouter

from . import users

web_router = APIRouter(tags=["Bancho"])

web_router.include_router(users.router)
