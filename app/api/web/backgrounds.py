from __future__ import annotations

from fastapi.responses import ORJSONResponse
from fastapi.responses import Response
from fastapi.routing import APIRouter

import app.settings

router = APIRouter()


@router.get("/osu-getseasonal.php")
async def osuSeasonal() -> Response:
    return ORJSONResponse(app.settings.SEASONAL_BGS)
