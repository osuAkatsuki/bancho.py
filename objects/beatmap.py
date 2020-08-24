# -*- coding: utf-8 -*-

from enum import IntEnum, unique
from collections import defaultdict
from datetime import datetime as dt
from os.path import exists

from pp.owoppai import Owoppai
from console import plog, Ansi
from objects import glob
from constants.gamemodes import GameMode

__all__ = 'RankedStatus', 'Beatmap'

# For some ungodly reason, different values are used to
# represent different ranked statuses all throughout osu!
# This drives me and probably everyone else pretty insane,
# but we have nothing to do but deal with it B).

@unique
class RankedStatus(IntEnum):
    """A class to represent osu! ranked statuses server-side for gulag.
       These are the same as the statuses used in osu!'s getscores.php.
    """
    NotSubmitted = -1
    Pending = 0
    UpdateAvailable = 1
    Ranked = 2
    Approved = 3
    Qualified = 4
    Loved = 5

    @classmethod
    def osu_api(cls):
        # XXX: only the ones that exist are mapped.
        return {
            cls.Pending: 0,
            cls.Ranked: 1,
            cls.Approved: 2,
            cls.Qualified: 3,
            cls.Loved: 4
        }

    @classmethod
    def from_osuapi_status(cls, osuapi_status: int):
        return cls(
            defaultdict(lambda: cls.UpdateAvailable, {
                -2: cls.Pending, # Graveyard
                -1: cls.Pending, # WIP
                 0: cls.Pending,
                 1: cls.Ranked,
                 2: cls.Approved,
                 3: cls.Qualified,
                 4: cls.Loved
            })[osuapi_status]
        )

