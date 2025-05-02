from __future__ import annotations

from typing import Literal

from fastapi.requests import Request
from fastapi.responses import Response
from fastapi.routing import APIRouter

router = APIRouter()


@router.get("/check-updates.php")
async def checkUpdates(
    request: Request,
    action: Literal["check", "path", "error"],
    stream: Literal["cuttingedge", "stable40", "beta40", "stable"],
) -> Response:
    return Response(b"")
