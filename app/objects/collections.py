# TODO: there is still a lot of inconsistency
# in a lot of these classes; needs refactor.
from __future__ import annotations

from typing import Iterable
from typing import Iterator
from typing import Optional
from typing import overload
from typing import Sequence
from typing import Union

import databases.core

import app.settings
import app.state
import app.utils
from app.constants.privileges import ClanPrivileges
from app.constants.privileges import Privileges
from app.logging import Ansi
from app.logging import log
from app.objects.achievement import Achievement
from app.objects.channel import Channel
from app.objects.clan import Clan
from app.objects.match import MapPool
from app.objects.match import Match
from app.objects.player import Player
from app.repositories import achievements as achievements_repo
from app.repositories import channels as channels_repo
from app.repositories import clans as clans_repo
from app.repositories import players as players_repo
from app.utils import make_safe_name

__all__ = (
    "Channels",
    "Matches",
    "Players",
    "MapPools",
    "Clans",
    "initialize_ram_caches",
)

# TODO: decorator for these collections which automatically
# adds debugging to their append/remove/insert/extend methods.


class Channels(list[Channel]):
    """The currently active chat channels on the server."""

    def __iter__(self) -> Iterator[Channel]:
        return super().__iter__()

    def __contains__(self, o: Union[Channel, str]) -> bool:
        """Check whether internal list contains `o`."""
        # Allow string to be passed to compare vs. name.
        if isinstance(o, str):
            return o in (chan.name for chan in self)
        else:
            return super().__contains__(o)

    @overload
    def __getitem__(self, index: int) -> Channel:
        ...

    @overload
    def __getitem__(self, index: str) -> Channel:
        ...

    @overload
    def __getitem__(self, index: slice) -> list[Channel]:
        ...

    def __getitem__(
        self,
        index: Union[int, slice, str],
    ) -> Union[Channel, list[Channel]]:
        # XXX: can be either a string (to get by name),
        # or a slice, for indexing the internal array.
        if isinstance(index, str):
            return self.get_by_name(index)  # type: ignore
        else:
            return super().__getitem__(index)

    def __repr__(self) -> str:
        # XXX: we use the "real" name, aka
        # #multi_1 instead of #multiplayer
        # #spect_1 instead of #spectator.
        return f'[{", ".join(c._name for c in self)}]'

    def get_by_name(self, name: str) -> Optional[Channel]:
        """Get a channel from the list by `name`."""
        for channel in self:
            if channel._name == name:
                return channel

        return None

    def append(self, channel: Channel) -> None:
        """Append `channel` to the list."""
        super().append(channel)

        if app.settings.DEBUG:
            log(f"{channel} added to channels list.")

    def extend(self, channels: Iterable[Channel]) -> None:
        """Extend the list with `channels`."""
        super().extend(channels)

        if app.settings.DEBUG:
            log(f"{channels} added to channels list.")

    def remove(self, channel: Channel) -> None:
        """Remove `channel` from the list."""
        super().remove(channel)

        if app.settings.DEBUG:
            log(f"{channel} removed from channels list.")

    async def prepare(self, db_conn: databases.core.Connection) -> None:
        """Fetch data from sql & return; preparing to run the server."""
        log("Fetching channels from sql.", Ansi.LCYAN)
        for row in await channels_repo.fetch_many():
            self.append(
                Channel(
                    name=row["name"],
                    topic=row["topic"],
                    read_priv=Privileges(row["read_priv"]),
                    write_priv=Privileges(row["write_priv"]),
                    auto_join=row["auto_join"] == 1,
                ),
            )


class Matches(list[Optional[Match]]):
    """The currently active multiplayer matches on the server."""

    def __init__(self) -> None:
        super().__init__([None] * app.settings.MAX_MATCHES)

    def __iter__(self) -> Iterator[Optional[Match]]:
        return super().__iter__()

    def __repr__(self) -> str:
        return f'[{", ".join(match.name for match in self if match)}]'

    def get_free(self) -> Optional[int]:
        """Return the first free match id from `self`."""
        for idx, match in enumerate(self):
            if match is None:
                return idx

        return None

    def append(self, match: Match) -> bool:
        """Append `match` to the list."""
        free = self.get_free()
        if free is not None:
            # set the id of the match to the lowest available free.
            match.id = free
            self[free] = match

            if app.settings.DEBUG:
                log(f"{match} added to matches list.")

            return True
        else:
            log(f"Match list is full! Could not add {match}.")
            return False

    # TODO: extend

    def remove(self, match: Match) -> None:
        """Remove `match` from the list."""
        for i, _m in enumerate(self):
            if match is _m:
                self[i] = None
                break

        if app.settings.DEBUG:
            log(f"{match} removed from matches list.")


