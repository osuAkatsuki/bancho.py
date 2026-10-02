from __future__ import annotations

import asyncio
import random
import secrets
import time
from collections import defaultdict
from functools import partial
from pathlib import Path
from time import perf_counter_ns
from typing import Any
from typing import cast

import httpx

import app.packets
import app.runtime as runtime_service_helpers
import app.settings
import app.utils
from app.application import Application
from app.application import BackgroundTaskSupervisor
from app.application import RuntimeResources
from app.bg_loops import HousekeepingService
from app.caches import ApplicationCaches
from app.discord import Webhook
from app.objects.beatmap import Beatmap
from app.objects.player import Player
from app.objects.score import Score
from app.repositories.container import Repositories
from app.repositories.container import build_repositories
from app.service_container import ApplicationServices
from app.services.account_settings import AccountSettingsService
from app.services.accounts import AccountRegistrationService
from app.services.avatars import AvatarsService
from app.services.bancho import BanchoAuthenticationService
from app.services.bancho import BanchoLoginService
from app.services.beatmap_leaderboards import BeatmapLeaderboardService
from app.services.beatmaps import BeatmapsService
from app.services.captcha import CAPTCHA_VERIFY_URLS
from app.services.captcha import CaptchaService
from app.services.clans import ClansService
from app.services.client_integrity import ClientIntegrityService
from app.services.comments import CommentsService
from app.services.direct_search import DirectSearchParams
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
from app.services.scores import ScoreDomainService
from app.services.scores import ScoresService
from app.services.screenshots import ScreenshotService
from app.services.session_bootstrap import SessionBootstrapService
from app.services.tourney_pools import TourneyPoolsService
from app.services.web_sessions import WebSessionsService
from app.sessions import SessionState

AVATARS_PATH = Path.cwd() / ".data/avatars"
SCREENSHOTS_PATH = Path.cwd() / ".data/ss"
REPLAYS_PATH = Path.cwd() / ".data/osr"
BEATMAPS_PATH = Path.cwd() / ".data/osu"


