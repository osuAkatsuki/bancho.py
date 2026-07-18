from __future__ import annotations

from typing import Annotated
from typing import cast

from fastapi import Depends
from fastapi import Request

from app.application import Application
from app.objects.collections import Matches
from app.repositories.achievements import AchievementsRepository
from app.repositories.clans import ClansRepository
from app.repositories.client_hashes import ClientHashesRepository
from app.repositories.comments import CommentsRepository
from app.repositories.favourites import FavouritesRepository
from app.repositories.ingame_logins import IngameLoginsRepository
from app.repositories.leaderboard_ranks import LeaderboardRanksRepository
from app.repositories.mail import MailRepository
from app.repositories.maps import MapsRepository
from app.repositories.ratings import RatingsRepository
from app.repositories.relationships import RelationshipsRepository
from app.repositories.scores import ScoresRepository
from app.repositories.stats import StatsRepository
from app.repositories.tourney_pool_maps import TourneyPoolMapsRepository
from app.repositories.tourney_pools import TourneyPoolsRepository
from app.repositories.user_achievements import UserAchievementsRepository
from app.repositories.users import UsersRepository
from app.repositories.web_sessions import WebSessionsRepository
from app.services.account_settings import AccountSettingsService
from app.services.accounts import AccountRegistrationService
from app.services.avatars import AvatarsService
from app.services.bancho import BanchoAuthenticationService
from app.services.bancho import BanchoLoginService
from app.services.beatmap_leaderboards import BeatmapLeaderboardService
from app.services.beatmaps import BeatmapsService
from app.services.captcha import CaptchaService
from app.services.clans import ClansService
from app.services.client_integrity import ClientIntegrityService
from app.services.comments import CommentsService
from app.services.direct_search import DirectSearchService
from app.services.favourites import FavouritesService
from app.services.mail import MailReadService
from app.services.maps import BeatmapInfoService
from app.services.maps import BeatmapRatingService
from app.services.maps import BeatmapSetService
from app.services.maps import MapsService
from app.services.performance import PerformanceService
from app.services.player_data import PlayerDataService
from app.services.player_leaderboards import PlayerLeaderboardsService
from app.services.player_moderation import PlayerModerationService
from app.services.player_sessions import PlayerSessionService
from app.services.players import PlayersService
from app.services.problem_reporting import ProblemReportingService
from app.services.relationships import RelationshipsService
from app.services.replays import ReplayService
from app.services.score_leaderboards import ScoreLeaderboardsService
from app.services.score_submission import ScoreSubmissionService
from app.services.scores import ScoresService
from app.services.screenshots import ScreenshotService
from app.services.tourney_pools import TourneyPoolsService
from app.services.web_sessions import WebSessionsService


def get_application(request: Request) -> Application:
    """Resolve the application graph at the outer FastAPI boundary."""

    return cast(Application, request.app.state.application)


ApplicationDependency = Annotated[Application, Depends(get_application)]


def get_api_keys(app: ApplicationDependency) -> dict[str, int]:
    return app.sessions.api_keys


def get_matches(app: ApplicationDependency) -> Matches:
    return app.sessions.matches


def get_achievements_repository(app: ApplicationDependency) -> AchievementsRepository:
    return app.repositories.achievements


def get_clans_repository(app: ApplicationDependency) -> ClansRepository:
    return app.repositories.clans


def get_client_hashes_repository(app: ApplicationDependency) -> ClientHashesRepository:
    return app.repositories.client_hashes


def get_comments_repository(app: ApplicationDependency) -> CommentsRepository:
    return app.repositories.comments


def get_favourites_repository(app: ApplicationDependency) -> FavouritesRepository:
    return app.repositories.favourites


def get_ingame_logins_repository(app: ApplicationDependency) -> IngameLoginsRepository:
    return app.repositories.ingame_logins


def get_mail_repository(app: ApplicationDependency) -> MailRepository:
    return app.repositories.mail


def get_leaderboard_ranks_repository(
    app: ApplicationDependency,
) -> LeaderboardRanksRepository:
    return app.repositories.leaderboard_ranks


def get_maps_repository(app: ApplicationDependency) -> MapsRepository:
    return app.repositories.maps


def get_ratings_repository(app: ApplicationDependency) -> RatingsRepository:
    return app.repositories.ratings


def get_relationships_repository(app: ApplicationDependency) -> RelationshipsRepository:
    return app.repositories.relationships


def get_scores_repository(app: ApplicationDependency) -> ScoresRepository:
    return app.repositories.scores


