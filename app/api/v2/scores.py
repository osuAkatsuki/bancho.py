"""bancho.py's v2 apis for interacting with scores"""

from __future__ import annotations

import dataclasses
from typing import Annotated
from typing import cast
from urllib.parse import quote

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Response
from fastapi import status
from fastapi.param_functions import Query

from app.api import dependencies as api_dependencies
from app.api.v2.common import actors
from app.api.v2.common import responses
from app.api.v2.common.responses import Failure
from app.api.v2.common.responses import Success
from app.api.v2.models.scores import Score
from app.api.v2.models.scores import ScoreBeatmap
from app.api.v2.models.scores import ScoreDetail
from app.api.v2.models.scores import ScorePlayer
from app.repositories.users import User
from app.services.replays import ReplayService
from app.services.scores import ScoresService

router = APIRouter()


@router.get("/scores")
async def get_all_scores(
    *,
    map_md5: str | None = None,
    mods: int | None = None,
    status: int | None = None,
    mode: int | None = None,
    user_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    actor: Annotated[
        User | None,
        Depends(actors.get_optional_actor),
    ],
    scores_service: Annotated[
        ScoresService,
        Depends(api_dependencies.get_scores_service),
    ],
) -> Success[list[Score]] | Failure:
    listing = await scores_service.fetch_scores(
        map_md5=map_md5,
        mods=mods,
        status=status,
        mode=mode,
        user_id=user_id,
        page=page,
        page_size=page_size,
        viewer=actor,
    )

    response = [Score.model_validate(rec) for rec in listing.scores]

    return responses.success(
        content=response,
        meta={
            "total": listing.total_scores,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/scores/{score_id}")
async def get_score(
    score_id: int,
    *,
    actor: Annotated[
        User | None,
        Depends(actors.get_optional_actor),
    ],
    scores_service: Annotated[
        ScoresService,
        Depends(api_dependencies.get_scores_service),
    ],
) -> Success[ScoreDetail] | Failure:
    data = await scores_service.fetch_score_with_context(score_id, viewer=actor)
    if data is None:
        return responses.failure(
            message="Score not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    response = ScoreDetail.model_validate(
        {
            **dataclasses.asdict(data.score),
            "beatmap": ScoreBeatmap.model_validate(data.beatmap),
            "player": ScorePlayer(
                id=data.player.id,
                name=data.player.name,
                country=data.player.country,
                clan_id=data.player.clan_id or None,
                clan_name=data.clan.name if data.clan is not None else None,
                clan_tag=data.clan.tag if data.clan is not None else None,
            ),
        },
    )
    return responses.success(response)


@router.get("/scores/{score_id}/replay")
async def download_score_replay(
    score_id: int,
    *,
    actor: Annotated[
        User | None,
        Depends(actors.get_optional_actor),
    ],
    replay_service: Annotated[
        ReplayService,
        Depends(api_dependencies.get_replay_service),
    ],
) -> Response:
    replay = await replay_service.build_full_replay(score_id, viewer=actor)
    if replay is None:
        return cast(
            Response,
            responses.failure(
                message="Replay not found.",
                status_code=status.HTTP_404_NOT_FOUND,
            ),
        )

    # both the plain (ascii) and RFC 5987 encodings, for unicode metadata
    ascii_filename = replay.filename.encode("ascii", "replace").decode()
    return Response(
        replay.data,
        media_type="application/x-osu-replay",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_filename}"; '
                f"filename*=UTF-8''{quote(replay.filename)}"
            ),
        },
    )
