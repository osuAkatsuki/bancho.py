from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import MutableSet
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from urllib.parse import unquote_plus

from app.constants.beatmap_statuses import RankedStatus
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.scoring_metrics import ScoringMetric
from app.objects.beatmap import Beatmap
from app.objects.player import Player
from app.repositories.clans import ClansRepository
from app.repositories.maps import MapsRepository
from app.repositories.ratings import RatingsRepository
from app.repositories.scores import BeatmapLeaderboardScoreRow
from app.services.score_leaderboards import PersonalBestLeaderboardScoreListing
from app.services.score_leaderboards import ScoreLeaderboardsService


class BeatmapSetCacheEntry(Protocol):
    @property
    def maps(self) -> Sequence[Beatmap]: ...


class BeatmapFetcher(Protocol):
    def __call__(self, md5: str, set_id: int = -1) -> Awaitable[Beatmap | None]: ...


@dataclass(frozen=True)
class BeatmapLeaderboardRequest:
    requesting_from_editor_song_select: bool
    leaderboard_type: int
    map_md5: str
    map_filename: str
    mode_arg: int
    map_set_id: int
    mods_arg: int
    aqn_files_found: bool


class BeatmapLeaderboardResultCode(StrEnum):
    FOUND = "found"
    NEEDS_UPDATE = "needs_update"
    NOT_SUBMITTED = "not_submitted"
    NO_LEADERBOARD = "no_leaderboard"


@dataclass(frozen=True)
class BeatmapLeaderboardResult:
    code: BeatmapLeaderboardResultCode
    ranked_status: RankedStatus | None = None
    beatmap_id: int | None = None
    beatmap_set_id: int | None = None
    beatmap_name: str | None = None
    beatmap_rating: float | None = None
    score_rows: list[BeatmapLeaderboardScoreRow] | None = None
    personal_best_score_row: PersonalBestLeaderboardScoreListing | None = None
    personal_best_user_id: int | None = None
    personal_best_display_name: str | None = None


