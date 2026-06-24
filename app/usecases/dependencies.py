from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

import app.state
import app.state.services
from app.repositories.achievements import AchievementsRepository
from app.repositories.maps import MapsRepository
from app.repositories.scores import ScoresRepository
from app.repositories.stats import StatsRepository
from app.repositories.user_achievements import UserAchievementsRepository

if TYPE_CHECKING:
    from app.objects.player import Player
    from app.usecases.score_leaderboards import ScoreLeaderboardsService
    from app.usecases.score_submission import AnnouncementChannel
    from app.usecases.score_submission import BeatmapFetcher
    from app.usecases.score_submission import OsuFileAvailabilityChecker
    from app.usecases.score_submission import PlayerAuthenticator
    from app.usecases.score_submission import ScoreSubmissionService


@dataclass(frozen=True)
class Repositories:
    achievements: AchievementsRepository
    maps: MapsRepository
    scores: ScoresRepository
    stats: StatsRepository
    user_achievements: UserAchievementsRepository


@dataclass(frozen=True)
class ScoreSubmissionServiceConfig:
    replays_path: Path
    restriction_admin: Player
    fetch_beatmap: BeatmapFetcher
    authenticate_player: PlayerAuthenticator
    ensure_osu_file_is_available: OsuFileAvailabilityChecker
    publish_user_stats: Callable[[Player], None]
    send_personal_best_notification: Callable[[Player, str], None]
    announce_channel: AnnouncementChannel | None
    domain: str
    increment_metric: Callable[[str], None]
    record_submission_integrity_failure: Callable[[], Awaitable[None]]


_score_submission_service_config: ScoreSubmissionServiceConfig | None = None


@cache
def get_repositories() -> Repositories:
    database = app.state.services.database

    return Repositories(
        achievements=AchievementsRepository(database),
        maps=MapsRepository(database),
        scores=ScoresRepository(database),
        stats=StatsRepository(database),
        user_achievements=UserAchievementsRepository(database),
    )


@cache
def get_score_leaderboards_service() -> ScoreLeaderboardsService:
    from app.usecases.score_leaderboards import ScoreLeaderboardsService

    repositories = get_repositories()

    return ScoreLeaderboardsService(scores=repositories.scores)


def configure_score_submission_service(config: ScoreSubmissionServiceConfig) -> None:
    global _score_submission_service_config

    _score_submission_service_config = config
    get_score_submission_service.cache_clear()


@cache
def get_score_submission_service() -> ScoreSubmissionService:
    from app.usecases.score_submission import ScoreSubmissionService

    if _score_submission_service_config is None:
        raise RuntimeError("Score submission service has not been configured.")

    repositories = get_repositories()

    return ScoreSubmissionService(
        replays_path=_score_submission_service_config.replays_path,
        restriction_admin=_score_submission_service_config.restriction_admin,
        fetch_beatmap=_score_submission_service_config.fetch_beatmap,
        authenticate_player=_score_submission_service_config.authenticate_player,
        score_submission_locks=app.state.score_submission_locks,
        database=app.state.services.database,
        scores=repositories.scores,
        stats=repositories.stats,
        maps=repositories.maps,
        achievements=repositories.achievements,
        user_achievements=repositories.user_achievements,
        ensure_osu_file_is_available=(
            _score_submission_service_config.ensure_osu_file_is_available
        ),
        publish_user_stats=_score_submission_service_config.publish_user_stats,
        send_personal_best_notification=(
            _score_submission_service_config.send_personal_best_notification
        ),
        announce_channel=_score_submission_service_config.announce_channel,
        domain=_score_submission_service_config.domain,
        increment_metric=_score_submission_service_config.increment_metric,
        record_submission_integrity_failure=(
            _score_submission_service_config.record_submission_integrity_failure
        ),
    )
