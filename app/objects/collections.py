# TODO: there is still a lot of inconsistency
# in a lot of these classes; needs refactor.
from __future__ import annotations

import asyncio
from typing import Any
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
        for c in self:
            if c._name == name:
                return c

        return None

    def append(self, c: Channel) -> None:
        """Append `c` to the list."""
        super().append(c)

        if app.settings.DEBUG:
            log(f"{c} added to channels list.")

    def extend(self, cs: Iterable[Channel]) -> None:
        """Extend the list with `cs`."""
        super().extend(cs)

        if app.settings.DEBUG:
            log(f"{cs} added to channels list.")

    def remove(self, c: Channel) -> None:
        """Remove `c` from the list."""
        super().remove(c)

        if app.settings.DEBUG:
            log(f"{c} removed from channels list.")

    async def prepare(self, db_conn: databases.core.Connection) -> None:
        """Fetch data from sql & return; preparing to run the server."""
        log("Fetching channels from sql.", Ansi.LCYAN)
        for row in await db_conn.fetch_all("SELECT * FROM channels"):
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
        super().__init__([None] * 64)  # TODO: customizability?

    def __iter__(self) -> Iterator[Optional[Match]]:
        return super().__iter__()

    def __repr__(self) -> str:
        return f'[{", ".join(match.name for match in self if match)}]'

    def get_free(self) -> Optional[int]:
        """Return the first free match id from `self`."""
        for idx, m in enumerate(self):
            if m is None:
                return idx

        return None

    def append(self, m: Match) -> bool:
        """Append `m` to the list."""
        if (free := self.get_free()) is not None:
            # set the id of the match to the lowest available free.
            m.id = free
            self[free] = m

            if app.settings.DEBUG:
                log(f"{m} added to matches list.")

            return True
        else:
            log(f"Match list is full! Could not add {m}.")
            return False

    # TODO: extend

    def remove(self, m: Match) -> None:
        """Remove `m` from the list."""
        for i, _m in enumerate(self):
            if m is _m:
                self[i] = None
                break

        if app.settings.DEBUG:
            log(f"{m} removed from matches list.")


