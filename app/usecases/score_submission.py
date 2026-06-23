from __future__ import annotations

import copy
import hashlib
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import NotRequired
from typing import Protocol
from typing import TypedDict

from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.constants.beatmap_statuses import RankedStatus
from app.constants.gamemodes import GameMode
from app.constants.score_statuses import SubmissionStatus
from app.constants.scoring_metrics import ScoringMetric
from app.objects.player import ClientDetails
from app.objects.player import ModeData
from app.objects.player import Player
from app.objects.score import Grade
from app.objects.score import Score
from app.repositories.achievements import Achievement
from app.repositories.scores import FirstPlaceScore
from app.repositories.scores import ScorePerformanceRow
from app.repositories.user_achievements import UserAchievement


class ScoreStatsUpdates(TypedDict):
    plays: int
    playtime: int
    tscore: int
    total_hits: int
    max_combo: NotRequired[int]
    xh_count: NotRequired[int]
    x_count: NotRequired[int]
    sh_count: NotRequired[int]
    s_count: NotRequired[int]
    a_count: NotRequired[int]
    rscore: NotRequired[int]
    acc: NotRequired[float]
    pp: NotRequired[int]


class GradeCountStatsUpdates(TypedDict):
    xh_count: NotRequired[int]
    x_count: NotRequired[int]
    sh_count: NotRequired[int]
    s_count: NotRequired[int]
    a_count: NotRequired[int]


class RankedScoreStatsUpdates(TypedDict):
    rscore: int
    xh_count: NotRequired[int]
    x_count: NotRequired[int]
    sh_count: NotRequired[int]
    s_count: NotRequired[int]
    a_count: NotRequired[int]


class WeightedPerformanceStatsUpdates(TypedDict):
    acc: float
    pp: int


class BeatmapPlayStatsUpdates(TypedDict):
    plays: int
    passes: int


class DatabaseTransactions(Protocol):
    def transaction(self) -> AbstractAsyncContextManager[Any]: ...


MIN_REPLAY_SIZE = 24
VANILLA_GAME_MODES = (
    GameMode.VANILLA_OSU,
    GameMode.VANILLA_TAIKO,
    GameMode.VANILLA_CATCH,
    GameMode.VANILLA_MANIA,
)


class AchievementsService(Protocol):
    async def fetch_many(self) -> Sequence[Achievement]: ...


class UserAchievementsService(Protocol):
    async def fetch_many(self, *, user_id: int) -> Sequence[UserAchievement]: ...

    async def create(
        self,
        user_id: int,
        achievement_id: int,
    ) -> UserAchievement: ...


class ReplayFile(Protocol):
    async def read(self) -> bytes: ...


class AnnouncementChannel(Protocol):
    def send(self, msg: str, sender: Player, to_self: bool = False) -> None: ...


class ScoresRepository(Protocol):
    async def create(
        self,
        map_md5: str,
        score: int,
        pp: float,
        acc: float,
        max_combo: int,
        mods: int,
        n300: int,
        n100: int,
        n50: int,
        nmiss: int,
        ngeki: int,
        nkatu: int,
        grade: str,
        status: int,
        mode: int,
        play_time: datetime,
        time_elapsed: int,
        client_flags: int,
        user_id: int,
        perfect: int,
        online_checksum: str,
    ) -> Mapping[str, Any]: ...

    async def mark_previous_best_scores_submitted(
        self,
        *,
        map_md5: str,
        user_id: int,
        mode: int,
    ) -> None: ...

    async def fetch_weighted_best_performances(
        self,
        *,
        user_id: int,
        mode: int,
    ) -> Sequence[ScorePerformanceRow]: ...

    async def fetch_first_place_score(
        self,
        *,
        map_md5: str,
        mode: int,
        scoring_metric: ScoringMetric,
    ) -> FirstPlaceScore | None: ...


