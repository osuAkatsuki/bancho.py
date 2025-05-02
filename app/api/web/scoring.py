from __future__ import annotations

import copy
import hashlib
from pathlib import Path as SystemPath
from typing import Any

from fastapi.datastructures import FormData
from fastapi.param_functions import File
from fastapi.param_functions import Form
from fastapi.param_functions import Header
from fastapi.requests import Request
from fastapi.responses import Response
from fastapi.routing import APIRouter
from starlette.datastructures import UploadFile as StarletteUploadFile

import app.packets
import app.settings
import app.state
import app.utils
from app import encryption
from app._typing import UNSET
from app.constants.gamemodes import GameMode
from app.logging import Ansi
from app.logging import log
from app.objects.beatmap import Beatmap
from app.objects.beatmap import RankedStatus
from app.objects.beatmap import ensure_osu_file_is_available
from app.objects.score import Grade
from app.objects.score import Score
from app.objects.score import SubmissionStatus
from app.repositories import stats as stats_repo
from app.repositories.achievements import Achievement
from app.usecases import achievements as achievements_usecases
from app.usecases import user_achievements as user_achievements_usecases

REPLAYS_PATH = SystemPath.cwd() / ".data/osr"


router = APIRouter()


def parse_form_data_score_params(
    score_data: FormData,
) -> tuple[bytes, StarletteUploadFile] | None:
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
        log(f"Failed to validate score multipart data: ({exc.args[0]})", Ansi.LRED)
        return None
    else:
        return (
            score_data_b64.encode(),
            replay_file,
        )


def chart_entry(name: str, before: float | None, after: float | None) -> str:
    return f"{name}Before:{before or ''}|{name}After:{after or ''}"


def format_achievement_string(file: str, name: str, description: str) -> str:
    return f"{file}+{name}+{description}"


