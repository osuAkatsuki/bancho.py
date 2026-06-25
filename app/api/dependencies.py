from __future__ import annotations

from typing import Annotated

from fastapi import Depends

import app.state.services
import app.state.sessions
from app import settings
from app import state
from app.adapters import score_submission as score_submission_adapters
from app.objects.beatmap import ensure_osu_file_is_available
from app.repositories.achievements import AchievementsRepository
from app.repositories.clans import ClansRepository
from app.repositories.client_hashes import ClientHashesRepository
from app.repositories.comments import CommentsRepository
from app.repositories.favourites import FavouritesRepository
from app.repositories.ingame_logins import IngameLoginsRepository
from app.repositories.mail import MailRepository
from app.repositories.maps import MapsRepository
from app.repositories.ratings import RatingsRepository
from app.repositories.scores import ScoresRepository
from app.repositories.stats import StatsRepository
from app.repositories.tourney_pool_maps import TourneyPoolMapsRepository
from app.repositories.tourney_pools import TourneyPoolsRepository
from app.repositories.user_achievements import UserAchievementsRepository
from app.repositories.users import UsersRepository
from app.services.bancho import BanchoLoginService
from app.services.clans import ClansService
from app.services.maps import MapsService
from app.services.osu_web import AccountRegistrationService
from app.services.osu_web import BeatmapInfoService
from app.services.osu_web import BeatmapRatingService
from app.services.osu_web import BeatmapSetService
from app.services.osu_web import CommentsService
from app.services.osu_web import FavouritesService
from app.services.osu_web import MailReadService
from app.services.osu_web import OsuLeaderboardSupportService
from app.services.players import PlayersService
from app.services.public_api import PublicApiService
from app.services.score_leaderboards import ScoreLeaderboardsService
from app.services.score_submission import ScoreSubmissionService
from app.services.scores import ScoresService


def get_achievements_repository() -> AchievementsRepository:
    return AchievementsRepository(app.state.services.database)


def get_clans_repository() -> ClansRepository:
    return ClansRepository(app.state.services.database)


def get_client_hashes_repository() -> ClientHashesRepository:
    return ClientHashesRepository(app.state.services.database)


def get_comments_repository() -> CommentsRepository:
    return CommentsRepository(app.state.services.database)


def get_favourites_repository() -> FavouritesRepository:
    return FavouritesRepository(app.state.services.database)


def get_ingame_logins_repository() -> IngameLoginsRepository:
    return IngameLoginsRepository(app.state.services.database)


def get_mail_repository() -> MailRepository:
    return MailRepository(app.state.services.database)


def get_maps_repository() -> MapsRepository:
    return MapsRepository(app.state.services.database)


def get_ratings_repository() -> RatingsRepository:
    return RatingsRepository(app.state.services.database)


def get_scores_repository() -> ScoresRepository:
    return ScoresRepository(app.state.services.database)


def get_stats_repository() -> StatsRepository:
    return StatsRepository(app.state.services.database)


def get_tourney_pool_maps_repository() -> TourneyPoolMapsRepository:
    return TourneyPoolMapsRepository(app.state.services.database)


def get_tourney_pools_repository() -> TourneyPoolsRepository:
    return TourneyPoolsRepository(app.state.services.database)


def get_user_achievements_repository() -> UserAchievementsRepository:
    return UserAchievementsRepository(app.state.services.database)


def get_users_repository() -> UsersRepository:
    return UsersRepository(app.state.services.database)


def get_clans_service(
    clans: Annotated[ClansRepository, Depends(get_clans_repository)],
) -> ClansService:
    return ClansService(clans=clans)


def get_bancho_login_service(
    users: Annotated[UsersRepository, Depends(get_users_repository)],
    ingame_logins: Annotated[
        IngameLoginsRepository,
        Depends(get_ingame_logins_repository),
    ],
    client_hashes: Annotated[
        ClientHashesRepository,
        Depends(get_client_hashes_repository),
    ],
    mail: Annotated[MailRepository, Depends(get_mail_repository)],
) -> BanchoLoginService:
    return BanchoLoginService(
        users=users,
        ingame_logins=ingame_logins,
        client_hashes=client_hashes,
        mail=mail,
        password_cache=state.cache.bcrypt,
    )


def get_maps_service(
    maps: Annotated[MapsRepository, Depends(get_maps_repository)],
) -> MapsService:
    return MapsService(maps=maps)


def get_account_registration_service(
    users: Annotated[UsersRepository, Depends(get_users_repository)],
    stats: Annotated[StatsRepository, Depends(get_stats_repository)],
) -> AccountRegistrationService:
    return AccountRegistrationService(
        users=users,
        stats=stats,
        database=app.state.services.database,
        password_cache=state.cache.bcrypt,
        ip_resolver=app.state.services.ip_resolver,
        fetch_geoloc=app.state.services.fetch_geoloc,
        disallowed_names=settings.DISALLOWED_NAMES,
        disallowed_passwords=settings.DISALLOWED_PASSWORDS,
    )