class StatsRepository(Protocol):
    async def partial_update(
        self,
        player_id: int,
        mode: int,
        tscore: int | _UnsetSentinel = UNSET,
        rscore: int | _UnsetSentinel = UNSET,
        pp: int | _UnsetSentinel = UNSET,
        plays: int | _UnsetSentinel = UNSET,
        playtime: int | _UnsetSentinel = UNSET,
        acc: float | _UnsetSentinel = UNSET,
        max_combo: int | _UnsetSentinel = UNSET,
        total_hits: int | _UnsetSentinel = UNSET,
        replay_views: int | _UnsetSentinel = UNSET,
        xh_count: int | _UnsetSentinel = UNSET,
        x_count: int | _UnsetSentinel = UNSET,
        sh_count: int | _UnsetSentinel = UNSET,
        s_count: int | _UnsetSentinel = UNSET,
        a_count: int | _UnsetSentinel = UNSET,
    ) -> Mapping[str, Any] | None: ...


class MapsRepository(Protocol):
    async def partial_update(
        self,
        id: int,
        *,
        plays: int | _UnsetSentinel = UNSET,
        passes: int | _UnsetSentinel = UNSET,
    ) -> Mapping[str, Any] | None: ...


@dataclass(frozen=True)
class UniqueIdHashes:
    unique_id1_md5: str
    unique_id2_md5: str


@dataclass(frozen=True)
class ScoreStatsPersistenceResult:
    previous_stats: ModeData
    current_stats: ModeData
    should_update_rank: bool
    should_publish_user_stats: bool


@dataclass(frozen=True)
class ScoreSubmissionPersistenceResult:
    score_id: int
    previous_stats: ModeData
    current_stats: ModeData
    previous_first_place_score: FirstPlaceScore | None
    unlocked_achievements: Sequence[Achievement]
    should_update_rank: bool
    should_publish_user_stats: bool


@dataclass(frozen=True)
class ScoreSubmissionStateSnapshot:
    score_id: int | None
    stats: ModeData
    beatmap_plays: int
    beatmap_passes: int
    had_recent_score: bool
    recent_score: Score | None


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


async def persist_submitted_score(score: Score, scores: ScoresRepository) -> int:
    assert score.bmap is not None
    assert score.player is not None

    if score.status == SubmissionStatus.BEST:
        # this score is our best score.
        # update any preexisting personal best
        # records with SubmissionStatus.SUBMITTED.
        await scores.mark_previous_best_scores_submitted(
            map_md5=score.bmap.md5,
            user_id=score.player.id,
            mode=score.mode.value,
        )

    created_score = await scores.create(
        map_md5=score.bmap.md5,
        score=score.score,
        pp=score.pp,
        acc=score.acc,
        max_combo=score.max_combo,
        mods=score.mods.value,
        n300=score.n300,
        n100=score.n100,
        n50=score.n50,
        nmiss=score.nmiss,
        ngeki=score.ngeki,
        nkatu=score.nkatu,
        grade=score.grade.name,
        status=score.status.value,
        mode=score.mode.value,
        play_time=score.server_time,
        time_elapsed=score.time_elapsed,
        client_flags=score.client_flags.value,
        user_id=score.player.id,
        perfect=int(score.perfect),
        online_checksum=score.client_checksum,
    )
    score_id = int(created_score["id"])
    score.id = score_id
    return score_id


async def save_replay_file(
    score: Score,
    *,
    replay_file: ReplayFile,
    replays_path: Path,
    restriction_admin: Player,
    log_missing_replay: Callable[[str], None],
) -> None:
    replay_data = await read_and_validate_replay_file(
        score,
        replay_file=replay_file,
        restriction_admin=restriction_admin,
        log_missing_replay=log_missing_replay,
    )
    write_replay_file(score, replay_data=replay_data, replays_path=replays_path)


async def read_and_validate_replay_file(
    score: Score,
    *,
    replay_file: ReplayFile,
    restriction_admin: Player,
    log_missing_replay: Callable[[str], None],
) -> bytes | None:
    assert score.player is not None

    if not score.passed:
        return None

    replay_data = await replay_file.read()

    if len(replay_data) >= MIN_REPLAY_SIZE:
        return replay_data

    log_missing_replay(f"{score.player} submitted a score without a replay!")

    if not score.player.restricted:
        await score.player.restrict(
            admin=restriction_admin,
            reason="submitted score with no replay",
        )
        if score.player.is_online:
            score.player.logout()

    return None