def get_stats_repository(app: ApplicationDependency) -> StatsRepository:
    return app.repositories.stats


def get_tourney_pool_maps_repository(
    app: ApplicationDependency,
) -> TourneyPoolMapsRepository:
    return app.repositories.tourney_pool_maps


def get_tourney_pools_repository(
    app: ApplicationDependency,
) -> TourneyPoolsRepository:
    return app.repositories.tourney_pools


def get_user_achievements_repository(
    app: ApplicationDependency,
) -> UserAchievementsRepository:
    return app.repositories.user_achievements


def get_users_repository(app: ApplicationDependency) -> UsersRepository:
    return app.repositories.users


def get_web_sessions_repository(
    app: ApplicationDependency,
) -> WebSessionsRepository:
    return app.repositories.web_sessions


def get_clans_service(app: ApplicationDependency) -> ClansService:
    return app.services.clans


def get_bancho_authentication_service(
    app: ApplicationDependency,
) -> BanchoAuthenticationService:
    return app.services.bancho_authentication


def get_bancho_login_service(app: ApplicationDependency) -> BanchoLoginService:
    return app.services.bancho_login


def get_maps_service(app: ApplicationDependency) -> MapsService:
    return app.services.maps


def get_account_registration_service(
    app: ApplicationDependency,
) -> AccountRegistrationService:
    return app.services.account_registration


def get_account_settings_service(
    app: ApplicationDependency,
) -> AccountSettingsService:
    return app.services.account_settings


def get_avatars_service(app: ApplicationDependency) -> AvatarsService:
    return app.services.avatars


def get_screenshot_service(app: ApplicationDependency) -> ScreenshotService:
    return app.services.screenshots


def get_client_integrity_service(
    app: ApplicationDependency,
) -> ClientIntegrityService:
    return app.services.client_integrity


def get_direct_search_service(app: ApplicationDependency) -> DirectSearchService:
    return app.services.direct_search


def get_beatmap_info_service(app: ApplicationDependency) -> BeatmapInfoService:
    return app.services.beatmap_info


def get_beatmap_rating_service(app: ApplicationDependency) -> BeatmapRatingService:
    return app.services.beatmap_rating


def get_beatmap_set_service(app: ApplicationDependency) -> BeatmapSetService:
    return app.services.beatmap_set


def get_beatmaps_service(app: ApplicationDependency) -> BeatmapsService:
    return app.services.beatmaps


def get_comments_service(app: ApplicationDependency) -> CommentsService:
    return app.services.comments


def get_favourites_service(app: ApplicationDependency) -> FavouritesService:
    return app.services.favourites


def get_mail_read_service(app: ApplicationDependency) -> MailReadService:
    return app.services.mail_read


def get_replay_service(app: ApplicationDependency) -> ReplayService:
    return app.services.replays


def get_player_leaderboards_service(
    app: ApplicationDependency,
) -> PlayerLeaderboardsService:
    return app.services.player_leaderboards


def get_players_service(app: ApplicationDependency) -> PlayersService:
    return app.services.players


def get_player_moderation_service(
    app: ApplicationDependency,
) -> PlayerModerationService:
    return app.services.player_moderation


def get_player_data_service(app: ApplicationDependency) -> PlayerDataService:
    return app.services.player_data


def get_player_session_service(
    app: ApplicationDependency,
) -> PlayerSessionService:
    return app.services.player_sessions


def get_problem_reporting_service(
    app: ApplicationDependency,
) -> ProblemReportingService:
    return app.services.problem_reporting


def get_performance_service(app: ApplicationDependency) -> PerformanceService:
    return app.services.performance


def get_tourney_pools_service(app: ApplicationDependency) -> TourneyPoolsService:
    return app.services.tourney_pools


def get_score_leaderboards_service(
    app: ApplicationDependency,
) -> ScoreLeaderboardsService:
    return app.services.score_leaderboards


def get_beatmap_leaderboard_service(
    app: ApplicationDependency,
) -> BeatmapLeaderboardService:
    return app.services.beatmap_leaderboards


def get_score_submission_service(
    app: ApplicationDependency,
) -> ScoreSubmissionService:
    return app.services.score_submission


def get_relationships_service(app: ApplicationDependency) -> RelationshipsService:
    return app.services.relationships


def get_scores_service(app: ApplicationDependency) -> ScoresService:
    return app.services.scores


def get_captcha_service(app: ApplicationDependency) -> CaptchaService:
    return app.services.captcha


def get_web_sessions_service(app: ApplicationDependency) -> WebSessionsService:
    return app.services.web_sessions
