from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

from py3rijndael import Pkcs7Padding
from py3rijndael import RijndaelCbc
from starlette.datastructures import FormData
from starlette.datastructures import UploadFile as StarletteUploadFile

import app.state.services
from app import repositories
from app import usecases
from app.constants.gamemodes import GameMode
from app.objects.beatmap import Beatmap
from app.objects.player import Player
from app.objects.score import Score
from app.objects.score import SubmissionStatus

## create


async def submit(score: Score, beatmap: Beatmap, player: Player) -> int:
    """Submit a score to the database."""
    if score.status == SubmissionStatus.BEST:
        # this score is our best score.
        # update any preexisting personal best
        # records with SubmissionStatus.SUBMITTED.
        await app.state.services.database.execute(
            "UPDATE scores SET status = 1 "
            "WHERE status = 2 AND map_md5 = :map_md5 "
            "AND userid = :user_id AND mode = :mode",
            {
                "map_md5": beatmap.md5,
                "user_id": player.id,
                "mode": score.mode,
            },
        )

    score_id = await app.state.services.database.execute(
        "INSERT INTO scores "
        "VALUES (NULL, "
        ":map_md5, :score, :pp, :acc, "
        ":max_combo, :mods, :n300, :n100, "
        ":n50, :nmiss, :ngeki, :nkatu, "
        ":grade, :status, :mode, :play_time, "
        ":time_elapsed, :client_flags, :user_id, :perfect, "
        ":checksum)",
        {
            "map_md5": beatmap.md5,
            "score": score.score,
            "pp": score.pp,
            "acc": score.acc,
            "max_combo": score.max_combo,
            "mods": score.mods,
            "n300": score.n300,
            "n100": score.n100,
            "n50": score.n50,
            "nmiss": score.nmiss,
            "ngeki": score.ngeki,
            "nkatu": score.nkatu,
            "grade": score.grade.name,
            "status": score.status,
            "mode": score.mode,
            "play_time": score.server_time,
            "time_elapsed": score.time_elapsed,
            "client_flags": score.client_flags,
            "user_id": player.id,
            "perfect": score.perfect,
            "checksum": score.client_checksum,
        },
    )
    return score_id


## read


def parse_form_data_score_params(
    score_data: FormData,
) -> Optional[tuple[bytes, StarletteUploadFile]]:
    """Parse the score data, and replay file
    from the form data's 'score' parameters."""
    try:
        score_parts = score_data.getlist("score")
        assert len(score_parts) == 2, "Invalid score data"

        score_data_b64 = score_data.getlist("score")[0]
        assert isinstance(score_data_b64, str), "Invalid score data"
        replay_file = score_data.getlist("score")[1]
        assert isinstance(replay_file, StarletteUploadFile), "Invalid replay data"
    except AssertionError as exc:
        # TODO: perhaps better logging?
        logging.error(f"Failed to validate score multipart data: ({exc.args[0]})")
        return None
    else:
        return (
            score_data_b64.encode(),
            replay_file,
        )


def decrypt_score_aes_data(
    # to decode
    score_data_b64: bytes,
    client_hash_b64: bytes,
    # used for decoding
    iv_b64: bytes,
    osu_version: str,
) -> tuple[list[str], str]:
    """Decrypt the base64'ed score data."""
    # TODO: perhaps this should return TypedDict?

    # attempt to decrypt score data
    aes = RijndaelCbc(
        key=f"osu!-scoreburgr---------{osu_version}".encode(),
        iv=base64.b64decode(iv_b64),
        padding=Pkcs7Padding(32),
        block_size=32,
    )

    score_data = aes.decrypt(base64.b64decode(score_data_b64)).decode().split(":")
    client_hash_decoded = aes.decrypt(base64.b64decode(client_hash_b64)).decode()

    # score data is delimited by colons (:).
    return score_data, client_hash_decoded


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
        score_args: usecases.performance.ScoreDifficultyParams = {
            "acc": score.acc,
            "combo": score.max_combo,
            "nmiss": score.nmiss,
        }
    else:  # mode_vn == 3
        score_args: usecases.performance.ScoreDifficultyParams = {
            "score": score.score,
        }

    result = usecases.performance.calculate_performances(
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

        score.prev_best = await repositories.scores.fetch(res["id"])
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


def calculate_accuracy(
    vanilla_mode: int,
    n300: int,
    n100: int,
    n50: int,
    ngeki: int,
    nkatu: int,
    nmiss: int,
) -> float:
    """Calculate the accuracy of our score."""
    if vanilla_mode == 0:  # osu!
        total = n300 + n100 + n50 + nmiss

        if total == 0:
            return 0.0

        return (
            100.0 * ((n300 * 300.0) + (n100 * 100.0) + (n50 * 50.0)) / (total * 300.0)
        )

    elif vanilla_mode == 1:  # osu!taiko
        total = n300 + n100 + nmiss

        if total == 0:
            return 0.0

        return 100.0 * ((n100 * 0.5) + n300) / total

    elif vanilla_mode == 2:  # osu!catch
        total = n300 + n100 + n50 + nkatu + nmiss

        if total == 0:
            return 0.0

        return 100.0 * (n300 + n100 + n50) / total

    elif vanilla_mode == 3:  # osu!mania
        total = n300 + n100 + n50 + ngeki + nkatu + nmiss

        if total == 0:
            return 0.0

        return (
            100.0
            * (
                (n50 * 50.0)
                + (n100 * 100.0)
                + (nkatu * 200.0)
                + ((n300 + ngeki) * 300.0)
            )
            / (total * 300.0)
        )
    else:
        raise Exception(f"Invalid vanilla mode {vanilla_mode}")


## update


async def increment_replay_views(player_id: int, mode: int) -> None:
    # TODO: move replay views to be per-score rather than per-user

    await app.state.services.database.execute(
        f"UPDATE stats "
        "SET replay_views = replay_views + 1 "
        "WHERE id = :user_id AND mode = :mode",
        {"user_id": player_id, "mode": mode},
    )


## delete
