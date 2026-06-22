from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from app.objects.player import ClientDetails
from app.objects.player import ModeData
from app.objects.score import Score
from app.repositories.achievements import Achievement


@dataclass(frozen=True)
class UniqueIdHashes:
    unique_id1_md5: str
    unique_id2_md5: str


def parse_unique_id_hashes(unique_ids: str) -> UniqueIdHashes:
    unique_id1, unique_id2 = unique_ids.split("|", maxsplit=1)
    return UniqueIdHashes(
        unique_id1_md5=hashlib.md5(unique_id1.encode()).hexdigest(),
        unique_id2_md5=hashlib.md5(unique_id2.encode()).hexdigest(),
    )


def validate_client_details(
    *,
    client_details: ClientDetails | None,
    osu_version: str,
    client_hash: str,
    unique_id_hashes: UniqueIdHashes,
) -> None:
    if client_details is None:
        raise ValueError("missing client details")

    if osu_version != f"{client_details.osu_version.date:%Y%m%d}":
        raise ValueError("osu! version mismatch")

    if client_hash != client_details.client_hash:
        raise ValueError("client hash mismatch")

    if unique_id_hashes.unique_id1_md5 != client_details.uninstall_md5:
        raise ValueError(
            f"unique_id1 mismatch ({unique_id_hashes.unique_id1_md5} != {client_details.uninstall_md5})",
        )

    if unique_id_hashes.unique_id2_md5 != client_details.disk_signature_md5:
        raise ValueError(
            f"unique_id2 mismatch ({unique_id_hashes.unique_id2_md5} != {client_details.disk_signature_md5})",
        )


def validate_score_checksum(
    *,
    score: Score,
    osu_version: str,
    client_hash: str,
    storyboard_md5: str | None,
) -> None:
    server_score_checksum = score.compute_online_checksum(
        osu_version=osu_version,
        osu_client_hash=client_hash,
        storyboard_checksum=storyboard_md5 or "",
    )
    if score.client_checksum != server_score_checksum:
        raise ValueError(
            f"online score checksum mismatch ({server_score_checksum} != {score.client_checksum})",
        )


def validate_beatmap_hash(
    *,
    submission_beatmap_md5: str,
    updated_beatmap_hash: str,
) -> None:
    if submission_beatmap_md5 != updated_beatmap_hash:
        raise ValueError(
            f"beatmap hash mismatch ({submission_beatmap_md5} != {updated_beatmap_hash})",
        )


def validate_submission_integrity(
    *,
    client_details: ClientDetails | None,
    osu_version: str,
    client_hash: str,
    unique_ids: str,
    score: Score,
    storyboard_md5: str | None,
    submission_beatmap_md5: str,
    updated_beatmap_hash: str,
) -> None:
    unique_id_hashes = parse_unique_id_hashes(unique_ids)
    validate_client_details(
        client_details=client_details,
        osu_version=osu_version,
        client_hash=client_hash,
        unique_id_hashes=unique_id_hashes,
    )
    validate_score_checksum(
        score=score,
        osu_version=osu_version,
        client_hash=client_hash,
        storyboard_md5=storyboard_md5,
    )
    validate_beatmap_hash(
        submission_beatmap_md5=submission_beatmap_md5,
        updated_beatmap_hash=updated_beatmap_hash,
    )


def chart_entry(
    name: str,
    before: float | int | None,
    after: float | int | None,
) -> str:
    return f"{name}Before:{before or ''}|{name}After:{after or ''}"


def format_achievement_string(file: str, name: str, description: str) -> str:
    return f"{file}+{name}+{description}"


def format_achievements(achievements: Sequence[Achievement]) -> str:
    return "/".join(
        format_achievement_string(
            achievement["file"],
            achievement["name"],
            achievement["desc"],
        )
        for achievement in achievements
    )


def build_submission_charts(
    *,
    score: Score,
    previous_stats: ModeData,
    current_stats: ModeData,
    achievements: Sequence[Achievement],
    domain: str,
) -> bytes:
    assert score.bmap is not None
    assert score.player is not None

    if score.prev_best:
        beatmap_ranking_chart_entries = (
            chart_entry("rank", score.prev_best.rank, score.rank),
            chart_entry("rankedScore", score.prev_best.score, score.score),
            chart_entry("totalScore", score.prev_best.score, score.score),
            chart_entry("maxCombo", score.prev_best.max_combo, score.max_combo),
            chart_entry("accuracy", round(score.prev_best.acc, 2), round(score.acc, 2)),
            chart_entry("pp", score.prev_best.pp, score.pp),
        )
    else:
        beatmap_ranking_chart_entries = (
            chart_entry("rank", None, score.rank),
            chart_entry("rankedScore", None, score.score),
            chart_entry("totalScore", None, score.score),
            chart_entry("maxCombo", None, score.max_combo),
            chart_entry("accuracy", None, round(score.acc, 2)),
            chart_entry("pp", None, score.pp),
        )

    overall_ranking_chart_entries = (
        chart_entry("rank", previous_stats.rank, current_stats.rank),
        chart_entry("rankedScore", previous_stats.rscore, current_stats.rscore),
        chart_entry("totalScore", previous_stats.tscore, current_stats.tscore),
        chart_entry("maxCombo", previous_stats.max_combo, current_stats.max_combo),
        chart_entry(
            "accuracy",
            round(previous_stats.acc, 2),
            round(current_stats.acc, 2),
        ),
        chart_entry("pp", previous_stats.pp, current_stats.pp),
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
        f"chartUrl:https://{domain}/u/{score.player.id}",
        "chartName:Overall Ranking",
        *overall_ranking_chart_entries,
        f"achievements-new:{format_achievements(achievements)}",
    ]

    return "|".join(submission_charts).encode()