def build_services(
    *,
    resources: RuntimeResources,
    caches: ApplicationCaches,
    sessions: SessionState,
    repositories: Repositories,
    score_submission_locks: defaultdict[str, Any],
    background_tasks: BackgroundTaskSupervisor,
) -> ApplicationServices:
    """Build the service graph from explicit application-owned dependencies."""

    async def fetch_mirror_search(
        url: str,
        *,
        params: DirectSearchParams,
    ) -> httpx.Response:
        http_params: dict[str, str | int | float | bool | None] = {
            "amount": params["amount"],
            "offset": params["offset"],
        }
        for key in ("query", "mode", "status"):
            if key in params:
                http_params[key] = params[key]
        return await resources.http_client.get(url, params=http_params)

    def increment_metric(metric: str) -> None:
        if resources.datadog is not None:
            resources.datadog.increment(metric)  # type: ignore[no-untyped-call]

    def decrement_online_players() -> None:
        if resources.datadog is not None:
            resources.datadog.decrement("bancho.online_players")  # type: ignore[no-untyped-call]

    def send_notification(player: Player, message: str) -> None:
        player.enqueue(app.packets.notification(message))

    def publish_user_stats(player: Player) -> None:
        sessions.players.enqueue(app.packets.user_stats(player))

    async def record_strange_occurrence_stacktrace() -> None:
        await runtime_service_helpers.log_strange_occurrence(
            app.utils.get_appropriate_stacktrace(),
            http_client=resources.http_client,
        )

    def send_audit_log(message: str) -> None:
        if app.settings.DISCORD_AUDIT_LOG_WEBHOOK:
            webhook = Webhook(
                app.settings.DISCORD_AUDIT_LOG_WEBHOOK,
                content=message,
            )
            background_tasks.schedule(webhook.post(resources.http_client))

    async def post_captcha_siteverify(
        url: str,
        data: dict[str, str],
    ) -> dict[str, Any]:
        response = await resources.http_client.post(url, data=data)
        response.raise_for_status()
        return cast("dict[str, Any]", response.json())

    bancho_authentication = BanchoAuthenticationService(
        users=repositories.users,
        online_players=sessions.players,
        password_cache=caches.passwords,
    )
    player_leaderboards = PlayerLeaderboardsService(
        stats=repositories.stats,
        leaderboard_ranks=repositories.leaderboard_ranks,
    )
    player_sessions = PlayerSessionService(
        players=sessions.players,
        channels=sessions.channels,
        matches=sessions.matches,
        bot=sessions.bot,
        decrement_online_players=decrement_online_players,
        debug=app.settings.DEBUG,
    )
    player_data = PlayerDataService(
        users=repositories.users,
        stats=repositories.stats,
        leaderboard_ranks=repositories.leaderboard_ranks,
        schedule_background=background_tasks.schedule,
    )
    player_moderation = PlayerModerationService(
        users=repositories.users,
        logs=repositories.logs,
        leaderboard_ranks=repositories.leaderboard_ranks,
        player_data=player_data,
        player_sessions=player_sessions,
        broadcast_packet=sessions.players.enqueue,
        send_audit_log=send_audit_log,
    )

    async def restrict_player(player: Player, reason: str) -> None:
        await player_moderation.restrict(
            player,
            admin=sessions.bot,
            reason=reason,
        )

    async def fetch_player_by_id(player_id: int) -> Player | None:
        return await players.fetch_player_session(
            user_id=player_id,
            username=None,
        )

    players = PlayersService(
        users=repositories.users,
        stats=repositories.stats,
        online_players=sessions.players,
        player_leaderboards=player_leaderboards,
        country_codes=runtime_service_helpers.country_codes,
    )
    score_leaderboards = ScoreLeaderboardsService(scores=repositories.scores)
    beatmaps = BeatmapsService(
        maps=repositories.maps,
        database=resources.database,
        http_client=resources.http_client,
        caches=caches,
        beatmaps_path=BEATMAPS_PATH,
        osu_api_key=(
            str(app.settings.OSU_API_KEY) if app.settings.OSU_API_KEY else None
        ),
        debug=app.settings.DEBUG,
    )
    performance = PerformanceService()
    score_domain = ScoreDomainService(
        scores=repositories.scores,
        stats=repositories.stats,
        fetch_beatmap=beatmaps.fetch_by_md5,
        fetch_player=fetch_player_by_id,
        performance=performance,
        beatmaps_path=BEATMAPS_PATH,
    )

    def schedule_replay_view_increment(score: Score) -> None:
        background_tasks.schedule(score_domain.increment_replay_views(score))

    if (
        app.settings.CAPTCHA_PROVIDER is not None
        and app.settings.CAPTCHA_PROVIDER not in CAPTCHA_VERIFY_URLS
    ):
        raise ValueError(
            f"Unsupported CAPTCHA_PROVIDER {app.settings.CAPTCHA_PROVIDER!r}; "
            f"must be one of {', '.join(CAPTCHA_VERIFY_URLS)}.",
        )

    return ApplicationServices(
        account_registration=AccountRegistrationService(
            users=repositories.users,
            stats=repositories.stats,
            database=resources.database,
            password_cache=caches.passwords,
            ip_resolver=resources.ip_resolver,
            fetch_geoloc=partial(
                runtime_service_helpers.fetch_geoloc,
                http_client=resources.http_client,
            ),
            increment_metric=increment_metric,
            ingame_registration_disallowed=app.settings.DISALLOW_INGAME_REGISTRATION,
            disallowed_names=app.settings.DISALLOWED_NAMES,
            disallowed_passwords=app.settings.DISALLOWED_PASSWORDS,
        ),
        account_settings=AccountSettingsService(
            users=repositories.users,
            stats=repositories.stats,
            leaderboard_ranks=repositories.leaderboard_ranks,
            authentication=bancho_authentication,
            online_players=sessions.players,
            password_cache=caches.passwords,
            disallowed_names=app.settings.DISALLOWED_NAMES,
            disallowed_passwords=app.settings.DISALLOWED_PASSWORDS,
        ),
        avatars=AvatarsService(avatars_path=AVATARS_PATH),
        bancho_authentication=bancho_authentication,
        bancho_login=BanchoLoginService(
            authentication=bancho_authentication,
            users=repositories.users,
            ingame_logins=repositories.ingame_logins,
            client_hashes=repositories.client_hashes,
            mail=repositories.mail,
        ),
        beatmap_info=BeatmapInfoService(
            maps=repositories.maps,
            scores=repositories.scores,
        ),
        beatmap_leaderboards=BeatmapLeaderboardService(
            score_leaderboards=score_leaderboards,
            clans=repositories.clans,
            maps=repositories.maps,
            ratings=repositories.ratings,
            beatmap_fetcher=beatmaps.fetch_by_md5,
            unsubmitted_cache=caches.unsubmitted,
            needs_update_cache=caches.needs_update,
            beatmapset_cache=caches.beatmapsets,
            publish_user_stats=publish_user_stats,
            increment_metric=increment_metric,
            log_strange_occurrence=partial(
                runtime_service_helpers.log_strange_occurrence,
                http_client=resources.http_client,
            ),
            get_appropriate_stacktrace=app.utils.get_appropriate_stacktrace,
        ),
        beatmap_rating=BeatmapRatingService(
            ratings=repositories.ratings,
            beatmap_cache=caches.beatmaps,
        ),
        beatmap_set=BeatmapSetService(maps=repositories.maps),
        beatmaps=beatmaps,
        captcha=CaptchaService(
            provider=app.settings.CAPTCHA_PROVIDER,
            secret=app.settings.CAPTCHA_SECRET,
            post_siteverify=post_captcha_siteverify,
        ),
        clans=ClansService(
            clans=repositories.clans,
            users=repositories.users,
            online_players=sessions.players,
            database=resources.database,
        ),
        client_integrity=ClientIntegrityService(
            restriction_roll=random.randrange,
            send_notification=send_notification,
            restrict_player=restrict_player,
            logout_player=player_sessions.logout,
        ),
        comments=CommentsService(
            comments=repositories.comments,
            schedule_latest_activity_update=player_data.schedule_latest_activity_update,
        ),
        direct_search=DirectSearchService(
            mirror_search_endpoint=app.settings.MIRROR_SEARCH_ENDPOINT,
            fetch_mirror_search=fetch_mirror_search,
        ),
        favourites=FavouritesService(favourites=repositories.favourites),
        housekeeping=HousekeepingService(
            users=repositories.users,
            online_players=sessions.players,
            fetch_player=fetch_player_by_id,
            remove_privileges=player_moderation.remove_privileges,
            notify_player=send_notification,
            logout_player=player_sessions.logout,
            clear_bot_status_cache=app.packets.bot_stats.cache_clear,
            current_time=time.time,
            debug=app.settings.DEBUG,
        ),
        mail_read=MailReadService(
            mail=repositories.mail,
            players=players,
        ),
        maps=MapsService(maps=repositories.maps),
        performance=performance,
        player_leaderboards=player_leaderboards,
        player_data=player_data,
        player_moderation=player_moderation,
        player_sessions=player_sessions,
        players=players,
        problem_reporting=ProblemReportingService(
            report_occurrence=partial(
                runtime_service_helpers.log_strange_occurrence,
                http_client=resources.http_client,
            ),
        ),
        relationships=RelationshipsService(
            relationships=repositories.relationships,
            users=repositories.users,
            online_players=sessions.players,
        ),
        replays=ReplayService(
            replays_path=REPLAYS_PATH,
            fetch_score=score_domain.fetch,
            fetch_replay_header=repositories.scores.fetch_replay_header,
            schedule_replay_view_increment=schedule_replay_view_increment,
        ),
        score_leaderboards=score_leaderboards,
        score_submission=ScoreSubmissionService(
            replays_path=REPLAYS_PATH,
            score_domain=score_domain,
            fetch_beatmap=beatmaps.fetch_by_md5,
            bancho_authentication=bancho_authentication,
            score_submission_locks=score_submission_locks,
            database=resources.database,
            scores=repositories.scores,
            stats=repositories.stats,
            maps=repositories.maps,
            achievements=repositories.achievements,
            user_achievements=repositories.user_achievements,
            ensure_osu_file_is_available=beatmaps.ensure_osu_file_is_available,
            publish_user_stats=publish_user_stats,
            send_personal_best_notification=send_notification,
            announce_channel=sessions.channels.get_by_name("#announce"),
            domain=app.settings.DOMAIN,
            increment_metric=increment_metric,
            record_submission_integrity_failure=record_strange_occurrence_stacktrace,
            restrict_player=restrict_player,
            schedule_player_activity_update=player_data.schedule_latest_activity_update,
            update_player_rank=player_data.update_rank,
        ),
        scores=ScoresService(
            scores=repositories.scores,
            users=repositories.users,
            clans=repositories.clans,
            fetch_beatmap=beatmaps.fetch_by_md5,
        ),
        screenshots=ScreenshotService(
            screenshots_path=SCREENSHOTS_PATH,
            token_urlsafe=secrets.token_urlsafe,
            log_strange_occurrence=partial(
                runtime_service_helpers.log_strange_occurrence,
                http_client=resources.http_client,
            ),
        ),
        tourney_pools=TourneyPoolsService(
            tourney_pools=repositories.tourney_pools,
            tourney_pool_maps=repositories.tourney_pool_maps,
            database=resources.database,
        ),
        web_sessions=WebSessionsService(
            authentication=bancho_authentication,
            users=repositories.users,
            web_sessions=repositories.web_sessions,
            generate_token=lambda: secrets.token_urlsafe(32),
        ),
    )


