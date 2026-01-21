from __future__ import annotations

from fastapi import status
from fastapi.param_functions import Path
from fastapi.requests import Request
from fastapi.responses import RedirectResponse
from fastapi.responses import Response
from fastapi.routing import APIRouter

import app.settings

router = APIRouter()


if app.settings.REDIRECT_OSU_URLS:
    # NOTE: this will likely be removed with the addition of a frontend.
    async def osu_redirect(request: Request, _: int = Path(...)) -> Response:
        return RedirectResponse(
            url=f"https://osu.ppy.sh{request['path']}",
            status_code=status.HTTP_301_MOVED_PERMANENTLY,
        )

    for pattern in (
        "/beatmapsets/{_}",
        "/beatmaps/{_}",
        "/beatmapsets/{_}/discussion",
        "/community/forums/topics/{_}",
    ):
        router.get(pattern)(osu_redirect)