def write_replay_file(
    score: Score,
    *,
    replay_data: bytes | None,
    replays_path: Path,
) -> None:
    if replay_data is None:
        return

    assert score.id is not None
    replay_disk_file = replays_path / f"{score.id}.osr"
    replay_disk_file.write_bytes(replay_data)


def format_score_submission_performance(score: Score) -> str:
    assert score.bmap is not None

    if score.bmap.status == RankedStatus.Loved and score.mode in VANILLA_GAME_MODES:
        return f"{score.score:,} score"

    return f"{score.pp:,.2f}pp"


def notify_score_submitter_of_personal_best(
    score: Score,
    *,
    send_notification: Callable[[Player, str], None],
) -> str | None:
    assert score.bmap is not None
    assert score.player is not None

    if score.status != SubmissionStatus.BEST:
        return None

    if not score.bmap.has_leaderboard:
        return None

    performance = format_score_submission_performance(score)
    send_notification(
        score.player,
        f"You achieved #{score.rank}! ({performance})",
    )
    return performance


def first_place_scoring_metric(score: Score) -> ScoringMetric:
    return "pp" if score.mode >= GameMode.RELAX_OSU else "score"


def score_should_announce_first_place(score: Score) -> bool:
    assert score.bmap is not None
    assert score.player is not None

    return (
        score.status == SubmissionStatus.BEST
        and score.bmap.has_leaderboard
        and score.rank == 1
        and not score.player.restricted
    )


async def fetch_previous_first_place_score(
    score: Score,
    *,
    scores: ScoresRepository,
) -> FirstPlaceScore | None:
    assert score.bmap is not None

    # Before persistence, the current first-place row is the previous #1 for
    # this submission.
    return await scores.fetch_first_place_score(
        map_md5=score.bmap.md5,
        mode=score.mode.value,
        scoring_metric=first_place_scoring_metric(score),
    )


def announce_first_place(
    score: Score,
    *,
    previous_first_place_score: FirstPlaceScore | None,
    announce_channel: AnnouncementChannel | None,
    domain: str,
) -> None:
    assert score.bmap is not None
    assert score.player is not None

    if not score_should_announce_first_place(score):
        return

    performance = format_score_submission_performance(score)
    ann = [
        f"\x01ACTION achieved #1 on {score.bmap.embed}",
        f"with {score.acc:.2f}% for {performance}.",
    ]

    if score.mods:
        ann.insert(1, f"+{score.mods!r}")

    if previous_first_place_score:
        if score.player.id != previous_first_place_score["id"]:
            ann.append(
                f"(Previous #1: [https://{domain}/u/"
                f"{previous_first_place_score['id']} "
                f"{previous_first_place_score['name']}])",
            )

    assert announce_channel is not None
    announce_channel.send(" ".join(ann), sender=score.player, to_self=True)


def capture_score_submission_state(score: Score) -> ScoreSubmissionStateSnapshot:
    assert score.bmap is not None
    assert score.player is not None

    current_stats = score.player.stats[score.mode]
    return ScoreSubmissionStateSnapshot(
        score_id=score.id,
        stats=copy.deepcopy(current_stats),
        beatmap_plays=score.bmap.plays,
        beatmap_passes=score.bmap.passes,
        had_recent_score=score.mode in score.player.recent_scores,
        recent_score=score.player.recent_scores.get(score.mode),
    )


def restore_score_submission_state(
    score: Score,
    snapshot: ScoreSubmissionStateSnapshot,
) -> None:
    assert score.bmap is not None
    assert score.player is not None

    score.id = snapshot.score_id
    score.player.stats[score.mode] = snapshot.stats
    score.bmap.plays = snapshot.beatmap_plays
    score.bmap.passes = snapshot.beatmap_passes

    if snapshot.had_recent_score:
        assert snapshot.recent_score is not None
        score.player.recent_scores[score.mode] = snapshot.recent_score
    else:
        score.player.recent_scores.pop(score.mode, None)


def apply_score_base_stats(score: Score, stats: ModeData) -> ScoreStatsUpdates:
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