class Beatmap:
    """A class representing an osu! beatmap.

    Attributes
    -----------
    md5: :class:`str`
        The MD5 hash of the map's .osu file.

    id: :class:`int`
        The unique id of the beatmap.

    set_id: :class:`int`
        The unique id of the beatmap set.

    artist: :class:`str`
        The song's artist.

    title: :class:`str`
        The song's title.

    version: :class:`str`
        The difficulty name of the beatmap.

    creator: :class:`str`
        The beatmap's creator.

    last_update: :class:`datetime`
        The datetime of the beatmap's last update.
        Used for making sure we always have the newest version.

    status: :class:`RankedStatus`
        The ranked status of the beatmap.

    frozen: :class:`bool`
        Whether the beatmap's status is to be kept when a newer
        version is found in the osu!api.
        # XXX: This is set when a map's status is manually changed.

    mode: :class:`GameMode`
        The primary gamemode of the map.

    bpm: :class:`float`
        The BPM of the map.

    cs: :class:`float`
        The circle size of the beatmap.

    od: :class:`float`
        The overall difficulty of the beatmap.

    ar: :class:`float`
        The approach rate of the beatmap.

    hp: :class:`float`
        The health drain of the beatmap.

    diff: :class:`float`
        A float representing the star rating for the map's primary gamemode.

    pp_values: List[:class:`float`]
        A list of cached pp values for common accuracy values
        following fmt: [90%, 95%, 98%, 99%, 100%].
        # XXX: These are only cached for the map's primary mode.
    """
    __slots__ = ('md5', 'id', 'set_id',
                 'artist', 'title', 'version', 'creator',
                 'status', 'last_update', 'frozen',
                 'mode', 'bpm', 'cs', 'od', 'ar', 'hp',
                 'diff', 'pp_values')

    def __init__(self, **kwargs):
        self.md5 = kwargs.pop('md5', '')
        self.id = kwargs.pop('id', 0)
        self.set_id = kwargs.pop('set_id', 0)

        self.artist = kwargs.pop('artist', '')
        self.title = kwargs.pop('title', '')
        self.version = kwargs.pop('version', '')
        self.creator = kwargs.pop('creator', '')

        self.last_update: dt = kwargs.pop('last_update', dt(1, 1, 1))
        self.status = RankedStatus(kwargs.pop('status', 0))
        self.frozen = kwargs.pop('frozen', False)
        self.mode = GameMode(kwargs.pop('mode', 0))

        self.bpm = kwargs.pop('bpm', 0.0)
        self.cs = kwargs.pop('cs', 0.0)
        self.od = kwargs.pop('od', 0.0)
        self.ar = kwargs.pop('ar', 0.0)
        self.hp = kwargs.pop('hp', 0.0)

        self.diff = kwargs.pop('diff', 0.00)
        self.pp_values = [0.0, 0.0, 0.0, 0.0, 0.0]
        #                [90,  95,  98,  99,  100].

    @property
    def filename(self) -> str:
        return f'{self.id}.osu'

    @property
    def full(self) -> str:
        return f'{self.artist} - {self.title} [{self.version}]'

    @property
    def url(self):
        return f'https://osu.ppy.sh/b/{self.id}'

    @property
    def set_url(self) -> str:
        return f'https://osu.ppy.sh/s/{self.set_id}'

    @property
    def embed(self) -> str:
        return f'[{self.url} {self.full}]'

    @classmethod
    async def from_bid(cls, bid: int, cache_pp: bool = False):
        # Try to get from sql.
        if (m := await cls.from_bid_sql(bid)):
            if cache_pp:
                if not exists('pp/oppai'):
                    await plog('Missing pp calculator (pp/oppai)', Ansi.LIGHT_RED)
                else:
                    await m.cache_pp()

            return m

        # TODO: perhaps implement osuapi GET?
        # not sure how useful it would be..
        # I think i'll have md5 most times lol.

    @classmethod
    async def from_bid_sql(cls, bid: int):
        if not (res := await glob.db.fetch(
            'SELECT md5, set_id, status, '
            'artist, title, version '
            'FROM maps WHERE id = %s',
            [bid]
        )): return

        res['id'] = bid
        return cls(**res)

    @classmethod
    async def from_md5(cls, md5: str, cache_pp: bool = False):
        # Try to get from sql.
        if (m := await cls.from_md5_sql(md5)):
            if cache_pp:
                await m.cache_pp()

            return m

        # Not in sql, get from osu!api.
        if glob.config.osu_api_key:
            return await cls.from_md5_osuapi(md5)

        await plog('Fetching beatmap requires osu!api key.', Ansi.LIGHT_RED)

    @classmethod
    async def from_md5_sql(cls, md5: str):
        if not (res := await glob.db.fetch(
            'SELECT id, set_id, status, '
            'artist, title, version '
            'FROM maps WHERE md5 = %s',
            [md5]
        )): return

        res['md5'] = md5
        return cls(**res)

    @classmethod
    async def from_md5_osuapi(cls, md5: str):
        params = {'k': glob.config.osu_api_key, 'h': md5}
        async with glob.http.get(f'https://old.ppy.sh/api/get_beatmaps', params = params) as resp:
            if not resp or resp.status != 200 or await resp.read() == b'[]':
                return # osu!api request failed.

            apidata = (await resp.json())[0]

        m = cls()
        m.md5 = md5
        m.id = int(apidata['beatmap_id'])
        m.set_id = int(apidata['beatmapset_id'])
        m.status = RankedStatus.from_osuapi_status(int(apidata['approved']))
        m.artist, m.title, m.version, m.creator = (
            apidata['artist'],
            apidata['title'],
            apidata['version'],
            apidata['creator']
        )

        date_format = '%Y-%m-%d %H:%M:%S'
        m.last_update = dt.strptime(apidata['last_update'], date_format)

        m.mode = GameMode(int(apidata['mode']))
        m.bpm = float(apidata['bpm'])
        m.cs = float(apidata['diff_size'])
        m.od = float(apidata['diff_overall'])
        m.ar = float(apidata['diff_approach'])
        m.hp = float(apidata['diff_drain'])

        m.diff = float(apidata['difficultyrating'])

        res = await glob.db.fetch(
            'SELECT last_update, status, frozen '
            'FROM maps WHERE id = %s',
            [apidata['beatmap_id']]
        )

        if res:
            # If a map with this ID exists, check if the api
            # data if newer than the data we have server-side;
            # the map may have been updated by its creator.

            # XXX: temp fix for local server
            if not res['last_update']:
                res['last_update'] = dt(1, 1, 1)#'0001-01-01 00:00:00'

            #old = dt.strptime(res['last_update'], date_format)

            if m.last_update > res['last_update']:
                if res['frozen'] and m.status != res['status']:
                    # Keep the ranked status of maps through updates,
                    # if we've specified to (by 'freezing' it).
                    m.status = res['status']
                    m.frozen = res['frozen']

                await m.save_to_sql()
        else:
            # New map, just save to DB.
            await m.save_to_sql()

        await plog(f'Retrieved {m.full} from the osu!api.', Ansi.LIGHT_GREEN)
        return m

    async def cache_pp(self) -> None:
        owpi = Owoppai()
        await owpi.open_map(self.id)

        for idx, acc in enumerate((90, 95, 98, 99, 100)):
            owpi.accuracy = acc
            self.pp_values[idx] = (await owpi.calculate_pp())[0]

    async def save_to_sql(self) -> None:
        if any(x is None for x in (
            self.md5, self.id, self.set_id, self.status,
            self.artist, self.title, self.version, self.creator,
            self.last_update, self.frozen, self.mode, self.bpm,
            self.cs, self.od, self.ar, self.hp, self.diff
        )):
            await plog('Tried to save invalid beatmap to SQL!', Ansi.LIGHT_RED)
            return

        await glob.db.execute(
            'REPLACE INTO maps (id, set_id, status, md5, '
            'artist, title, version, creator, last_update, '
            'frozen, mode, bpm, cs, od, ar, hp, diff) VALUES ('
            '%s, %s, %s, %s, %s, %s, %s, %s, %s, '
            '%s, %s, %s, %s, %s, %s, %s, %s)', [
                self.id, self.set_id, int(self.status), self.md5,
                self.artist, self.title, self.version, self.creator,
                self.last_update, self.frozen, int(self.mode), self.bpm,
                self.cs, self.od, self.ar, self.hp, self.diff
            ]
        )
