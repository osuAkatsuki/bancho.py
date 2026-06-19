from __future__ import annotations

from fastapi import APIRouter

from . import backgrounds
from . import beatmaps
from . import channels
from . import comments
from . import connect
from . import direct
from . import favourites
from . import friends
from . import lastfm
from . import leaderboards
from . import peppy
from . import ratings
from . import replays
from . import scoring
from . import screenshots
from . import updates

# Unhandled endpoints:
# POST /osu-error.php
# POST /osu-session.php
# POST /osu-osz2-bmsubmit-post.php
# POST /osu-osz2-bmsubmit-upload.php
# GET /osu-osz2-bmsubmit-getid.php
# GET /osu-get-beatmap-topic.php

web_router = APIRouter(tags=["Web"], prefix="/web")

web_router.include_router(backgrounds.router)
web_router.include_router(beatmaps.router)
web_router.include_router(channels.router)
web_router.include_router(comments.router)
web_router.include_router(connect.router)
web_router.include_router(direct.router)
web_router.include_router(favourites.router)
web_router.include_router(friends.router)
web_router.include_router(lastfm.router)
web_router.include_router(leaderboards.router)
web_router.include_router(peppy.router)
web_router.include_router(ratings.router)
web_router.include_router(replays.router)
web_router.include_router(scoring.router)
web_router.include_router(screenshots.router)
web_router.include_router(updates.router)
