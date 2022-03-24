from __future__ import annotations

from pathlib import Path

import app.repositories.scores
import app.state.services
import app.usecases.performance  # maybe problem?
from app.constants.gamemodes import GameMode
from app.objects.beatmap import Beatmap
from app.objects.player import Player
from app.objects.score import Score
from app.objects.score import SubmissionStatus
from app.usecases.performance import ScoreDifficultyParams  # maybe problem?


async def calculate_placement(score: Score, beatmap: Beatmap) -> int:
    if score.mode >= GameMode.RELAX_OSU:
        scoring_metric = "pp"
        score_value = score.pp
    else:
        scoring_metric = "score"
        score_value = score.score

    better_scores = await app.state.services.database.fetch_val(
        "SELECT COUNT(*) AS c FROM scores s "
        "INNER JOIN users u ON u.id = s.userid "
        "WHERE s.map_md5 = :map_md5 AND s.mode = :mode "
        "AND s.status = 2 AND u.priv & 1 "
        f"AND s.{scoring_metric} > :score",
        {
            "map_md5": beatmap.md5,
            "mode": score.mode,
            "score": score_value,
        },
        column=0,  # COUNT(*)
    )

    # TODO: idk if returns none
    return better_scores + 1  # if better_scores is not None else 1


def calculate_performance(score: Score, osu_file_path: Path) -> tuple[float, float]:
    """Calculate PP and star rating for our score."""
    mode_vn = score.mode.as_vanilla

    if mode_vn in (0, 1, 2):
        score_args: ScoreDifficultyParams = {
            "acc": score.acc,
            "combo": score.max_combo,
            "nmiss": score.nmiss,
        }
    else:  # mode_vn == 3
        score_args: ScoreDifficultyParams = {
            "score": score.score,
        }

    result = app.usecases.performance.calculate_performances(
        osu_file_path=str(osu_file_path),
        mode=mode_vn,
        mods=int(score.mods),
        scores=[score_args],
    )

    return result[0]["performance"], result[0]["star_rating"]


async def calculate_status(score: Score, beatmap: Beatmap, player: Player) -> None:
    """Calculate the submission status of a submitted score."""
    # find any other `status = 2` scores we have
    # on the map. If there are any, store
    res = await app.state.services.database.fetch_one(
        "SELECT id, pp FROM scores "
        "WHERE userid = :user_id AND map_md5 = :map_md5 "
        "AND mode = :mode AND status = 2",
        {
            "user_id": player.id,
            "map_md5": beatmap.md5,
            "mode": score.mode,
        },
    )

    if res:
        # we have a score on the map.
        # save it as our previous best score.

        score.prev_best = await app.repositories.scores.fetch(res["id"])
        assert score.prev_best is not None

        # if our new score is better, update
        # both of our score's submission statuses.
        # NOTE: this will be updated in sql later on in submission
        if score.pp > res["pp"]:
            score.status = SubmissionStatus.BEST
            score.prev_best.status = SubmissionStatus.SUBMITTED
        else:
            score.status = SubmissionStatus.SUBMITTED
    else:
        # this is our first score on the map.
        score.status = SubmissionStatus.BEST


def calculate_accuracy(score: Score) -> float:
    """Calculate the accuracy of our score."""
    mode_vn = score.mode.as_vanilla

    if mode_vn == 0:  # osu!
        total = score.n300 + score.n100 + score.n50 + score.nmiss

        if total == 0:
            return 0.0

        return (
            100.0
            * ((score.n300 * 300.0) + (score.n100 * 100.0) + (score.n50 * 50.0))
            / (total * 300.0)
        )

    elif mode_vn == 1:  # osu!taiko
        total = score.n300 + score.n100 + score.nmiss

        if total == 0:
            return 0.0

        return 100.0 * ((score.n100 * 0.5) + score.n300) / total

    elif mode_vn == 2:  # osu!catch
        total = score.n300 + score.n100 + score.n50 + score.nkatu + score.nmiss

        if total == 0:
            return 0.0

        return 100.0 * (score.n300 + score.n100 + score.n50) / total

    elif mode_vn == 3:  # osu!mania
        total = (
            score.n300
            + score.n100
            + score.n50
            + score.ngeki
            + score.nkatu
            + score.nmiss
        )

        if total == 0:
            return 0.0

        return (
            100.0
            * (
                (score.n50 * 50.0)
                + (score.n100 * 100.0)
                + (score.nkatu * 200.0)
                + ((score.n300 + score.ngeki) * 300.0)
            )
            / (total * 300.0)
        )
    else:
        raise Exception(f"Invalid vanilla mode {mode_vn}")


""" Methods for updating a score. """


async def increment_replay_views(player_id: int, mode: int) -> None:
    # TODO: move replay views to be per-score rather than per-user

    await app.state.services.database.execute(
        f"UPDATE stats "
        "SET replay_views = replay_views + 1 "
        "WHERE id = :user_id AND mode = :mode",
        {"user_id": player_id, "mode": mode},
    )