async def build_application(resources: RuntimeResources) -> Application:
    """Compose one complete application graph after infrastructure is ready."""
    from app.api.domains.cho import build_packet_router
    from app.api.domains.cho import write_chat_log
    from app.commands import build_command_router
    from app.logging import magnitude_fmt_time

    caches = ApplicationCaches()
    repositories = build_repositories(resources.database, resources.redis)
    sessions = await SessionBootstrapService(
        channels=repositories.channels,
        users=repositories.users,
    ).build()
    score_submission_locks: defaultdict[str, asyncio.Lock] = defaultdict(
        asyncio.Lock,
    )
    background_tasks = BackgroundTaskSupervisor(resources.loop)
    services = build_services(
        resources=resources,
        caches=caches,
        sessions=sessions,
        repositories=repositories,
        score_submission_locks=score_submission_locks,
        background_tasks=background_tasks,
    )

    async def fetch_beatmap_by_md5(beatmap_md5: str) -> Beatmap | None:
        return await services.beatmaps.fetch_by_md5(beatmap_md5)

    command_router = build_command_router(
        prefix=app.settings.COMMAND_PREFIX,
        clock=perf_counter_ns,
        format_elapsed=magnitude_fmt_time,
        developer_mode=app.settings.DEVELOPER_MODE,
        players=sessions.players,
        players_service=services.players,
        channels=sessions.channels,
        bot=sessions.bot,
        api_keys=sessions.api_keys,
        database=resources.database,
        loop=resources.loop,
        beatmap_cache=caches.beatmaps,
        beatmapset_cache=caches.beatmapsets,
        users=repositories.users,
        map_requests=repositories.map_requests,
        maps=repositories.maps,
        logs=repositories.logs,
        clans_repository=repositories.clans,
        clans=services.clans,
        tourney_pools=services.tourney_pools,
        performance=services.performance,
        player_sessions=services.player_sessions,
        player_moderation=services.player_moderation,
        relationships=services.relationships,
        fetch_beatmap_by_id=services.beatmaps.fetch_by_id,
        fetch_beatmap_by_md5=fetch_beatmap_by_md5,
        ensure_osu_file_available=services.beatmaps.ensure_osu_file_is_available,
    )
    packet_router = build_packet_router(
        players=sessions.players,
        channels=sessions.channels,
        matches=sessions.matches,
        bot=sessions.bot,
        command_router=command_router,
        player_data_service=services.player_data,
        player_session_service=services.player_sessions,
        players_service=services.players,
        relationships_service=services.relationships,
        mail_repository=repositories.mail,
        performance_service=services.performance,
        problem_reporting_service=services.problem_reporting,
        fetch_beatmap_by_id=services.beatmaps.fetch_by_id,
        fetch_beatmap_by_md5=fetch_beatmap_by_md5,
        ensure_osu_file_available=services.beatmaps.ensure_osu_file_is_available,
        beatmaps_path=BEATMAPS_PATH,
        pp_cached_accuracies=app.settings.PP_CACHED_ACCURACIES,
        clock=time.time,
        nanosecond_clock=perf_counter_ns,
        chat_logger=write_chat_log,
        get_stacktrace=app.utils.get_appropriate_stacktrace,
        schedule_background=background_tasks.schedule,
    )

    return Application(
        resources=resources,
        caches=caches,
        sessions=sessions,
        repositories=repositories,
        services=services,
        command_router=command_router,
        packet_router=packet_router,
        score_submission_locks=score_submission_locks,
        background_tasks=background_tasks,
    )