@router.post("/osu-submit-modular-selector.php")
async def osuSubmitModularSelector(
    request: Request,
    # TODO: should token be allowed
    # through but ac'd if not found?
    # TODO: validate token format
    # TODO: save token in the database
    token: str = Header(...),
    # TODO: do ft & st contain pauses?
    exited_out: bool = Form(..., alias="x"),
    fail_time: int = Form(..., alias="ft"),
    visual_settings_b64: bytes = Form(..., alias="fs"),
    updated_beatmap_hash: str = Form(..., alias="bmk"),
    storyboard_md5: str | None = Form(None, alias="sbk"),
    iv_b64: bytes = Form(..., alias="iv"),
    unique_ids: str = Form(..., alias="c1"),
    score_time: int = Form(..., alias="st"),
    pw_md5: str = Form(..., alias="pass"),
    osu_version: str = Form(..., alias="osuver"),
    client_hash_b64: bytes = Form(..., alias="s"),
    fl_cheat_screenshot: bytes | None = File(None, alias="i"),
) -> Response:
    """Handle a score submission from an osu! client with an active session."""

    if fl_cheat_screenshot:
        stacktrace = app.utils.get_appropriate_stacktrace()
        await app.state.services.log_strange_occurrence(stacktrace)

    # NOTE: the bancho protocol uses the "score" parameter name for both
    # the base64'ed score data, and the replay file in the multipart
    # starlette/fastapi do not support this, so we've moved it out
    score_parameters = parse_form_data_score_params(await request.form())
    if score_parameters is None:
        return Response(b"")

    # extract the score data and replay file from the score data
    score_data_b64, replay_file = score_parameters

    # decrypt the score data (aes)
    score_data, client_hash_decoded = encryption.decrypt_score_aes_data(
        score_data_b64,
        client_hash_b64,
        iv_b64,
        osu_version,
    )

    # fetch map & player

    bmap_md5 = score_data[0]
    bmap = await Beatmap.from_md5(bmap_md5)
    if not bmap:
        # Map does not exist, most likely unsubmitted.
        return Response(b"error: beatmap")

    # if the client has supporter, a space is appended
    # but usernames may also end with a space, which must be preserved
    username = score_data[1]
    if username[-1] == " ":
        username = username[:-1]

    player = await app.state.sessions.players.from_login(username, pw_md5)
    if not player:
        # Player is not online, return nothing so that their
        # client will retry submission when they log in.
        return Response(b"")

    # parse the score from the remaining data
    score = Score.from_submission(score_data[2:])

    # attach bmap & player
    score.bmap = bmap
    score.player = player

    ## perform checksum validation

    unique_id1, unique_id2 = unique_ids.split("|", maxsplit=1)
    unique_id1_md5 = hashlib.md5(unique_id1.encode()).hexdigest()
    unique_id2_md5 = hashlib.md5(unique_id2.encode()).hexdigest()

    try:
        assert player.client_details is not None

        if osu_version != f"{player.client_details.osu_version.date:%Y%m%d}":
            raise ValueError("osu! version mismatch")

        if client_hash_decoded != player.client_details.client_hash:
            raise ValueError("client hash mismatch")
        # assert unique ids (c1) are correct and match login params
        if unique_id1_md5 != player.client_details.uninstall_md5:
            raise ValueError(
                f"unique_id1 mismatch ({unique_id1_md5} != {player.client_details.uninstall_md5})",
            )

        if unique_id2_md5 != player.client_details.disk_signature_md5:
            raise ValueError(
                f"unique_id2 mismatch ({unique_id2_md5} != {player.client_details.disk_signature_md5})",
            )

        # assert online checksums match
        server_score_checksum = score.compute_online_checksum(
            osu_version=osu_version,
            osu_client_hash=client_hash_decoded,
            storyboard_checksum=storyboard_md5 or "",
        )
        if score.client_checksum != server_score_checksum:
            raise ValueError(
                f"online score checksum mismatch ({server_score_checksum} != {score.client_checksum})",
            )

        # assert beatmap hashes match
        if bmap_md5 != updated_beatmap_hash:
            raise ValueError(
                f"beatmap hash mismatch ({bmap_md5} != {updated_beatmap_hash})",
            )

    except (ValueError, AssertionError):
        # NOTE: this is undergoing a temporary trial period,
        # after which, it will be enabled & perform restrictions.
        stacktrace = app.utils.get_appropriate_stacktrace()
        await app.state.services.log_strange_occurrence(stacktrace)

        # await player.restrict(
        #     admin=app.state.sessions.bot,
        #     reason="mismatching hashes on score submission",
        # )

        # refresh their client state
        # if player.online:
        #     player.logout()

        # return b"error: ban"

    # we should update their activity no matter
    # what the result of the score submission is.
    score.player.update_latest_activity_soon()

    # make sure the player's client displays the correct mode's stats
    if score.mode != score.player.status.mode:
        score.player.status.mods = score.mods
        score.player.status.mode = score.mode

        if not score.player.restricted:
            app.state.sessions.players.enqueue(app.packets.user_stats(score.player))

    # hold a lock around (check if submitted, submission) to ensure no duplicates
    # are submitted to the database, and potentially award duplicate score/pp/etc.
    async with app.state.score_submission_locks[score.client_checksum]:
        # stop here if this is a duplicate score
        if await app.state.services.database.fetch_one(
            "SELECT 1 FROM scores WHERE online_checksum = :checksum",
            {"checksum": score.client_checksum},
        ):
            log(f"{score.player} submitted a duplicate score.", Ansi.LYELLOW)
            return Response(b"error: no")

        # all data read from submission.
        # now we can calculate things based on our data.
        score.acc = score.calculate_accuracy()

        osu_file_available = await ensure_osu_file_is_available(
            bmap.id,
            expected_md5=bmap.md5,
        )
        if osu_file_available:
            score.pp, score.sr = score.calculate_performance(bmap.id)

            if score.passed:
                await score.calculate_status()

                if score.bmap.status != RankedStatus.Pending:
                    score.rank = await score.calculate_placement()
            else:
                score.status = SubmissionStatus.FAILED

        score.time_elapsed = score_time if score.passed else fail_time

        # TODO: re-implement pp caps for non-whitelisted players?

        """ Score submission checks completed; submit the score. """

        if app.state.services.datadog:
            app.state.services.datadog.increment("bancho.submitted_scores")  # type: ignore[no-untyped-call]

        if score.status == SubmissionStatus.BEST:
            if app.state.services.datadog:
                app.state.services.datadog.increment("bancho.submitted_scores_best")  # type: ignore[no-untyped-call]

            if score.bmap.has_leaderboard:
                if score.bmap.status == RankedStatus.Loved and score.mode in (
                    GameMode.VANILLA_OSU,
                    GameMode.VANILLA_TAIKO,
                    GameMode.VANILLA_CATCH,
                    GameMode.VANILLA_MANIA,
                ):
                    performance = f"{score.score:,} score"
                else:
                    performance = f"{score.pp:,.2f}pp"

                score.player.enqueue(
                    app.packets.notification(
                        f"You achieved #{score.rank}! ({performance})",
                    ),
                )

                if score.rank == 1 and not score.player.restricted:
                    announce_chan = app.state.sessions.channels.get_by_name("#announce")

                    ann = [
                        f"\x01ACTION achieved #1 on {score.bmap.embed}",
                        f"with {score.acc:.2f}% for {performance}.",
                    ]

                    if score.mods:
                        ann.insert(1, f"+{score.mods!r}")

                    scoring_metric = (
                        "pp" if score.mode >= GameMode.RELAX_OSU else "score"
                    )

                    # If there was previously a score on the map, add old #1.
                    prev_n1 = await app.state.services.database.fetch_one(
                        "SELECT u.id, name FROM users u "
                        "INNER JOIN scores s ON u.id = s.userid "
                        "WHERE s.map_md5 = :map_md5 AND s.mode = :mode "
                        "AND s.status = 2 AND u.priv & 1 "
                        f"ORDER BY s.{scoring_metric} DESC LIMIT 1",
                        {"map_md5": score.bmap.md5, "mode": score.mode},
                    )

                    if prev_n1:
                        if score.player.id != prev_n1["id"]:
                            ann.append(
                                f"(Previous #1: [https://{app.settings.DOMAIN}/u/"
                                "{id} {name}])".format(
                                    id=prev_n1["id"],
                                    name=prev_n1["name"],
                                ),
                            )

                    assert announce_chan is not None
                    announce_chan.send(" ".join(ann), sender=score.player, to_self=True)

            # this score is our best score.
            # update any preexisting personal best
            # records with SubmissionStatus.SUBMITTED.
            await app.state.services.database.execute(
                "UPDATE scores SET status = 1 "
                "WHERE status = 2 AND map_md5 = :map_md5 "
                "AND userid = :user_id AND mode = :mode",
                {
                    "map_md5": score.bmap.md5,
                    "user_id": score.player.id,
                    "mode": score.mode,
                },
            )

        score.id = await app.state.services.database.execute(
            "INSERT INTO scores "
            "VALUES (NULL, "
            ":map_md5, :score, :pp, :acc, "
            ":max_combo, :mods, :n300, :n100, "
            ":n50, :nmiss, :ngeki, :nkatu, "
            ":grade, :status, :mode, :play_time, "
            ":time_elapsed, :client_flags, :user_id, :perfect, "
            ":checksum)",
            {
                "map_md5": score.bmap.md5,
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
                "user_id": score.player.id,
                "perfect": score.perfect,
                "checksum": score.client_checksum,
            },
        )

    if score.passed:
        replay_data = await replay_file.read()

        MIN_REPLAY_SIZE = 24

        if len(replay_data) >= MIN_REPLAY_SIZE:
            replay_disk_file = REPLAYS_PATH / f"{score.id}.osr"
            replay_disk_file.write_bytes(replay_data)
        else:
            log(f"{score.player} submitted a score without a replay!", Ansi.LRED)

            if not score.player.restricted:
                await score.player.restrict(
                    admin=app.state.sessions.bot,
                    reason="submitted score with no replay",
                )
                if score.player.is_online:
                    score.player.logout()

    """ Update the user's & beatmap's stats """

    # get the current stats, and take a
    # shallow copy for the response charts.
    stats = score.player.stats[score.mode]
    prev_stats = copy.copy(stats)

    # stuff update for all submitted scores
    stats.playtime += score.time_elapsed // 1000
    stats.plays += 1
    stats.tscore += score.score
    stats.total_hits += score.n300 + score.n100 + score.n50

    if score.mode.as_vanilla in (1, 3):
        # taiko uses geki & katu for hitting big notes with 2 keys
        # mania uses geki & katu for rainbow 300 & 200
        stats.total_hits += score.ngeki + score.nkatu

    stats_updates: dict[str, Any] = {
        "plays": stats.plays,
        "playtime": stats.playtime,
        "tscore": stats.tscore,
        "total_hits": stats.total_hits,
    }

    if score.passed and score.bmap.has_leaderboard:
        # player passed & map is ranked, approved, or loved.

        if score.max_combo > stats.max_combo:
            stats.max_combo = score.max_combo
            stats_updates["max_combo"] = stats.max_combo

        if score.bmap.awards_ranked_pp and score.status == SubmissionStatus.BEST:
            # map is ranked or approved, and it's our (new)
            # best score on the map. update the player's
            # ranked score, grades, pp, acc and global rank.

            additional_rscore = score.score
            if score.prev_best:
                # we previously had a score, so remove
                # it's score from our ranked score.
                additional_rscore -= score.prev_best.score

                if score.grade != score.prev_best.grade:
                    if score.grade >= Grade.A:
                        stats.grades[score.grade] += 1
                        grade_col = format(score.grade, "stats_column")
                        stats_updates[grade_col] = stats.grades[score.grade]

                    if score.prev_best.grade >= Grade.A:
                        stats.grades[score.prev_best.grade] -= 1
                        grade_col = format(score.prev_best.grade, "stats_column")
                        stats_updates[grade_col] = stats.grades[score.prev_best.grade]
            else:
                # this is our first submitted score on the map
                if score.grade >= Grade.A:
                    stats.grades[score.grade] += 1
                    grade_col = format(score.grade, "stats_column")
                    stats_updates[grade_col] = stats.grades[score.grade]

            stats.rscore += additional_rscore
            stats_updates["rscore"] = stats.rscore

            # fetch scores sorted by pp for total acc/pp calc
            # NOTE: we select all plays (and not just top100)
            # because bonus pp counts the total amount of ranked
            # scores. I'm aware this scales horribly, and it'll
            # likely be split into two queries in the future.
            best_scores = await app.state.services.database.fetch_all(
                "SELECT s.pp, s.acc FROM scores s "
                "INNER JOIN maps m ON s.map_md5 = m.md5 "
                "WHERE s.userid = :user_id AND s.mode = :mode "
                "AND s.status = 2 AND m.status IN (2, 3) "  # ranked, approved
                "ORDER BY s.pp DESC",
                {"user_id": score.player.id, "mode": score.mode},
            )

            # calculate new total weighted accuracy
            weighted_acc = sum(
                row["acc"] * 0.95**i for i, row in enumerate(best_scores)
            )
            bonus_acc = 100.0 / (20 * (1 - 0.95 ** len(best_scores)))
            stats.acc = (weighted_acc * bonus_acc) / 100
            stats_updates["acc"] = stats.acc

            # calculate new total weighted pp
            weighted_pp = sum(row["pp"] * 0.95**i for i, row in enumerate(best_scores))
            bonus_pp = 416.6667 * (1 - 0.9994 ** len(best_scores))
            stats.pp = round(weighted_pp + bonus_pp)
            stats_updates["pp"] = stats.pp

            # update global & country ranking
            stats.rank = await score.player.update_rank(score.mode)

    await stats_repo.partial_update(
        score.player.id,
        score.mode.value,
        plays=stats_updates.get("plays", UNSET),
        playtime=stats_updates.get("playtime", UNSET),
        tscore=stats_updates.get("tscore", UNSET),
        total_hits=stats_updates.get("total_hits", UNSET),
        max_combo=stats_updates.get("max_combo", UNSET),
        xh_count=stats_updates.get("xh_count", UNSET),
        x_count=stats_updates.get("x_count", UNSET),
        sh_count=stats_updates.get("sh_count", UNSET),
        s_count=stats_updates.get("s_count", UNSET),
        a_count=stats_updates.get("a_count", UNSET),
        rscore=stats_updates.get("rscore", UNSET),
        acc=stats_updates.get("acc", UNSET),
        pp=stats_updates.get("pp", UNSET),
    )

    if not score.player.restricted:
        # enqueue new stats info to all other users
        app.state.sessions.players.enqueue(app.packets.user_stats(score.player))

        # update beatmap with new stats
        score.bmap.plays += 1
        if score.passed:
            score.bmap.passes += 1

        await app.state.services.database.execute(
            "UPDATE maps SET plays = :plays, passes = :passes WHERE md5 = :map_md5",
            {
                "plays": score.bmap.plays,
                "passes": score.bmap.passes,
                "map_md5": score.bmap.md5,
            },
        )

    # update their recent score
    score.player.recent_scores[score.mode] = score

    """ score submission charts """

    # charts are only displayed for passes vanilla gamemodes.
    if not score.passed:  # TODO: check if this is correct
        response = b"error: no"
    else:
        # construct and send achievements & ranking charts to the client
        if score.bmap.awards_ranked_pp and not score.player.restricted:
            unlocked_achievements: list[Achievement] = []

            server_achievements = await achievements_usecases.fetch_many()
            player_achievements = await user_achievements_usecases.fetch_many(
                user_id=score.player.id,
            )

            for server_achievement in server_achievements:
                player_unlocked_achievement = any(
                    player_achievement
                    for player_achievement in player_achievements
                    if player_achievement["achid"] == server_achievement["id"]
                )
                if player_unlocked_achievement:
                    # player already has this achievement.
                    continue

                achievement_condition = server_achievement["cond"]
                if achievement_condition(score, score.mode.as_vanilla):
                    await user_achievements_usecases.create(
                        score.player.id,
                        server_achievement["id"],
                    )
                    unlocked_achievements.append(server_achievement)

            achievements_str = "/".join(
                format_achievement_string(a["file"], a["name"], a["desc"])
                for a in unlocked_achievements
            )
        else:
            achievements_str = ""

        # create score submission charts for osu! client to display

        if score.prev_best:
            beatmap_ranking_chart_entries = (
                chart_entry("rank", score.prev_best.rank, score.rank),
                chart_entry("rankedScore", score.prev_best.score, score.score),
                chart_entry("totalScore", score.prev_best.score, score.score),
                chart_entry("maxCombo", score.prev_best.max_combo, score.max_combo),
                chart_entry(
                    "accuracy",
                    round(score.prev_best.acc, 2),
                    round(score.acc, 2),
                ),
                chart_entry("pp", score.prev_best.pp, score.pp),
            )
        else:
            # no previous best score
            beatmap_ranking_chart_entries = (
                chart_entry("rank", None, score.rank),
                chart_entry("rankedScore", None, score.score),
                chart_entry("totalScore", None, score.score),
                chart_entry("maxCombo", None, score.max_combo),
                chart_entry("accuracy", None, round(score.acc, 2)),
                chart_entry("pp", None, score.pp),
            )

        overall_ranking_chart_entries = (
            chart_entry("rank", prev_stats.rank, stats.rank),
            chart_entry("rankedScore", prev_stats.rscore, stats.rscore),
            chart_entry("totalScore", prev_stats.tscore, stats.tscore),
            chart_entry("maxCombo", prev_stats.max_combo, stats.max_combo),
            chart_entry("accuracy", round(prev_stats.acc, 2), round(stats.acc, 2)),
            chart_entry("pp", prev_stats.pp, stats.pp),
        )

        submission_charts = [
            # beatmap info chart
            f"beatmapId:{score.bmap.id}",
            f"beatmapSetId:{score.bmap.set_id}",
            f"beatmapPlaycount:{score.bmap.plays}",
            f"beatmapPasscount:{score.bmap.passes}",
            f"approvedDate:{score.bmap.last_update}",
            "\n",
            # beatmap ranking chart
            "chartId:beatmap",
            f"chartUrl:{score.bmap.set.url}",
            "chartName:Beatmap Ranking",
            *beatmap_ranking_chart_entries,
            f"onlineScoreId:{score.id}",
            "\n",
            # overall ranking chart
            "chartId:overall",
            f"chartUrl:https://{app.settings.DOMAIN}/u/{score.player.id}",
            "chartName:Overall Ranking",
            *overall_ranking_chart_entries,
            f"achievements-new:{achievements_str}",
        ]

        response = "|".join(submission_charts).encode()

    log(
        f"[{score.mode!r}] {score.player} submitted a score! "
        f"({score.status!r}, {score.pp:,.2f}pp / {stats.pp:,}pp)",
        Ansi.LGREEN,
    )

    return Response(response)
