from __future__ import annotations

from fastapi.responses import Response
from fastapi.routing import APIRouter

router = APIRouter()


@router.get("/p/doyoureallywanttoaskpeppy")
async def peppyDMHandler() -> Response:
    return Response(
        content=(
            b"This user's ID is usually peppy's (when on bancho), "
            b"and is blocked from being messaged by the osu! client."
        ),
    )
