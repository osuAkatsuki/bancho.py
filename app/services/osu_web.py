from __future__ import annotations

import hashlib
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import bcrypt

from app._typing import IPAddress
from app.adapters.database import Database
from app.constants import regexes
from app.constants.beatmap_statuses import RankedStatus
from app.constants.score_statuses import SubmissionStatus
from app.objects.beatmap import Beatmap
from app.objects.player import Player
from app.repositories.clans import ClansRepository
from app.repositories.comments import CommentsRepository
from app.repositories.comments import CommentWithUserPrivileges
from app.repositories.comments import TargetType
from app.repositories.favourites import FavouritesRepository
from app.repositories.mail import MailRepository
from app.repositories.maps import MapSetInfo
from app.repositories.maps import MapsRepository
from app.repositories.ratings import RatingsRepository
from app.repositories.scores import ScoresRepository
from app.repositories.stats import StatsRepository
from app.repositories.users import User
from app.repositories.users import UsersRepository
from app.state.services import Geolocation


class IPResolver(Protocol):
    def get_ip(self, headers: Mapping[str, str]) -> IPAddress: ...


class PlayerLookup(Protocol):
    async def from_cache_or_sql(
        self,
        id: int | None = None,
        name: str | None = None,
    ) -> Player | None: ...


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
class OsuLeaderboardSupportService:
    clans: ClansRepository
    maps: MapsRepository
    ratings: RatingsRepository

    async def fetch_clan_tag(self, clan_id: int) -> str | None:
        clan = await self.clans.fetch_one(id=clan_id)
        return clan["tag"] if clan is not None else None

    async def map_exists_by_filename(self, filename: str) -> bool:
        return await self.maps.fetch_one(filename=filename) is not None

    async def fetch_map_rating_average(self, map_md5: str) -> float:
        map_ratings = await self.ratings.fetch_many(
            map_md5=map_md5,
            page=None,
            page_size=None,
        )
        ratings = [row["rating"] for row in map_ratings]
        return sum(ratings) / len(ratings) if ratings else 0.0


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

    async def fetch_relevant_to_replay(
        self,
        *,
        score_id: int,
        map_set_id: int,
        map_id: int,
    ) -> list[CommentWithUserPrivileges]:
        return await self.comments.fetch_all_relevant_to_replay(
            score_id=score_id,
            map_set_id=map_set_id,
            map_id=map_id,
        )

    async def create_comment(
        self,
        *,
        target: str,
        map_set_id: int,
        map_id: int,
        score_id: int,
        player_id: int,
        start_time: int,
        comment: str,
        colour: str | None,
    ) -> None:
        if target == "song":
            target_id = map_set_id
        elif target == "map":
            target_id = map_id
        else:
            target_id = score_id

        await self.comments.create(
            target_id=target_id,
            target_type=TargetType(target),
            userid=player_id,
            time=start_time,
            comment=comment,
            colour=colour,
        )


@dataclass(frozen=True)
class MailReadService:
    mail: MailRepository
    players: PlayerLookup

    async def mark_conversation_with_player_as_read(
        self,
        *,
        player_id: int,
        target_name: str,
    ) -> None:
        target = await self.players.from_cache_or_sql(name=target_name)
        if target is not None:
            await self.mail.mark_conversation_as_read(
                to_id=player_id,
                from_id=target.id,
            )


class RegistrationErrors(dict[str, list[str]]):
    pass


@dataclass(frozen=True)
class RegisteredAccount:
    player: User
    password_md5: bytes
    password_bcrypt: bytes


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
    disallowed_names: Sequence[str]
    disallowed_passwords: Sequence[str]

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