@dataclass(frozen=True)
class BeatmapLeaderboardService:
    score_leaderboards: ScoreLeaderboardsService
    clans: ClansRepository
    maps: MapsRepository
    ratings: RatingsRepository
    beatmap_fetcher: BeatmapFetcher
    unsubmitted_cache: MutableSet[str]
    needs_update_cache: MutableSet[str]
    beatmapset_cache: Mapping[int, BeatmapSetCacheEntry]
    publish_user_stats: Callable[[Player], None]
    increment_metric: Callable[[str], None]
    log_strange_occurrence: Callable[[object], Awaitable[None]]
    get_appropriate_stacktrace: Callable[[], object]

    async def fetch_leaderboard(
        self,
        *,
        player: Player,
        request: BeatmapLeaderboardRequest,
    ) -> BeatmapLeaderboardResult:
        if request.aqn_files_found:
            await self.log_strange_occurrence(self.get_appropriate_stacktrace())

        # check if this md5 has already been  cached as
        # unsubmitted/needs update to reduce osu!api spam
        if request.map_md5 in self.unsubmitted_cache:
            return BeatmapLeaderboardResult(
                code=BeatmapLeaderboardResultCode.NOT_SUBMITTED,
            )
        if request.map_md5 in self.needs_update_cache:
            return BeatmapLeaderboardResult(
                code=BeatmapLeaderboardResultCode.NEEDS_UPDATE,
            )

        mode, mods = self._resolve_score_query_mode_and_mods(
            mode_arg=request.mode_arg,
            mods_arg=request.mods_arg,
        )
        self._update_player_status_if_needed(player, mode=mode, mods=mods)

        scoring_metric: ScoringMetric = "pp" if mode >= GameMode.RELAX_OSU else "score"

        bmap = await self.beatmap_fetcher(request.map_md5, set_id=request.map_set_id)
        if bmap is None:
            return await self._classify_missing_beatmap(request)

        # we've found a beatmap for the request.
        self.increment_metric("bancho.leaderboards_served")

        if bmap.status < RankedStatus.Ranked:
            # only show leaderboards for ranked,
            # approved, qualified, or loved maps.
            return BeatmapLeaderboardResult(
                code=BeatmapLeaderboardResultCode.NO_LEADERBOARD,
                ranked_status=bmap.status,
            )

        if not request.requesting_from_editor_song_select:
            leaderboard_scores = await self.score_leaderboards.fetch_leaderboard_scores(
                leaderboard_type=request.leaderboard_type,
                map_md5=bmap.md5,
                mode=mode,
                mods=mods,
                player=player,
                scoring_metric=scoring_metric,
            )
            score_rows = leaderboard_scores.score_rows
            personal_best_score_row = leaderboard_scores.personal_best_score_row
        else:
            score_rows = []
            personal_best_score_row = None

        map_avg_rating = await self._fetch_map_rating_average(bmap.md5)
        personal_best_display_name = None
        if personal_best_score_row is not None:
            user_clan_tag = (
                await self._fetch_clan_tag(player.clan_id)
                if player.clan_id is not None
                else None
            )
            personal_best_display_name = (
                f"[{user_clan_tag}] {player.name}"
                if user_clan_tag is not None
                else player.name
            )

        return BeatmapLeaderboardResult(
            code=BeatmapLeaderboardResultCode.FOUND,
            ranked_status=bmap.status,
            beatmap_id=bmap.id,
            beatmap_set_id=bmap.set_id,
            beatmap_name=bmap.full_name,
            beatmap_rating=map_avg_rating,
            score_rows=score_rows,
            personal_best_score_row=personal_best_score_row,
            personal_best_user_id=(
                player.id if personal_best_score_row is not None else None
            ),
            personal_best_display_name=personal_best_display_name,
        )

    def _resolve_score_query_mode_and_mods(
        self,
        *,
        mode_arg: int,
        mods_arg: int,
    ) -> tuple[GameMode, Mods]:
        if mods_arg & Mods.RELAX:
            if mode_arg == 3:  # rx!mania doesn't exist
                mods_arg &= ~Mods.RELAX
            else:
                mode_arg += 4
        elif mods_arg & Mods.AUTOPILOT:
            if mode_arg in (1, 2, 3):  # ap!catch, taiko and mania don't exist
                mods_arg &= ~Mods.AUTOPILOT
            else:
                mode_arg += 8

        return GameMode(mode_arg), Mods(mods_arg)

    def _update_player_status_if_needed(
        self,
        player: Player,
        *,
        mode: GameMode,
        mods: Mods,
    ) -> None:
        # attempt to update their stats if their
        # gm/gm-affecting-mods change at all.
        if mode == player.status.mode:
            return

        player.status.mods = mods
        player.status.mode = mode

        if not player.restricted:
            self.publish_user_stats(player)

    async def _classify_missing_beatmap(
        self,
        request: BeatmapLeaderboardRequest,
    ) -> BeatmapLeaderboardResult:
        # map not found, figure out whether it needs an
        # update or isn't submitted using its filename.
        has_set_id = request.map_set_id > 0
        if has_set_id and request.map_set_id not in self.beatmapset_cache:
            # set not cached, it doesn't exist
            self.unsubmitted_cache.add(request.map_md5)
            return BeatmapLeaderboardResult(
                code=BeatmapLeaderboardResultCode.NOT_SUBMITTED,
            )

        map_filename = unquote_plus(request.map_filename)  # TODO: is unquote needed?

        if has_set_id:
            # we can look it up in the specific set from cache
            map_exists = any(
                map_filename == bmap.filename
                for bmap in self.beatmapset_cache[request.map_set_id].maps
            )
        else:
            # we can't find it on the osu!api by md5,
            # and we don't have the set id, so we must
            # look it up in sql from the filename.
            map_exists = await self._map_exists_by_filename(map_filename)

        if map_exists:
            # map can be updated.
            self.needs_update_cache.add(request.map_md5)
            return BeatmapLeaderboardResult(
                code=BeatmapLeaderboardResultCode.NEEDS_UPDATE,
            )

        # map is unsubmitted.
        # add this map to the unsubmitted cache, so
        # that we don't have to make this request again.
        self.unsubmitted_cache.add(request.map_md5)
        return BeatmapLeaderboardResult(code=BeatmapLeaderboardResultCode.NOT_SUBMITTED)

    async def _fetch_clan_tag(self, clan_id: int) -> str | None:
        clan = await self.clans.fetch_one(id=clan_id)
        return clan.tag if clan is not None else None

    async def _map_exists_by_filename(self, filename: str) -> bool:
        return await self.maps.fetch_one(filename=filename) is not None

    async def _fetch_map_rating_average(self, map_md5: str) -> float:
        map_ratings = await self.ratings.fetch_many(
            map_md5=map_md5,
            page=None,
            page_size=None,
        )
        ratings = [row.rating for row in map_ratings]
        return sum(ratings) / len(ratings) if ratings else 0.0