def set_grade_count_update(
    updates: GradeCountStatsUpdates,
    grade: Grade,
    value: int,
) -> None:
    if grade == Grade.XH:
        updates["xh_count"] = value
    elif grade == Grade.X:
        updates["x_count"] = value
    elif grade == Grade.SH:
        updates["sh_count"] = value
    elif grade == Grade.S:
        updates["s_count"] = value
    elif grade == Grade.A:
        updates["a_count"] = value
    else:
        raise ValueError(f"Unexpected grade count update for {grade!r}")


def apply_ranked_score_stats(score: Score, stats: ModeData) -> RankedScoreStatsUpdates:
    grade_updates: GradeCountStatsUpdates = {}

    for grade, delta in grade_count_deltas(score).items():
        stats.grades[grade] += delta
        set_grade_count_update(grade_updates, grade, stats.grades[grade])

    stats.rscore += ranked_score_delta(score)

    return {
        **grade_updates,
        "rscore": stats.rscore,
    }


def apply_score_stats(score: Score, stats: ModeData) -> ScoreStatsUpdates:
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
        # Official osu! includes loved maps in ranked score and grade counts.
        # bancho.py has historically counted only ranked/approved maps here;
        # expanding this would require a stats backfill for existing users.
        # Map is ranked or approved, and this is our (new)
        # best score on the map. Update the player's
        # ranked score and grade counts.
        ranked_updates = apply_ranked_score_stats(score, stats)
        if "xh_count" in ranked_updates:
            updates["xh_count"] = ranked_updates["xh_count"]
        if "x_count" in ranked_updates:
            updates["x_count"] = ranked_updates["x_count"]
        if "sh_count" in ranked_updates:
            updates["sh_count"] = ranked_updates["sh_count"]
        if "s_count" in ranked_updates:
            updates["s_count"] = ranked_updates["s_count"]
        if "a_count" in ranked_updates:
            updates["a_count"] = ranked_updates["a_count"]
        updates["rscore"] = ranked_updates["rscore"]

    return updates


def calculate_weighted_accuracy(best_scores: Sequence[ScorePerformanceRow]) -> float:
    # Calculate new total weighted accuracy.
    weighted_acc = sum(row["acc"] * 0.95**i for i, row in enumerate(best_scores))
    bonus_acc = 100.0 / (20 * (1 - 0.95 ** len(best_scores)))
    return (weighted_acc * bonus_acc) / 100


def calculate_weighted_pp(best_scores: Sequence[ScorePerformanceRow]) -> int:
    # Calculate new total weighted pp.
    weighted_pp = sum(row["pp"] * 0.95**i for i, row in enumerate(best_scores))
    bonus_pp = 416.6667 * (1 - 0.9994 ** len(best_scores))
    return round(weighted_pp + bonus_pp)


def apply_weighted_performance_stats(
    stats: ModeData,
    best_scores: Sequence[ScorePerformanceRow],
) -> WeightedPerformanceStatsUpdates:
    stats.acc = calculate_weighted_accuracy(best_scores)
    stats.pp = calculate_weighted_pp(best_scores)

    return {
        "acc": stats.acc,
        "pp": stats.pp,
    }


def apply_beatmap_play_stats(score: Score) -> BeatmapPlayStatsUpdates:
    assert score.bmap is not None

    # update beatmap with new stats
    score.bmap.plays += 1
    if score.passed:
        score.bmap.passes += 1

    return {
        "plays": score.bmap.plays,
        "passes": score.bmap.passes,
    }