def get_beatmap_info_service(
    maps: Annotated[MapsRepository, Depends(get_maps_repository)],
    scores: Annotated[ScoresRepository, Depends(get_scores_repository)],
) -> BeatmapInfoService:
    return BeatmapInfoService(maps=maps, scores=scores)


def get_beatmap_rating_service(
    ratings: Annotated[RatingsRepository, Depends(get_ratings_repository)],
) -> BeatmapRatingService:
    return BeatmapRatingService(
        ratings=ratings,
        beatmap_cache=state.cache.beatmap,
    )


def get_beatmap_set_service(
    maps: Annotated[MapsRepository, Depends(get_maps_repository)],
) -> BeatmapSetService:
    return BeatmapSetService(maps=maps)


def get_comments_service(
    comments: Annotated[CommentsRepository, Depends(get_comments_repository)],
) -> CommentsService:
    return CommentsService(comments=comments)


def get_favourites_service(
    favourites: Annotated[FavouritesRepository, Depends(get_favourites_repository)],
) -> FavouritesService:
    return FavouritesService(favourites=favourites)


def get_mail_read_service(
    mail: Annotated[MailRepository, Depends(get_mail_repository)],
) -> MailReadService:
    return MailReadService(
        mail=mail,
        players=app.state.sessions.players,
    )


def get_osu_leaderboard_support_service(
    clans: Annotated[ClansRepository, Depends(get_clans_repository)],
    maps: Annotated[MapsRepository, Depends(get_maps_repository)],
    ratings: Annotated[RatingsRepository, Depends(get_ratings_repository)],
) -> OsuLeaderboardSupportService:
    return OsuLeaderboardSupportService(
        clans=clans,
        maps=maps,
        ratings=ratings,
    )


def get_players_service(
    users: Annotated[UsersRepository, Depends(get_users_repository)],
    stats: Annotated[StatsRepository, Depends(get_stats_repository)],
) -> PlayersService:
    return PlayersService(
        users=users,
        stats=stats,
        online_players=app.state.sessions.players,
    )


def get_public_api_service(
    users: Annotated[UsersRepository, Depends(get_users_repository)],
    stats: Annotated[StatsRepository, Depends(get_stats_repository)],
    clans: Annotated[ClansRepository, Depends(get_clans_repository)],
    scores: Annotated[ScoresRepository, Depends(get_scores_repository)],
    tourney_pools: Annotated[
        TourneyPoolsRepository,
        Depends(get_tourney_pools_repository),
    ],
    tourney_pool_maps: Annotated[
        TourneyPoolMapsRepository,
        Depends(get_tourney_pool_maps_repository),
    ],
) -> PublicApiService:
    return PublicApiService(
        database=app.state.services.database,
        users=users,
        stats=stats,
        clans=clans,
        scores=scores,
        tourney_pools=tourney_pools,
        tourney_pool_maps=tourney_pool_maps,
    )


def get_score_leaderboards_service(
    scores: Annotated[ScoresRepository, Depends(get_scores_repository)],
) -> ScoreLeaderboardsService:
    return ScoreLeaderboardsService(scores=scores)


def get_score_submission_service(
    scores: Annotated[ScoresRepository, Depends(get_scores_repository)],
    stats: Annotated[StatsRepository, Depends(get_stats_repository)],
    maps: Annotated[MapsRepository, Depends(get_maps_repository)],
    achievements: Annotated[
        AchievementsRepository,
        Depends(get_achievements_repository),
    ],
    user_achievements: Annotated[
        UserAchievementsRepository,
        Depends(get_user_achievements_repository),
    ],
) -> ScoreSubmissionService:
    return ScoreSubmissionService(
        replays_path=score_submission_adapters.REPLAYS_PATH,
        restriction_admin=app.state.sessions.bot,
        fetch_beatmap=score_submission_adapters.fetch_score_submission_beatmap,
        authenticate_player=score_submission_adapters.authenticate_score_submitter,
        score_submission_locks=app.state.score_submission_locks,
        database=app.state.services.database,
        scores=scores,
        stats=stats,
        maps=maps,
        achievements=achievements,
        user_achievements=user_achievements,
        ensure_osu_file_is_available=ensure_osu_file_is_available,
        publish_user_stats=score_submission_adapters.publish_score_submitter_stats,
        send_personal_best_notification=(
            score_submission_adapters.send_personal_best_notification
        ),
        announce_channel=app.state.sessions.channels.get_by_name("#announce"),
        domain=settings.DOMAIN,
        increment_metric=score_submission_adapters.increment_score_submission_metric,
        record_submission_integrity_failure=(
            score_submission_adapters.record_score_submission_integrity_failure
        ),
    )


def get_scores_service(
    scores: Annotated[ScoresRepository, Depends(get_scores_repository)],
) -> ScoresService:
    return ScoresService(scores=scores)
