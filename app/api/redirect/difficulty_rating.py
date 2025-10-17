from __future__ import annotations

from fastapi import status
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from fastapi.responses import Response
from fastapi.routing import APIRouter

router = APIRouter()


@router.post("/difficulty-rating")
async def difficultyRatingHandler(request: Request) -> Response:
    return RedirectResponse(
        url=f"https://osu.ppy.sh{request['path']}",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )
