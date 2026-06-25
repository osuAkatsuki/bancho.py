from __future__ import annotations

import hashlib
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import MutableSet
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from typing import TypedDict
from urllib.parse import unquote
from urllib.parse import unquote_plus

import bcrypt

import app.utils
from app._typing import IPAddress
from app.adapters.database import Database
from app.constants import regexes
from app.constants.beatmap_statuses import RankedStatus
from app.constants.clientflags import LastFMFlags
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import Privileges
from app.constants.score_statuses import SubmissionStatus
from app.constants.scoring_metrics import ScoringMetric
from app.logging import Ansi
from app.logging import log
from app.objects.beatmap import Beatmap
from app.objects.player import Player
from app.objects.score import Score
from app.repositories.clans import ClansRepository
from app.repositories.comments import CommentsRepository
from app.repositories.comments import CommentWithUserPrivileges
from app.repositories.comments import TargetType
from app.repositories.favourites import FavouritesRepository
from app.repositories.mail import MailRepository
from app.repositories.maps import MapSetInfo
from app.repositories.maps import MapsRepository
from app.repositories.ratings import RatingsRepository
from app.repositories.scores import BeatmapLeaderboardScoreRow
from app.repositories.scores import ScoresRepository
from app.repositories.stats import StatsRepository
from app.repositories.users import User
from app.repositories.users import UsersRepository
from app.services.score_leaderboards import PersonalBestLeaderboardScoreListing
from app.services.score_leaderboards import ScoreLeaderboardsService
from app.state.services import Geolocation

DirectSearchParams = Mapping[str, str | int | float | bool | None]


class IPResolver(Protocol):
    def get_ip(self, headers: Mapping[str, str]) -> IPAddress: ...


class PlayerLookup(Protocol):
    async def from_cache_or_sql(
        self,
        id: int | None = None,
        name: str | None = None,
    ) -> Player | None: ...


class BeatmapSetCacheEntry(Protocol):
    @property
    def maps(self) -> Sequence[Beatmap]: ...


class DirectSearchHTTPResponse(Protocol):
    status_code: int

    def json(self) -> list[DirectSearchSetPayload]: ...


class DirectSearchGetter(Protocol):
    def __call__(
        self,
        url: str,
        *,
        params: DirectSearchParams,
    ) -> Awaitable[DirectSearchHTTPResponse]: ...


class BeatmapFetcher(Protocol):
    def __call__(self, md5: str, set_id: int = -1) -> Awaitable[Beatmap | None]: ...


class ScoreFetcher(Protocol):
    def __call__(self, score_id: int) -> Awaitable[Score | None]: ...


class ReplayViewScheduler(Protocol):
    def __call__(self, score: Score) -> None: ...


class DirectSearchBeatmapPayload(TypedDict):
    DifficultyRating: float
    DiffName: str
    CS: float
    OD: float
    AR: float
    HP: float
    Mode: int


class DirectSearchSetPayload(TypedDict):
    Artist: str
    Title: str
    Creator: str
    RankedStatus: int
    LastUpdate: str
    SetID: int
    HasVideo: bool | int
    ChildrenBeatmaps: list[DirectSearchBeatmapPayload] | None


class ScreenshotUploadResultCode(StrEnum):
    UPLOADED = "uploaded"
    FILE_TOO_LARGE = "file_too_large"
    INVALID_FILE_TYPE = "invalid_file_type"


@dataclass(frozen=True)
class ScreenshotUploadResult:
    code: ScreenshotUploadResultCode
    filename: str | None = None


@dataclass(frozen=True)
class ScreenshotService:
    screenshots_path: Path
    token_urlsafe: Callable[[int], str]
    log_strange_occurrence: Callable[[object], Awaitable[None]]

    async def upload_screenshot(
        self,
        *,
        player: Player,
        endpoint_version: int,
        screenshot_data: bytes,
    ) -> ScreenshotUploadResult:
        with memoryview(screenshot_data) as screenshot_view:
            # png sizes: 1080p: ~300-800kB | 4k: ~1-2mB
            if len(screenshot_view) > (4 * 1024 * 1024):
                return ScreenshotUploadResult(
                    code=ScreenshotUploadResultCode.FILE_TOO_LARGE,
                )

            if endpoint_version != 1:
                await self.log_strange_occurrence(
                    "Incorrect endpoint version "
                    f"(/web/osu-screenshot.php v{endpoint_version})",
                )

            if app.utils.has_jpeg_headers_and_trailers(screenshot_view):
                extension = "jpeg"
            elif app.utils.has_png_headers_and_trailers(screenshot_view):
                extension = "png"
            else:
                return ScreenshotUploadResult(
                    code=ScreenshotUploadResultCode.INVALID_FILE_TYPE,
                )

        while True:
            filename = f"{self.token_urlsafe(6)}.{extension}"
            screenshot_path = self.screenshots_path / filename
            if not screenshot_path.exists():
                break

        with screenshot_path.open("wb") as screenshot_file:
            screenshot_file.write(screenshot_data)

        log(f"{player} uploaded {filename}.")
        return ScreenshotUploadResult(
            code=ScreenshotUploadResultCode.UPLOADED,
            filename=filename,
        )


class LastFmResult(StrEnum):
    EMPTY = "empty"
    STOP_SENDING = "stop_sending"


@dataclass(frozen=True)
class LastFmService:
    restriction_admin: Player
    restriction_roll: Callable[[int], int]
    send_notification: Callable[[Player, str], None]

    async def handle_client_integrity_flags(
        self,
        *,
        player: Player,
        beatmap_id_or_hidden_flag: str,
    ) -> LastFmResult:
        if not beatmap_id_or_hidden_flag or beatmap_id_or_hidden_flag[0] != "a":
            # not anticheat related, tell the
            # client not to send any more for now.
            return LastFmResult.STOP_SENDING

        flags = LastFMFlags(int(beatmap_id_or_hidden_flag[1:]))

        if flags & (LastFMFlags.HQ_ASSEMBLY | LastFMFlags.HQ_FILE):
            # Player is currently running hq!osu; could possibly
            # be a separate client, buuuut prooobably not lol.
            await self._restrict_and_refresh_client(
                player,
                reason=f"hq!osu running ({flags})",
            )
            return LastFmResult.STOP_SENDING

        if flags & LastFMFlags.REGISTRY_EDITS:
            # Player has registry edits left from
            # hq!osu's multiaccounting tool. This
            # does not necessarily mean they are
            # using it now, but they have in the past.
            if self.restriction_roll(32) == 0:
                # Random chance (1/32) for a ban.
                await self._restrict_and_refresh_client(
                    player,
                    reason="hq!osu relife 1/32",
                )
                return LastFmResult.STOP_SENDING

            self.send_notification(
                player,
                "\n".join(
                    [
                        "Hey!",
                        "It appears you have hq!osu's multiaccounting tool (relife) enabled.",
                        "This tool leaves a change in your registry that the osu! client can detect.",
                        "Please re-install relife and disable the program to avoid any restrictions.",
                    ],
                ),
            )
            player.logout()
            return LastFmResult.STOP_SENDING

        """ These checks only worked for ~5 hours from release. rumoi's quick!
        if flags & (
            LastFMFlags.SDL2_LIBRARY
            | LastFMFlags.OPENSSL_LIBRARY
            | LastFMFlags.AQN_MENU_SAMPLE
        ):
            # AQN has been detected in the client, either
            # through the 'libeay32.dll' library being found
            # onboard, or from the menu sound being played in
            # the AQN menu while being in an inappropriate menu
            # for the context of the sound effect.
            pass
        """

        return LastFmResult.EMPTY

    async def _restrict_and_refresh_client(
        self,
        player: Player,
        *,
        reason: str,
    ) -> None:
        await player.restrict(admin=self.restriction_admin, reason=reason)

        # refresh their client state
        if player.is_online:
            player.logout()


@dataclass(frozen=True)
class DirectSearchBeatmap:
    difficulty_rating: float
    name: str
    cs: float
    od: float
    ar: float
    hp: float
    mode: int


@dataclass(frozen=True)
class DirectSearchSet:
    artist: str
    title: str
    creator: str
    ranked_status: int
    last_update: str
    set_id: int
    has_video: int
    beatmaps: list[DirectSearchBeatmap]


class DirectSearchResultCode(StrEnum):
    FOUND = "found"
    MIRROR_ERROR = "mirror_error"


@dataclass(frozen=True)
class DirectSearchResult:
    code: DirectSearchResultCode
    result_count: int = 0
    beatmap_sets: list[DirectSearchSet] | None = None


@dataclass(frozen=True)
class DirectSearchService:
    mirror_search_endpoint: str
    fetch_mirror_search: DirectSearchGetter

    async def search(
        self,
        *,
        ranked_status: int,
        query: str,
        mode: int,
        page_num: int,
    ) -> DirectSearchResult:
        params: dict[str, str | int | float | bool | None] = {
            "amount": 100,
            "offset": page_num * 100,
        }

        # eventually we could try supporting these,
        # but it mostly depends on the mirror.
        if query not in ("Newest", "Top+Rated", "Most+Played"):
            params["query"] = query

        if mode != -1:  # -1 for all
            params["mode"] = mode

        if ranked_status != 4:  # 4 for all
            # convert to osu!api status
            params["status"] = RankedStatus.from_osudirect(ranked_status).osu_api

        response = await self.fetch_mirror_search(
            self.mirror_search_endpoint,
            params=params,
        )
        if response.status_code != 200:
            return DirectSearchResult(code=DirectSearchResultCode.MIRROR_ERROR)

        result = response.json()
        beatmap_sets: list[DirectSearchSet] = []

        for bmapset in result:
            if bmapset["ChildrenBeatmaps"] is None:
                continue

            diff_sorted_maps = sorted(
                bmapset["ChildrenBeatmaps"],
                key=lambda beatmap: beatmap["DifficultyRating"],
            )

            beatmap_sets.append(
                DirectSearchSet(
                    artist=self._replace_osudirect_delimiter(bmapset["Artist"]),
                    title=self._replace_osudirect_delimiter(bmapset["Title"]),
                    creator=bmapset["Creator"],
                    ranked_status=bmapset["RankedStatus"],
                    last_update=bmapset["LastUpdate"],
                    set_id=bmapset["SetID"],
                    # some mirrors use a true/false instead of 0 or 1
                    has_video=int(bmapset["HasVideo"]),
                    beatmaps=[
                        DirectSearchBeatmap(
                            difficulty_rating=beatmap["DifficultyRating"],
                            name=self._replace_osudirect_delimiter(
                                beatmap["DiffName"],
                            ),
                            cs=beatmap["CS"],
                            od=beatmap["OD"],
                            ar=beatmap["AR"],
                            hp=beatmap["HP"],
                            mode=beatmap["Mode"],
                        )
                        for beatmap in diff_sorted_maps
                    ],
                ),
            )

        result_count = len(result)
        return DirectSearchResult(
            code=DirectSearchResultCode.FOUND,
            # send over 100 if we receive 100 matches, so the client knows
            # there are more to get.
            result_count=101 if result_count == 100 else result_count,
            beatmap_sets=beatmap_sets,
        )

    def _replace_osudirect_delimiter(self, value: str) -> str:
        # XXX: this is a bug that exists on official servers (lmao)
        # | is used to delimit the set data, so the difficulty name
        # cannot contain this or it will be ignored. we fix it here
        # by using a different character.
        return value.replace("|", "I")