class Players(list[Player]):
    """The currently active players on the server."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __iter__(self) -> Iterator[Player]:
        return super().__iter__()

    def __contains__(self, player: Union[Player, str]) -> bool:
        # allow us to either pass in the player
        # obj, or the player name as a string.
        if isinstance(player, str):
            return player in (player.name for player in self)
        else:
            return super().__contains__(player)

    def __repr__(self) -> str:
        return f'[{", ".join(map(repr, self))}]'

    @property
    def ids(self) -> set[int]:
        """Return a set of the current ids in the list."""
        return {p.id for p in self}

    @property
    def staff(self) -> set[Player]:
        """Return a set of the current staff online."""
        return {p for p in self if p.priv & Privileges.STAFF}

    @property
    def restricted(self) -> set[Player]:
        """Return a set of the current restricted players."""
        return {p for p in self if not p.priv & Privileges.UNRESTRICTED}

    @property
    def unrestricted(self) -> set[Player]:
        """Return a set of the current unrestricted players."""
        return {p for p in self if p.priv & Privileges.UNRESTRICTED}

    def enqueue(self, data: bytes, immune: Sequence[Player] = []) -> None:
        """Enqueue `data` to all players, except for those in `immune`."""
        for player in self:
            if player not in immune:
                player.enqueue(data)

    def get(
        self,
        token: Optional[str] = None,
        id: Optional[int] = None,
        name: Optional[str] = None,
    ) -> Optional[Player]:
        """Get a player by token, id, or name from cache."""
        for player in self:
            if token is not None:
                if player.token == token:
                    return player
            elif id is not None:
                if player.id == id:
                    return player
            elif name is not None:
                if player.safe_name == make_safe_name(name):
                    return player

        return None

    async def get_sql(
        self,
        id: Optional[int] = None,
        name: Optional[str] = None,
    ) -> Optional[Player]:
        """Get a player by token, id, or name from sql."""
        # try to get from sql.
        player = await players_repo.fetch_one(
            id=id,
            name=name,
            fetch_all_fields=True,
        )
        if player is None:
            return None

        # encode pw_bcrypt from str -> bytes.
        player["pw_bcrypt"] = player["pw_bcrypt"].encode()

        if player["clan_id"] != 0:
            player["clan"] = app.state.sessions.clans.get(id=player["clan_id"])
            player["clan_priv"] = ClanPrivileges(player["clan_priv"])
        else:
            player["clan"] = player["clan_priv"] = None

        # country from acronym to {acronym, numeric}
        player["geoloc"] = {
            "latitude": 0.0,  # TODO
            "longitude": 0.0,
            "country": {
                "acronym": player["country"],
                "numeric": app.state.services.country_codes[player["country"]],
            },
        }

        return Player(**player, token="")

    async def from_cache_or_sql(
        self,
        id: Optional[int] = None,
        name: Optional[str] = None,
    ) -> Optional[Player]:
        """Try to get player from cache, or sql as fallback."""
        player = self.get(id=id, name=name)
        if player is not None:
            return player
        player = await self.get_sql(id=id, name=name)
        if player is not None:
            return player

        return None

    async def from_login(
        self,
        name: str,
        pw_md5: str,
        sql: bool = False,
    ) -> Optional[Player]:
        """Return a player with a given name & pw_md5, from cache or sql."""
        player = self.get(name=name)
        if not player:
            if not sql:
                return None

            player = await self.get_sql(name=name)
            if not player:
                return None

        assert player.pw_bcrypt is not None

        if app.state.cache.bcrypt[player.pw_bcrypt] == pw_md5.encode():
            return player

        return None

    def append(self, player: Player) -> None:
        """Append `p` to the list."""
        if player in self:
            if app.settings.DEBUG:
                log(f"{player} double-added to global player list?")
            return

        super().append(player)

    def remove(self, player: Player) -> None:
        """Remove `p` from the list."""
        if player not in self:
            if app.settings.DEBUG:
                log(f"{player} removed from player list when not online?")
            return

        super().remove(player)


class MapPools(list[MapPool]):
    """The currently active mappools on the server."""

    def __iter__(self) -> Iterator[MapPool]:
        return super().__iter__()

    @overload
    def __getitem__(self, index: int) -> MapPool:
        ...

    @overload
    def __getitem__(self, index: str) -> MapPool:
        ...

    @overload
    def __getitem__(self, index: slice) -> list[MapPool]:
        ...

    def __getitem__(
        self,
        index: Union[int, slice, str],
    ) -> Union[MapPool, list[MapPool]]:
        """Allow slicing by either a string (for name), or slice."""
        if isinstance(index, str):
            return self.get_by_name(index)  # type: ignore
        else:
            return super().__getitem__(index)

    def get(
        self,
        id: Optional[int] = None,
        name: Optional[str] = None,
    ) -> Optional[MapPool]:
        """Get a mappool by id, or name from cache."""
        for player in self:
            if id is not None:
                if player.id == id:
                    return player
            elif name is not None:
                if player.name == name:
                    return player

        return None

    def __contains__(self, o: Union[MapPool, str]) -> bool:
        """Check whether internal list contains `o`."""
        # Allow string to be passed to compare vs. name.
        if isinstance(o, str):
            return o in (pool.name for pool in self)
        else:
            return o in self

    def get_by_name(self, name: str) -> Optional[MapPool]:
        """Get a pool from the list by `name`."""
        for player in self:
            if player.name == name:
                return player

        return None

    def append(self, mappool: MapPool) -> None:
        """Append `mappool` to the list."""
        super().append(mappool)

        if app.settings.DEBUG:
            log(f"{mappool} added to mappools list.")

    def extend(self, mappools: Iterable[MapPool]) -> None:
        """Extend the list with `mappools`."""
        super().extend(mappools)

        if app.settings.DEBUG:
            log(f"{mappools} added to mappools list.")

    def remove(self, mappool: MapPool) -> None:
        """Remove `mappool` from the list."""
        super().remove(mappool)

        if app.settings.DEBUG:
            log(f"{mappool} removed from mappools list.")

    async def prepare(self, db_conn: databases.core.Connection) -> None:
        """Fetch data from sql & return; preparing to run the server."""
        log("Fetching mappools from sql.", Ansi.LCYAN)
        for row in await db_conn.fetch_all("SELECT * FROM tourney_pools"):
            created_by = await app.state.sessions.players.from_cache_or_sql(
                id=row["created_by"],
            )

            assert created_by is not None

            pool = MapPool(
                id=row["id"],
                name=row["name"],
                created_at=row["created_at"],
                created_by=created_by,
            )
            await pool.maps_from_sql(db_conn)
            self.append(pool)


class Clans(list[Clan]):
    """The currently active clans on the server."""

    def __iter__(self) -> Iterator[Clan]:
        return super().__iter__()

    @overload
    def __getitem__(self, index: int) -> Clan:
        ...

    @overload
    def __getitem__(self, index: str) -> Clan:
        ...

    @overload
    def __getitem__(self, index: slice) -> list[Clan]:
        ...

    def __getitem__(self, index: Union[int, str, slice]):
        """Allow slicing by either a string (for name), or slice."""
        if isinstance(index, str):
            return self.get(name=index)
        else:
            return super().__getitem__(index)

    def __contains__(self, o: Union[Clan, str]) -> bool:
        """Check whether internal list contains `o`."""
        # Allow string to be passed to compare vs. name.
        if isinstance(o, str):
            return o in (clan.name for clan in self)
        else:
            return o in self

    def get(
        self,
        id: Optional[int] = None,
        name: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> Optional[Clan]:
        """Get a clan by name, tag, or id."""
        for clan in self:
            if id is not None:
                if clan.id == id:
                    return clan
            elif name is not None:
                if clan.name == name:
                    return clan
            elif tag is not None:
                if clan.tag == tag:
                    return clan

        return None

    def append(self, clan: Clan) -> None:
        """Append `clan` to the list."""
        super().append(clan)

        if app.settings.DEBUG:
            log(f"{clan} added to clans list.")

    def extend(self, clans: Iterable[Clan]) -> None:
        """Extend the list with `clans`."""
        super().extend(clans)

        if app.settings.DEBUG:
            log(f"{clans} added to clans list.")

    def remove(self, clan: Clan) -> None:
        """Remove `clan` from the list."""
        super().remove(clan)

        if app.settings.DEBUG:
            log(f"{clan} removed from clans list.")

    async def prepare(self, db_conn: databases.core.Connection) -> None:
        """Fetch data from sql & return; preparing to run the server."""
        log("Fetching clans from sql.", Ansi.LCYAN)
        for row in await clans_repo.fetch_many():
            clan_members = await players_repo.fetch_many(clan_id=row["id"])
            clan = Clan(
                id=row["id"],
                name=row["name"],
                tag=row["tag"],
                created_at=row["created_at"],
                owner_id=row["owner"],
                member_ids={member["id"] for member in clan_members},
            )
            self.append(clan)


async def initialize_ram_caches(db_conn: databases.core.Connection) -> None:
    """Setup & cache the global collections before listening for connections."""
    # fetch channels, clans and pools from db
    await app.state.sessions.channels.prepare(db_conn)
    await app.state.sessions.clans.prepare(db_conn)
    await app.state.sessions.pools.prepare(db_conn)

    bot = await players_repo.fetch_one(id=1)
    if bot is None:
        raise RuntimeError("Bot account not found in database.")

    # create bot & add it to online players
    app.state.sessions.bot = Player(
        id=1,
        name=bot["name"],
        login_time=float(0x7FFFFFFF),  # (never auto-dc)
        priv=Privileges.UNRESTRICTED,
        bot_client=True,
    )
    app.state.sessions.players.append(app.state.sessions.bot)

    # global achievements (sorted by vn gamemodes)
    for row in await achievements_repo.fetch_many():
        achievement = Achievement(
            id=row["id"],
            file=row["file"],
            name=row["name"],
            desc=row["desc"],
            # NOTE: achievement conditions are stored as stringified python
            # expressions in the database to allow for extensive customizability.
            cond=eval(f'lambda score, mode_vn: {row.pop("cond")}'),
        )

        app.state.sessions.achievements.append(achievement)

    # static api keys
    app.state.sessions.api_keys = {
        row["api_key"]: row["id"]
        for row in await db_conn.fetch_all(
            "SELECT id, api_key FROM users WHERE api_key IS NOT NULL",
        )
    }
