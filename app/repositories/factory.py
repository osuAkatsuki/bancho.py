from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import app.state.services
from app.repositories.achievements import AchievementsRepository
from app.repositories.channels import ChannelsRepository
from app.repositories.clans import ClansRepository
from app.repositories.client_hashes import ClientHashesRepository
from app.repositories.comments import CommentsRepository
from app.repositories.favourites import FavouritesRepository
from app.repositories.ingame_logins import IngameLoginsRepository
from app.repositories.logs import LogsRepository
from app.repositories.mail import MailRepository
from app.repositories.map_requests import MapRequestsRepository
from app.repositories.maps import MapsRepository
from app.repositories.ratings import RatingsRepository
from app.repositories.scores import ScoresRepository
from app.repositories.stats import StatsRepository
from app.repositories.tourney_pool_maps import TourneyPoolMapsRepository
from app.repositories.tourney_pools import TourneyPoolsRepository
from app.repositories.user_achievements import UserAchievementsRepository
from app.repositories.users import UsersRepository


@dataclass(frozen=True)
class Repositories:
    achievements: AchievementsRepository
    channels: ChannelsRepository
    clans: ClansRepository
    client_hashes: ClientHashesRepository
    comments: CommentsRepository
    favourites: FavouritesRepository
    ingame_logins: IngameLoginsRepository
    logs: LogsRepository
    mail: MailRepository
    map_requests: MapRequestsRepository
    maps: MapsRepository
    ratings: RatingsRepository
    scores: ScoresRepository
    stats: StatsRepository
    tourney_pool_maps: TourneyPoolMapsRepository
    tourney_pools: TourneyPoolsRepository
    user_achievements: UserAchievementsRepository
    users: UsersRepository


@cache
def get_repositories() -> Repositories:
    database = app.state.services.database

    return Repositories(
        achievements=AchievementsRepository(database),
        channels=ChannelsRepository(database),
        clans=ClansRepository(database),
        client_hashes=ClientHashesRepository(database),
        comments=CommentsRepository(database),
        favourites=FavouritesRepository(database),
        ingame_logins=IngameLoginsRepository(database),
        logs=LogsRepository(database),
        mail=MailRepository(database),
        map_requests=MapRequestsRepository(database),
        maps=MapsRepository(database),
        ratings=RatingsRepository(database),
        scores=ScoresRepository(database),
        stats=StatsRepository(database),
        tourney_pool_maps=TourneyPoolMapsRepository(database),
        tourney_pools=TourneyPoolsRepository(database),
        user_achievements=UserAchievementsRepository(database),
        users=UsersRepository(database),
    )
