from __future__ import annotations

from dataclasses import dataclass

from app.bg_loops import HousekeepingService
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


@dataclass(frozen=True)
class ApplicationServices:
    """Root-owned service instances for one application graph."""

    account_registration: AccountRegistrationService
    account_settings: AccountSettingsService
    avatars: AvatarsService
    bancho_authentication: BanchoAuthenticationService
    bancho_login: BanchoLoginService
    beatmap_info: BeatmapInfoService
    beatmap_leaderboards: BeatmapLeaderboardService
    beatmap_rating: BeatmapRatingService
    beatmap_set: BeatmapSetService
    beatmaps: BeatmapsService
    captcha: CaptchaService
    clans: ClansService
    client_integrity: ClientIntegrityService
    comments: CommentsService
    direct_search: DirectSearchService
    favourites: FavouritesService
    housekeeping: HousekeepingService
    mail_read: MailReadService
    maps: MapsService
    performance: PerformanceService
    player_leaderboards: PlayerLeaderboardsService
    player_data: PlayerDataService
    player_moderation: PlayerModerationService
    player_sessions: PlayerSessionService
    players: PlayersService
    problem_reporting: ProblemReportingService
    relationships: RelationshipsService
    replays: ReplayService
    score_leaderboards: ScoreLeaderboardsService
    score_submission: ScoreSubmissionService
    scores: ScoresService
    screenshots: ScreenshotService
    tourney_pools: TourneyPoolsService
    web_sessions: WebSessionsService
