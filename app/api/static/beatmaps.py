from __future__ import annotations

from fastapi import status
from fastapi.param_functions import Path
from fastapi.responses import RedirectResponse
from fastapi.responses import Response
from fastapi.routing import APIRouter

import app.settings

router = APIRouter()


@router.get("/{map_set_id}")
async def get_osz(
    map_set_id: str = Path(...),
) -> Response:
    """Handle a map download request (osu.ppy.sh/d/*)."""
    no_video = map_set_id[-1] == "n"
    if no_video:
        map_set_id = map_set_id[:-1]

    query_str = f"{map_set_id}?n={int(not no_video)}"

    return RedirectResponse(
        url=f"{app.settings.MIRROR_DOWNLOAD_ENDPOINT}/{query_str}",
        status_code=status.HTTP_301_MOVED_PERMANENTLY,
    )
