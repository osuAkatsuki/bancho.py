""" bmap: static beatmap info (thumbnails, previews, etc.) """
from __future__ import annotations

from fastapi import APIRouter
from fastapi import status
from fastapi.requests import Request
from fastapi.responses import RedirectResponse

# import app.settings

router = APIRouter(tags=["Beatmaps"])

# @router.get("/preview/{beatmap_set_id}.mp3")
# async def preview(beatmap_set_id: int) -> RedirectResponse:
#     """Fetch an audio preview for a beatmap set."""
#     USING_MINO = "catboy.best" in app.settings.MIRROR_URL

#     if USING_MINO:
#         # mino provides full-quality audio previews
#         url = f"https://catboy.best/api/preview/audio/{beatmap_set_id}?set=1"
#     else:
#         # official osu! servers use lossy compression
#         url = f"https://b.ppy.sh/preview/{beatmap_set_id}.mp3"

#     return RedirectResponse(url, status_code=status.HTTP_301_MOVED_PERMANENTLY)


# forward any unmatched request to osu!
# eventually if we do bmap submission, we'll need this.
@router.get("/{file_path:path}")
async def everything(request: Request):
    return RedirectResponse(
        url=f"https://b.ppy.sh{request['path']}",
        status_code=status.HTTP_301_MOVED_PERMANENTLY,
    )