async def persist_score_submission_stats(
    score: Score,
    *,
    stats: StatsRepository,
    scores: ScoresRepository,
    maps: MapsRepository,
) -> ScoreStatsPersistenceResult:
    assert score.bmap is not None
    assert score.player is not None

    # get the current stats, and take a
    # shallow copy for the response charts.
    current_stats = score.player.stats[score.mode]
    previous_stats = copy.copy(current_stats)

    stats_updates = apply_score_stats(score, current_stats)
    should_update_rank = False

    if score.passed and score.bmap.has_leaderboard:
        # player passed & map is ranked, approved, or loved.

        if score.bmap.awards_ranked_pp and score.status == SubmissionStatus.BEST:
            # map is ranked or approved, and it's our (new)
            # best score on the map. update the player's pp,
            # acc and global rank.

            # fetch scores sorted by pp for total acc/pp calc
            # NOTE: we select all plays (and not just top100)
            # because bonus pp counts the total amount of ranked
            # scores. I'm aware this scales horribly, and it'll
            # likely be split into two queries in the future.
            best_scores = await scores.fetch_weighted_best_performances(
                user_id=score.player.id,
                mode=score.mode.value,
            )

            weighted_updates = apply_weighted_performance_stats(
                current_stats,
                best_scores,
            )
            stats_updates["acc"] = weighted_updates["acc"]
            stats_updates["pp"] = weighted_updates["pp"]

            should_update_rank = True

    await stats.partial_update(
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

    should_publish_user_stats = not score.player.restricted
    if should_publish_user_stats:
        beatmap_updates = apply_beatmap_play_stats(score)
        await maps.partial_update(
            score.bmap.id,
            plays=beatmap_updates["plays"],
            passes=beatmap_updates["passes"],
        )

    return ScoreStatsPersistenceResult(
        previous_stats=previous_stats,
        current_stats=current_stats,
        should_update_rank=should_update_rank,
        should_publish_user_stats=should_publish_user_stats,
    )


def score_can_unlock_achievements(score: Score) -> bool:
    assert score.bmap is not None
    assert score.player is not None

    return score.passed and score.bmap.awards_ranked_pp and not score.player.restricted


async def persist_score_submission(
    score: Score,
    *,
    database: DatabaseTransactions,
    scores: ScoresRepository,
    stats: StatsRepository,
    maps: MapsRepository,
    achievements: AchievementsService,
    user_achievements: UserAchievementsService,
) -> ScoreSubmissionPersistenceResult:
    snapshot = capture_score_submission_state(score)

    try:
        async with database.transaction():
            should_announce_first_place = score_should_announce_first_place(score)
            previous_first_place_score = (
                await fetch_previous_first_place_score(score, scores=scores)
                if should_announce_first_place
                else None
            )
            score_id = await persist_submitted_score(score, scores)
            stats_result = await persist_score_submission_stats(
                score,
                stats=stats,
                scores=scores,
                maps=maps,
            )
            unlocked_achievements = (
                await unlock_new_achievements(
                    score=score,
                    achievements=achievements,
                    user_achievements=user_achievements,
                )
                if score_can_unlock_achievements(score)
                else []
            )
    except BaseException:
        restore_score_submission_state(score, snapshot)
        raise

    return ScoreSubmissionPersistenceResult(
        score_id=score_id,
        previous_stats=stats_result.previous_stats,
        current_stats=stats_result.current_stats,
        previous_first_place_score=previous_first_place_score,
        unlocked_achievements=unlocked_achievements,
        should_update_rank=stats_result.should_update_rank,
        should_publish_user_stats=stats_result.should_publish_user_stats,
    )


async def apply_score_submission_side_effects(
    score: Score,
    persistence_result: ScoreSubmissionPersistenceResult,
    *,
    publish_user_stats: Callable[[Player], None],
) -> None:
    assert score.player is not None

    if persistence_result.should_update_rank:
        persistence_result.current_stats.rank = await score.player.update_rank(
            score.mode,
        )

    if persistence_result.should_publish_user_stats:
        publish_user_stats(score.player)

    # update their recent score
    score.player.recent_scores[score.mode] = score


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
    unlocked_achievements: Sequence[Achievement] | None = None,
) -> bytes:
    if not score.passed:  # TODO: check if this is correct
        return b"error: no"

    assert score.bmap is not None
    assert score.player is not None

    if unlocked_achievements is not None:
        achievements_to_display = unlocked_achievements
    elif score_can_unlock_achievements(score):
        unlocked_achievements = await unlock_new_achievements(
            score=score,
            achievements=achievements,
            user_achievements=user_achievements,
        )
        achievements_to_display = unlocked_achievements
    else:
        achievements_to_display = []

    return build_submission_charts(
        score=score,
        previous_stats=previous_stats,
        current_stats=current_stats,
        achievements=achievements_to_display,
        domain=domain,
    )
