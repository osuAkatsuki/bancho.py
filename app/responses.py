from __future__ import annotations

from typing import Mapping
from typing import Optional
from typing import TypeVar
from typing import Union

from fastapi import status
from fastapi.responses import ORJSONResponse

import app.settings
from app.objects.achievement import Achievement
from app.objects.beatmap import Beatmap
from app.objects.player import ModeData
from app.objects.player import Player
from app.objects.score import Score


def osu_registration_failure(errors: Mapping[str, list[str]]) -> ORJSONResponse:
    """Reformat the errors mapping into a response for the osu! client."""
    errors = {k: ["\n".join(v)] for k, v in errors.items()}

    return ORJSONResponse(
        content={"form_error": {"user": errors}},
        status_code=status.HTTP_400_BAD_REQUEST,
    )


T = TypeVar("T", bound=Union[int, float])


def chart_entry(name: str, before: Optional[T], after: T) -> str:
    return f"{name}Before:{before or ''}|{name}After:{after}"


def score_submission_charts(
    player: Player,
    beatmap: Beatmap,
    new_stats: ModeData,
    old_stats: ModeData,
    new_score: Score,
    old_score: Score,
    achievements_unlocked: list[Achievement],
) -> bytes:
    """Construct the ranking charts returned in /web/osu-submit-modular-selector.php."""
    if old_score:
        beatmap_ranking_chart_entries = (
            chart_entry(
                "rank",
                before=old_score.rank,
                after=new_score.rank,  # type: ignore
            ),
            chart_entry(
                "rankedScore",
                before=old_score.score,
                after=new_score.score,
            ),
            chart_entry(
                "totalScore",
                before=old_score.score,
                after=new_score.score,
            ),
            chart_entry(
                "maxCombo",
                before=old_score.max_combo,
                after=new_score.max_combo,
            ),
            chart_entry(
                "accuracy",
                round(old_score.acc, 2),
                round(new_score.acc, 2),
            ),
            chart_entry(
                "pp",
                before=old_score.pp,
                after=new_score.pp,
            ),
        )
    else:
        # no previous best score
        beatmap_ranking_chart_entries = (
            chart_entry(
                "rank",
                before=None,
                after=new_score.rank,  # type: ignore
            ),
            chart_entry(
                "rankedScore",
                before=None,
                after=new_score.score,
            ),
            chart_entry(
                "totalScore",
                before=None,
                after=new_score.score,
            ),
            chart_entry(
                "maxCombo",
                before=None,
                after=new_score.max_combo,
            ),
            chart_entry(
                "accuracy",
                before=None,
                after=round(new_score.acc, 2),
            ),
            chart_entry(
                "pp",
                before=None,
                after=new_score.pp,
            ),
        )

    overall_ranking_chart_entries = (
        chart_entry(
            "rank",
            before=old_stats.rank,
            after=new_stats.rank,
        ),
        chart_entry(
            "rankedScore",
            before=old_stats.rscore,
            after=new_stats.rscore,
        ),
        chart_entry(
            "totalScore",
            before=old_stats.tscore,
            after=new_stats.tscore,
        ),
        chart_entry(
            "maxCombo",
            before=old_stats.max_combo,
            after=new_stats.max_combo,
        ),
        chart_entry(
            "accuracy",
            before=round(old_stats.acc, 2),
            after=round(new_stats.acc, 2),
        ),
        chart_entry(
            "pp",
            before=old_stats.pp,
            after=new_stats.pp,
        ),
    )

    submission_charts = [
        # beatmap info chart
        f"beatmapId:{beatmap.id}",
        f"beatmapSetId:{beatmap.set_id}",
        f"beatmapPlaycount:{beatmap.plays}",
        f"beatmapPasscount:{beatmap.passes}",
        f"approvedDate:{beatmap.last_update}",
        "\n",
        # beatmap ranking chart
        "chartId:beatmap",
        f"chartUrl:https://osu.{app.settings.DOMAIN}/beatmapsets/{beatmap.set_id}",
        "chartName:Beatmap Ranking",
        *beatmap_ranking_chart_entries,
        f"onlineScoreId:{new_score.id}",
        "\n",
        # overall ranking chart
        "chartId:overall",
        f"chartUrl:https://{app.settings.DOMAIN}/u/{player.id}",
        "chartName:Overall Ranking",
        *overall_ranking_chart_entries,
        f"achievements-new:{'/'.join(map(repr, achievements_unlocked))}",
    ]

    return "|".join(submission_charts).encode()