class Players(list[Player]):
    """The currently active players on the server."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __iter__(self) -> Iterator[Player]:
        return super().__iter__()

    def __contains__(self, p: Union[Player, str]) -> bool:
        # allow us to either pass in the player
        # obj, or the player name as a string.
        if isinstance(p, str):
            return p in (player.name for player in self)
        else:
            return super().__contains__(p)

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
        for p in self:
            if p not in immune:
                p.enqueue(data)

    @staticmethod
    def _parse_attr(kwargs: dict[str, Any]) -> tuple[str, object]:
        """Get first matched attr & val from input kwargs. Used in get() methods."""
        for attr in ("token", "id", "name"):
            if (val := kwargs.pop(attr, None)) is not None:
                if attr == "name":
                    attr = "safe_name"
                    val = make_safe_name(val)

                return attr, val
        else:
            raise ValueError("Incorrect call to Players.get()")

    def get(self, **kwargs: object) -> Optional[Player]:
        """Get a player by token, id, or name from cache."""
        attr, val = self._parse_attr(kwargs)

        for p in self:
            if getattr(p, attr) == val:
                return p

        return None

    async def get_sql(self, **kwargs: object) -> Optional[Player]:
        """Get a player by token, id, or name from sql."""
        attr, val = self._parse_attr(kwargs)

        # try to get from sql.
        row = await app.state.services.database.fetch_one(
            "SELECT id, name, priv, pw_bcrypt, country, "
            "silence_end, donor_end, clan_id, clan_priv, api_key "
            f"FROM users WHERE {attr} = :val",
            {"val": val},
        )

        if not row:
            return None

        row = dict(row)

        # encode pw_bcrypt from str -> bytes.
        row["pw_bcrypt"] = row["pw_bcrypt"].encode()

        if row["clan_id"] != 0:
            row["clan"] = app.state.sessions.clans.get(id=row["clan_id"])
            row["clan_priv"] = ClanPrivileges(row["clan_priv"])
        else:
            row["clan"] = row["clan_priv"] = None

        # country from acronym to {acronym, numeric}
        row["geoloc"] = {
            "latitude": 0.0,  # TODO
            "longitude": 0.0,
            "country": {
                "acronym": row["country"],
                "numeric": app.state.services.country_codes[row["country"]],
            },
        }

        return Player(**row, token="")

    async def from_cache_or_sql(self, **kwargs: object) -> Optional[Player]:
        """Try to get player from cache, or sql as fallback."""
        if p := self.get(**kwargs):
            return p
        elif p := await self.get_sql(**kwargs):
            return p

        return None

    async def from_login(
        self,
        name: str,
        pw_md5: str,
        sql: bool = False,
    ) -> Optional[Player]:
        """Return a player with a given name & pw_md5, from cache or sql."""
        if not (p := self.get(name=name)):
            if not sql:  # not to fetch from sql.
                return None

            if not (p := await self.get_sql(name=name)):
                # no player found in sql either.
                return None

        if app.state.cache.bcrypt[p.pw_bcrypt] == pw_md5.encode():
            return p

        return None

    def append(self, p: Player) -> None:
        """Append `p` to the list."""
        if p in self:
            if app.settings.DEBUG:
                log(f"{p} double-added to global player list?")
            return

        super().append(p)

    def remove(self, p: Player) -> None:
        """Remove `p` from the list."""
        if p not in self:
            if app.settings.DEBUG:
                log(f"{p} removed from player list when not online?")
            return

        super().remove(p)


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

    @staticmethod
    def _parse_attr(kwargs: dict[str, Any]) -> tuple[str, object]:
        """Get first matched attr & val from input kwargs. Used in get() methods."""
        for attr in ("id", "name"):
            if (val := kwargs.pop(attr, None)) is not None:
                return attr, val
        else:
            raise ValueError("Incorrect call to MapPools.get()")

    def get(self, **kwargs: object) -> Optional[MapPool]:
        """Get a mappool by id, or name from cache."""
        attr, val = self._parse_attr(kwargs)

        for p in self:
            if getattr(p, attr) == val:
                return p

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
        for p in self:
            if p.name == name:
                return p

        return None

    def append(self, m: MapPool) -> None:
        """Append `m` to the list."""
        super().append(m)

        if app.settings.DEBUG:
            log(f"{m} added to mappools list.")

    def extend(self, ms: Iterable[MapPool]) -> None:
        """Extend the list with `ms`."""
        super().extend(ms)

        if app.settings.DEBUG:
            log(f"{ms} added to mappools list.")

    def remove(self, m: MapPool) -> None:
        """Remove `m` from the list."""
        super().remove(m)

        if app.settings.DEBUG:
            log(f"{m} removed from mappools list.")

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

    def get(self, **kwargs: object) -> Optional[Clan]:
        """Get a clan by name, tag, or id."""
        for attr in ("name", "tag", "id"):
            if val := kwargs.pop(attr, None):
                break
        else:
            raise ValueError("Incorrect call to Clans.get()")

        for c in self:
            if getattr(c, attr) == val:
                return c

        return None

    def append(self, c: Clan) -> None:
        """Append `c` to the list."""
        super().append(c)

        if app.settings.DEBUG:
            log(f"{c} added to clans list.")

    def extend(self, cs: Iterable[Clan]) -> None:
        """Extend the list with `cs`."""
        super().extend(cs)

        if app.settings.DEBUG:
            log(f"{cs} added to clans list.")

    def remove(self, c: Clan) -> None:
        """Remove `m` from the list."""
        super().remove(c)

        if app.settings.DEBUG:
            log(f"{c} removed from clans list.")

    async def prepare(self, db_conn: databases.core.Connection) -> None:
        """Fetch data from sql & return; preparing to run the server."""
        log("Fetching clans from sql.", Ansi.LCYAN)
        for row in await db_conn.fetch_all("SELECT * FROM clans"):
            row = dict(row)  # make a mutable copy
            row["owner_id"] = row.pop("owner")
            clan = Clan(**row)
            await clan.members_from_sql(db_conn)
            self.append(clan)


async def initialize_ram_caches(db_conn: databases.core.Connection) -> None:
    """Setup & cache the global collections before listening for connections."""
    # fetch channels, clans and pools from db
    await app.state.sessions.channels.prepare(db_conn)
    await app.state.sessions.clans.prepare(db_conn)
    await app.state.sessions.pools.prepare(db_conn)

    bot_name = await app.utils.fetch_bot_name(db_conn)

    # create bot & add it to online players
    app.state.sessions.bot = Player(
        id=1,
        name=bot_name,
        login_time=float(0x7FFFFFFF),  # (never auto-dc)
        priv=Privileges.UNRESTRICTED,
        bot_client=True,
    )
    app.state.sessions.players.append(app.state.sessions.bot)

    # global achievements (sorted by vn gamemodes)
    for row in await db_conn.fetch_all("SELECT * FROM achievements"):
        # NOTE: achievement conditions are stored as stringified python
        # expressions in the database to allow for extensive customizability.
        row = dict(row)
        condition = eval(f'lambda score, mode_vn: {row.pop("cond")}')
        achievement = Achievement(**row, cond=condition)

        app.state.sessions.achievements.append(achievement)

    # static api keys
    app.state.sessions.api_keys = {
        row["api_key"]: row["id"]
        for row in await db_conn.fetch_all(
            "SELECT id, api_key FROM users WHERE api_key IS NOT NULL",
        )
    }
