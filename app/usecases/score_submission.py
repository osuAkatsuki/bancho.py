from __future__ import annotations

import hashlib
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from typing import Protocol

from app.objects.player import ClientDetails
from app.objects.player import ModeData
from app.objects.score import Grade
from app.objects.score import Score
from app.objects.score import SubmissionStatus
from app.repositories.achievements import Achievement
from app.repositories.user_achievements import UserAchievement

StatsUpdates = dict[str, Any]
BestScorePerformance = Mapping[str, float]
GRADE_STATS_COLUMNS = {
    Grade.XH: "xh_count",
    Grade.X: "x_count",
    Grade.SH: "sh_count",
    Grade.S: "s_count",
    Grade.A: "a_count",
}


class AchievementsService(Protocol):
    async def fetch_many(self) -> Sequence[Achievement]: ...


class UserAchievementsService(Protocol):
    async def fetch_many(self, *, user_id: int) -> Sequence[UserAchievement]: ...

    async def create(
        self,
        user_id: int,
        achievement_id: int,
    ) -> UserAchievement: ...


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


def apply_score_base_stats(score: Score, stats: ModeData) -> StatsUpdates:
    # Stats updated for all submitted scores.
    stats.playtime += score.time_elapsed // 1000
    stats.plays += 1
    stats.tscore += score.score
    stats.total_hits += score.n300 + score.n100 + score.n50

    if score.mode.as_vanilla in (1, 3):
        # Taiko uses geki & katu for hitting big notes with 2 keys;
        # mania uses geki & katu for rainbow 300 & 200.
        stats.total_hits += score.ngeki + score.nkatu

    return {
        "plays": stats.plays,
        "playtime": stats.playtime,
        "tscore": stats.tscore,
        "total_hits": stats.total_hits,
    }


def ranked_score_delta(score: Score) -> int:
    if score.prev_best is None:
        return score.score

    # We previously had a score, so remove its score from our ranked score.
    return score.score - score.prev_best.score


def grade_count_deltas(score: Score) -> dict[Grade, int]:
    if score.prev_best is None:
        # This is our first submitted score on the map.
        return {score.grade: 1} if score.grade >= Grade.A else {}

    if score.grade == score.prev_best.grade:
        return {}

    deltas: dict[Grade, int] = {}
    if score.grade >= Grade.A:
        deltas[score.grade] = 1
    if score.prev_best.grade >= Grade.A:
        deltas[score.prev_best.grade] = deltas.get(score.prev_best.grade, 0) - 1

    return deltas


def apply_ranked_score_stats(score: Score, stats: ModeData) -> StatsUpdates:
    updates: StatsUpdates = {}

    for grade, delta in grade_count_deltas(score).items():
        stats.grades[grade] += delta
        updates[GRADE_STATS_COLUMNS[grade]] = stats.grades[grade]

    stats.rscore += ranked_score_delta(score)
    updates["rscore"] = stats.rscore

    return updates


def apply_score_stats(score: Score, stats: ModeData) -> StatsUpdates:
    updates = apply_score_base_stats(score, stats)

    if not score.passed:
        return updates

    assert score.bmap is not None
    if not score.bmap.has_leaderboard:
        return updates

    if score.max_combo > stats.max_combo:
        stats.max_combo = score.max_combo
        updates["max_combo"] = stats.max_combo

    if score.bmap.awards_ranked_pp and score.status == SubmissionStatus.BEST:
        # Map is ranked or approved, and this is our (new)
        # best score on the map. Update the player's
        # ranked score and grade counts.
        updates.update(apply_ranked_score_stats(score, stats))

    return updates


def calculate_weighted_accuracy(best_scores: Sequence[BestScorePerformance]) -> float:
    # Calculate new total weighted accuracy.
    weighted_acc = sum(row["acc"] * 0.95**i for i, row in enumerate(best_scores))
    bonus_acc = 100.0 / (20 * (1 - 0.95 ** len(best_scores)))
    return (weighted_acc * bonus_acc) / 100


def calculate_weighted_pp(best_scores: Sequence[BestScorePerformance]) -> int:
    # Calculate new total weighted pp.
    weighted_pp = sum(row["pp"] * 0.95**i for i, row in enumerate(best_scores))
    bonus_pp = 416.6667 * (1 - 0.9994 ** len(best_scores))
    return round(weighted_pp + bonus_pp)


def apply_weighted_performance_stats(
    stats: ModeData,
    best_scores: Sequence[BestScorePerformance],
) -> StatsUpdates:
    stats.acc = calculate_weighted_accuracy(best_scores)
    stats.pp = calculate_weighted_pp(best_scores)

    return {
        "acc": stats.acc,
        "pp": stats.pp,
    }


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


def achievement_is_unlocked(
    achievement: Achievement,
    user_achievements: Sequence[UserAchievement],
) -> bool:
    return any(
        user_achievement["achid"] == achievement["id"]
        for user_achievement in user_achievements
    )


async def unlock_new_achievements(
    *,
    score: Score,
    achievements: AchievementsService,
    user_achievements: UserAchievementsService,
) -> list[Achievement]:
    assert score.player is not None

    unlocked_achievements: list[Achievement] = []
    server_achievements = await achievements.fetch_many()
    player_achievements = await user_achievements.fetch_many(user_id=score.player.id)

    for server_achievement in server_achievements:
        if achievement_is_unlocked(server_achievement, player_achievements):
            continue

        achievement_condition = server_achievement["cond"]
        if achievement_condition(score, score.mode.as_vanilla):
            await user_achievements.create(
                score.player.id,
                server_achievement["id"],
            )
            unlocked_achievements.append(server_achievement)

    return unlocked_achievements


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


async def build_score_submission_response(
    *,
    score: Score,
    previous_stats: ModeData,
    current_stats: ModeData,
    domain: str,
    achievements: AchievementsService,
    user_achievements: UserAchievementsService,
) -> bytes:
    if not score.passed:  # TODO: check if this is correct
        return b"error: no"

    assert score.bmap is not None
    assert score.player is not None

    if score.bmap.awards_ranked_pp and not score.player.restricted:
        unlocked_achievements = await unlock_new_achievements(
            score=score,
            achievements=achievements,
            user_achievements=user_achievements,
        )
    else:
        unlocked_achievements = []

    return build_submission_charts(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        achievements=unlocked_achievements,
        domain=domain,
    )