class ReplayResultCode(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class ReplayResult:
    code: ReplayResultCode
    path: Path | None = None


@dataclass(frozen=True)
class ReplayService:
    replays_path: Path
    fetch_score: ScoreFetcher
    schedule_replay_view_increment: ReplayViewScheduler

    async def fetch_replay_file(
        self,
        *,
        viewer_id: int,
        score_id: int,
    ) -> ReplayResult:
        score = await self.fetch_score(score_id)
        if score is None:
            return ReplayResult(code=ReplayResultCode.NOT_FOUND)

        replay_path = self.replays_path / f"{score_id}.osr"
        if not replay_path.exists():
            return ReplayResult(code=ReplayResultCode.NOT_FOUND)

        player = getattr(score, "player", None)
        if player is not None and viewer_id != player.id:
            self.schedule_replay_view_increment(score)

        return ReplayResult(code=ReplayResultCode.FOUND, path=replay_path)


@dataclass(frozen=True)
class OsuLeaderboardRequest:
    requesting_from_editor_song_select: bool
    leaderboard_type: int
    map_md5: str
    map_filename: str
    mode_arg: int
    map_set_id: int
    mods_arg: int
    aqn_files_found: bool


class OsuLeaderboardResultCode(StrEnum):
    FOUND = "found"
    NEEDS_UPDATE = "needs_update"
    NOT_SUBMITTED = "not_submitted"
    NO_LEADERBOARD = "no_leaderboard"


@dataclass(frozen=True)
class OsuLeaderboardResult:
    code: OsuLeaderboardResultCode
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
class OsuLeaderboardService:
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
        request: OsuLeaderboardRequest,
    ) -> OsuLeaderboardResult:
        if request.aqn_files_found:
            await self.log_strange_occurrence(self.get_appropriate_stacktrace())

        # check if this md5 has already been  cached as
        # unsubmitted/needs update to reduce osu!api spam
        if request.map_md5 in self.unsubmitted_cache:
            return OsuLeaderboardResult(code=OsuLeaderboardResultCode.NOT_SUBMITTED)
        if request.map_md5 in self.needs_update_cache:
            return OsuLeaderboardResult(code=OsuLeaderboardResultCode.NEEDS_UPDATE)

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
            return OsuLeaderboardResult(
                code=OsuLeaderboardResultCode.NO_LEADERBOARD,
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

        return OsuLeaderboardResult(
            code=OsuLeaderboardResultCode.FOUND,
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
        request: OsuLeaderboardRequest,
    ) -> OsuLeaderboardResult:
        # map not found, figure out whether it needs an
        # update or isn't submitted using its filename.
        has_set_id = request.map_set_id > 0
        if has_set_id and request.map_set_id not in self.beatmapset_cache:
            # set not cached, it doesn't exist
            self.unsubmitted_cache.add(request.map_md5)
            return OsuLeaderboardResult(code=OsuLeaderboardResultCode.NOT_SUBMITTED)

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
            return OsuLeaderboardResult(code=OsuLeaderboardResultCode.NEEDS_UPDATE)

        # map is unsubmitted.
        # add this map to the unsubmitted cache, so
        # that we don't have to make this request again.
        self.unsubmitted_cache.add(request.map_md5)
        return OsuLeaderboardResult(code=OsuLeaderboardResultCode.NOT_SUBMITTED)

    async def _fetch_clan_tag(self, clan_id: int) -> str | None:
        clan = await self.clans.fetch_one(id=clan_id)
        return clan["tag"] if clan is not None else None

    async def _map_exists_by_filename(self, filename: str) -> bool:
        return await self.maps.fetch_one(filename=filename) is not None

    async def _fetch_map_rating_average(self, map_md5: str) -> float:
        map_ratings = await self.ratings.fetch_many(
            map_md5=map_md5,
            page=None,
            page_size=None,
        )
        ratings = [row["rating"] for row in map_ratings]
        return sum(ratings) / len(ratings) if ratings else 0.0


@dataclass(frozen=True)
class BeatmapInfo:
    index: int
    id: int
    set_id: int
    md5: str
    status: int
    grades: list[str]


@dataclass(frozen=True)
class BeatmapInfoService:
    maps: MapsRepository
    scores: ScoresRepository

    async def fetch_beatmap_info(
        self,
        *,
        filenames: Sequence[str],
        player_id: int,
        vanilla_mode: int,
    ) -> list[BeatmapInfo]:
        beatmap_info: list[BeatmapInfo] = []

        for idx, map_filename in enumerate(filenames):
            beatmap = await self.maps.fetch_one(filename=map_filename)
            if beatmap is None:
                continue

            # osu! only allows us to send back one grade per gamemode, so we
            # send back vanilla grades. In theory this could be user-customizable.
            grades = ["N", "N", "N", "N"]
            for score in await self.scores.fetch_many(
                map_md5=beatmap["md5"],
                user_id=player_id,
                mode=vanilla_mode,
                status=SubmissionStatus.BEST,
            ):
                grades[score["mode"]] = score["grade"]

            beatmap_info.append(
                BeatmapInfo(
                    index=idx,
                    id=beatmap["id"],
                    set_id=beatmap["set_id"],
                    md5=beatmap["md5"],
                    status=beatmap["status"],
                    grades=grades,
                ),
            )

        return beatmap_info


class AddFavouriteResult(StrEnum):
    ADDED = "added"
    ALREADY_FAVOURITED = "already_favourited"


@dataclass(frozen=True)
class FavouritesService:
    favourites: FavouritesRepository

    async def fetch_favourite_set_ids(self, player_id: int) -> list[int]:
        favourites = await self.favourites.fetch_all(userid=player_id)
        return [favourite["setid"] for favourite in favourites]

    async def add_favourite(
        self,
        *,
        player_id: int,
        map_set_id: int,
    ) -> AddFavouriteResult:
        if await self.favourites.fetch_one(player_id, map_set_id):
            return AddFavouriteResult.ALREADY_FAVOURITED

        await self.favourites.create(userid=player_id, setid=map_set_id)
        return AddFavouriteResult.ADDED


class BeatmapRatingResultCode(StrEnum):
    NO_EXIST = "no_exist"
    NOT_RANKED = "not_ranked"
    CAN_RATE = "can_rate"
    ALREADY_VOTED = "already_voted"


@dataclass(frozen=True)
class BeatmapRatingResult:
    code: BeatmapRatingResultCode
    average_rating: float | None = None


@dataclass(frozen=True)
class BeatmapRatingService:
    ratings: RatingsRepository
    beatmap_cache: Mapping[str | int, Beatmap]

    async def rate_or_check(
        self,
        *,
        player_id: int,
        map_md5: str,
        rating: int | None,
    ) -> BeatmapRatingResult:
        if rating is None:
            if map_md5 not in self.beatmap_cache:
                return BeatmapRatingResult(code=BeatmapRatingResultCode.NO_EXIST)

            cached = self.beatmap_cache[map_md5]
            if cached.status < RankedStatus.Ranked:
                return BeatmapRatingResult(code=BeatmapRatingResultCode.NOT_RANKED)

            existing_rating = await self.ratings.fetch_one(
                map_md5=map_md5,
                userid=player_id,
            )
            if existing_rating is None:
                return BeatmapRatingResult(code=BeatmapRatingResultCode.CAN_RATE)
        else:
            await self.ratings.create(
                userid=player_id,
                map_md5=map_md5,
                rating=rating,
            )

        map_ratings = await self.ratings.fetch_many(map_md5=map_md5)
        ratings = [row["rating"] for row in map_ratings]
        return BeatmapRatingResult(
            code=BeatmapRatingResultCode.ALREADY_VOTED,
            average_rating=sum(ratings) / len(ratings),
        )


@dataclass(frozen=True)
class BeatmapSetService:
    maps: MapsRepository

    async def fetch_set_info(
        self,
        *,
        set_id: int | None = None,
        map_id: int | None = None,
        md5: str | None = None,
    ) -> MapSetInfo | None:
        return await self.maps.fetch_set_info(
            set_id=set_id,
            map_id=map_id,
            md5=md5,
        )


@dataclass(frozen=True)
class CommentsService:
    comments: CommentsRepository

    async def fetch_relevant_to_replay_for_player(
        self,
        *,
        player: Player,
        score_id: int,
        map_set_id: int,
        map_id: int,
    ) -> list[CommentWithUserPrivileges]:
        comments = await self.comments.fetch_all_relevant_to_replay(
            score_id=score_id,
            map_set_id=map_set_id,
            map_id=map_id,
        )
        player.update_latest_activity_soon()
        return comments

    async def create_comment_for_player(
        self,
        *,
        player: Player,
        target: str,
        map_set_id: int,
        map_id: int,
        score_id: int,
        start_time: int,
        comment: str,
        colour: str | None,
    ) -> None:
        if colour and not player.priv & Privileges.DONATOR:
            # only supporters can use colours.
            colour = None

            log(
                f"User {player} attempted to use a coloured comment without "
                "supporter status. Submitting comment without a colour.",
            )

        if target == "song":
            target_id = map_set_id
        elif target == "map":
            target_id = map_id
        else:
            target_id = score_id

        await self.comments.create(
            target_id=target_id,
            target_type=TargetType(target),
            userid=player.id,
            time=start_time,
            comment=comment,
            colour=colour,
        )

        player.update_latest_activity_soon()


@dataclass(frozen=True)
class MailReadService:
    mail: MailRepository
    players: PlayerLookup

    async def mark_channel_as_read(
        self,
        *,
        player: Player,
        channel: str,
    ) -> None:
        target_name = unquote(channel)  # TODO: unquote needed?
        if not target_name:
            log(
                f"User {player} attempted to mark a channel as read without a target.",
                Ansi.LYELLOW,
            )
            return

        target = await self.players.from_cache_or_sql(name=target_name)
        if target is not None:
            await self.mail.mark_conversation_as_read(
                to_id=player.id,
                from_id=target.id,
            )


class RegistrationErrors(dict[str, list[str]]):
    pass


@dataclass(frozen=True)
class RegisteredAccount:
    player: User
    password_md5: bytes
    password_bcrypt: bytes


class AccountRegistrationResultCode(StrEnum):
    OK = "ok"
    MISSING_REQUIRED_PARAMS = "missing_required_params"
    INGAME_REGISTRATION_DISABLED = "ingame_registration_disabled"
    VALIDATION_FAILED = "validation_failed"


@dataclass(frozen=True)
class AccountRegistrationResult:
    code: AccountRegistrationResultCode
    errors: RegistrationErrors | None = None


@dataclass(frozen=True)
class AccountRegistrationService:
    users: UsersRepository
    stats: StatsRepository
    database: Database
    password_cache: dict[bytes, bytes]
    ip_resolver: IPResolver
    fetch_geoloc: Callable[
        [IPAddress, Mapping[str, str] | None],
        Awaitable[Geolocation | None],
    ]
    increment_metric: Callable[[str], None]
    ingame_registration_disallowed: bool
    disallowed_names: Sequence[str]
    disallowed_passwords: Sequence[str]

    async def check_or_register(
        self,
        *,
        username: str,
        email: str,
        password: str,
        should_create_account: bool,
        request_headers: Mapping[str, str],
    ) -> AccountRegistrationResult:
        if not all((username, email, password)):
            return AccountRegistrationResult(
                code=AccountRegistrationResultCode.MISSING_REQUIRED_PARAMS,
            )

        # Disable in-game registration if enabled
        if self.ingame_registration_disallowed:
            return AccountRegistrationResult(
                code=AccountRegistrationResultCode.INGAME_REGISTRATION_DISABLED,
            )

        errors = await self.validate_registration(
            username=username,
            email=email,
            password=password,
        )
        if errors:
            return AccountRegistrationResult(
                code=AccountRegistrationResultCode.VALIDATION_FAILED,
                errors=errors,
            )

        if should_create_account:
            # the client isn't just checking values,
            # they want to register the account now.
            registered_account = await self.create_account(
                username=username,
                email=email,
                password=password,
                request_headers=request_headers,
            )
            player = registered_account.player

            self.increment_metric("bancho.registrations")
            log(f"<{username} ({player['id']})> has registered!", Ansi.LGREEN)

        return AccountRegistrationResult(code=AccountRegistrationResultCode.OK)

    async def validate_registration(
        self,
        *,
        username: str,
        email: str,
        password: str,
    ) -> RegistrationErrors:
        errors: RegistrationErrors = RegistrationErrors()

        # Usernames must:
        # - be within 2-15 characters in length
        # - not contain both ' ' and '_', one is fine
        # - not be in the config's `disallowed_names` list
        # - not already be taken by another player
        if not regexes.USERNAME.match(username):
            errors.setdefault("username", []).append(
                "Must be 2-15 characters in length.",
            )

        if "_" in username and " " in username:
            errors.setdefault("username", []).append(
                'May contain "_" and " ", but not both.',
            )

        if username in self.disallowed_names:
            errors.setdefault("username", []).append(
                "Disallowed username; pick another.",
            )

        if "username" not in errors:
            if await self.users.fetch_one(name=username):
                errors.setdefault("username", []).append(
                    "Username already taken by another player.",
                )

        # Emails must:
        # - match the regex `^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{1,24}$`
        # - not already be taken by another player
        if not regexes.EMAIL.match(email):
            errors.setdefault("user_email", []).append("Invalid email syntax.")
        else:
            if await self.users.fetch_one(email=email):
                errors.setdefault("user_email", []).append(
                    "Email already taken by another player.",
                )

        # Passwords must:
        # - be within 8-32 characters in length
        # - have more than 3 unique characters
        # - not be in the config's `disallowed_passwords` list
        if not 8 <= len(password) <= 32:
            errors.setdefault("password", []).append(
                "Must be 8-32 characters in length.",
            )

        if len(set(password)) <= 3:
            errors.setdefault("password", []).append(
                "Must have more than 3 unique characters.",
            )

        if password.lower() in self.disallowed_passwords:
            errors.setdefault("password", []).append(
                "That password was deemed too simple.",
            )

        return errors

    async def create_account(
        self,
        *,
        username: str,
        email: str,
        password: str,
        request_headers: Mapping[str, str],
    ) -> RegisteredAccount:
        password_md5 = hashlib.md5(password.encode()).hexdigest().encode()
        password_bcrypt = bcrypt.hashpw(password_md5, bcrypt.gensalt())
        self.password_cache[password_bcrypt] = password_md5

        ip = self.ip_resolver.get_ip(request_headers)
        geoloc = await self.fetch_geoloc(ip, request_headers)
        country = geoloc["country"]["acronym"] if geoloc is not None else "XX"

        async with self.database.transaction():
            player = await self.users.create(
                name=username,
                email=email,
                pw_bcrypt=password_bcrypt,
                country=country,
            )
            await self.stats.create_all_modes(player_id=player["id"])

        return RegisteredAccount(
            player=player,
            password_md5=password_md5,
            password_bcrypt=password_bcrypt,
        )
