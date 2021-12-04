""" bmap: static beatmap info (thumbnails, previews, etc.) """
from fastapi import APIRouter
from fastapi import status
from fastapi.requests import Request
from fastapi.responses import RedirectResponse


router = APIRouter(prefix="/map", tags=["Beatmaps"])

# for now, just send everything to osu!
# eventually if we do bmap submission, we'll need this.
@router.get("/{file_path:path}")
async def everything(request: Request):
    return RedirectResponse(
        url=f"https://b.ppy.sh{request['path']}",
        status_code=status.HTTP_301_MOVED_PERMANENTLY,
    )
