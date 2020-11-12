# -*- coding: utf-8 -*-

from typing import Optional
from enum import IntEnum, unique
from datetime import datetime
from collections import defaultdict
from cmyui import log, Ansi
import time

from utils.recalculator import PPCalculator
from objects import glob
from constants.gamemodes import GameMode
from constants.mods import Mods

__all__ = 'RankedStatus', 'Beatmap'

# for some ungodly reason, different values are used to
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

    @property
    def osu_api(self):
        """Convert the value to osu!api status."""
        # XXX: only the ones that exist are mapped.
        return {
            self.Pending: 0,
            self.Ranked: 1,
            self.Approved: 2,
            self.Qualified: 3,
            self.Loved: 4
        }[self.value]

    @classmethod
    def from_osuapi(cls, osuapi_status: int):
        """Convert from osu!api status."""
        return cls(
            defaultdict(lambda: cls.UpdateAvailable, {
                -2: cls.Pending, # graveyard
                -1: cls.Pending, # wip
                 0: cls.Pending,
                 1: cls.Ranked,
                 2: cls.Approved,
                 3: cls.Qualified,
                 4: cls.Loved
            })[osuapi_status]
        )

    @classmethod
    def from_osudirect(cls, osudirect_status: int):
        """Convert from osu!direct status."""
        return cls(
            defaultdict(lambda: cls.UpdateAvailable, {
                0: cls.Ranked,
                2: cls.Pending,
                3: cls.Qualified,
                #4: all ranked statuses lol
                5: cls.Pending, # graveyard
                7: cls.Ranked, # played before
                8: cls.Loved
            })[osudirect_status]
        )

    @classmethod
    def from_str(cls, status_str: str):
        """Convert from string value."""
        return cls( # could perhaps have `'unranked': cls.Pending`?
            defaultdict(lambda: cls.UpdateAvailable, {
                'pending': cls.Pending,
                'ranked': cls.Ranked,
                'approved': cls.Approved,
                'qualified': cls.Qualified,
                'loved': cls.Loved
            })[status_str]
        )

#@dataclass
#class BeatmapInfoRequest:
#    filenames: Sequence[str]
#    ids: Sequence[int]

#@dataclass
#class BeatmapInfo:
#    id: int # i16
#    map_id: int # i32
#    set_id: int # i32
#    thread_id: int # i32
#    status: int # u8
#    osu_rank: int # u8
#    fruits_rank: int # u8
#    taiko_rank: int # u8
#    mania_rank: int # u8
#    map_md5: str

class Beatmap:
    """A class representing an osu! beatmap.

    Possibly confusing attributes
    -----------
    frozen: `bool`
        Whether the beatmap's status is to be kept when a newer
        version is found in the osu!api.
        # XXX: This is set when a map's status is manually changed.

    pp_cache: dict[`Mods`, list[`float`]]
        Cached pp values to serve when a map is /np'ed.
        PP will be cached for whichever mod combination is requested.
    """
    __slots__ = ('md5', 'id', 'set_id',
                 'artist', 'title', 'version', 'creator',
                 'status', 'last_update', 'frozen',
                 'plays', 'passes',
                 'mode', 'bpm', 'cs', 'od', 'ar', 'hp',
                 'diff', 'pp_cache')

    def __init__(self, **kwargs):
        self.md5 = kwargs.pop('md5', '')
        self.id = kwargs.pop('id', 0)
        self.set_id = kwargs.pop('set_id', 0)

        self.artist = kwargs.pop('artist', '')
        self.title = kwargs.pop('title', '')
        self.version = kwargs.pop('version', '') # diff name
        self.creator = kwargs.pop('creator', '')

        self.last_update = kwargs.pop('last_update', datetime(1970, 1, 1))
        self.status = RankedStatus(kwargs.pop('status', 0))
        self.frozen = kwargs.pop('frozen', False) == 1

        self.plays = kwargs.pop('plays', 0)
        self.passes = kwargs.pop('passes', 0)

        self.mode = GameMode(kwargs.pop('mode', 0))
        self.bpm = kwargs.pop('bpm', 0.0)
        self.cs = kwargs.pop('cs', 0.0)
        self.od = kwargs.pop('od', 0.0)
        self.ar = kwargs.pop('ar', 0.0)
        self.hp = kwargs.pop('hp', 0.0)

        self.diff = kwargs.pop('diff', 0.00)
        self.pp_cache = {} # {mods: (acc: pp, ...), ...}

    @property
    def filename(self) -> str:
        """The name of `self`'s .osu file."""
        return f'{self.id}.osu'

    @property
    def full(self) -> str:
        """The full osu! formatted name `self`."""
        return f'{self.artist} - {self.title} [{self.version}]'

    @property
    def url(self):
        """The osu! beatmap url for `self`."""
        return f'https://osu.ppy.sh/b/{self.id}'

    @property
    def set_url(self) -> str:
        """The osu! beatmap set url for `self`."""
        return f'https://osu.ppy.sh/s/{self.set_id}'

    @property
    def embed(self) -> str:
        """An osu! chat embed to `self`'s osu! beatmap page."""
        return f'[{self.url} {self.full}]'

    @classmethod
    async def from_bid(cls, bid: int):
        """Create a `Beatmap` from sql using a beatmap id."""
        # TODO: perhaps some better caching solution that allows
        # for maps to be retrieved from the cache by id OR md5?

        # try to get from sql.
        if (m := await cls.from_bid_sql(bid)):
            # add the map to our cache.
            if m.md5 not in glob.cache['beatmap']:
                glob.cache['beatmap'][m.md5] = {
                    'timeout': time.time() + glob.config.map_cache_timeout,
                    'map': m
                }

            return m

        # TODO: perhaps implement osuapi GET?
        # not sure how useful it would be..
        # I think i'll have md5 most times lol.

    @classmethod
    async def from_bid_sql(cls, bid: int):
        if not (res := await glob.db.fetch(
            'SELECT set_id, status, md5, '
            'artist, title, version, creator, '
            'last_update, frozen, mode, plays, '
            'passes, bpm, cs, od, ar, hp, diff '
            'FROM maps WHERE id = %s',
            [bid]
        )): return

        return cls(**res, id=bid)

    @classmethod
    async def from_md5(cls, md5: str, set_id: Optional[int] = None):
        """Create a `Beatmap` from sql or osu!api using it's md5."""
        # check if the map is in the cache.
        if md5 in glob.cache['beatmap']:
            # check if our cached result is within timeout.
            cached = glob.cache['beatmap'][md5]

            if (time.time() - cached['timeout']) <= 0:
                # cache is within timeout.
                return cached['map']

            # cache is outdated and should be deleted.
            del glob.cache['beatmap'][md5]

        # check if the map is in the unsubmitted cache.
        if md5 in glob.cache['unsubmitted']:
            return

        # try to get from sql.
        if not (m := await cls.from_md5_sql(md5)):
            # Map not found in sql.

            # if the user has no api key, we cannot make
            # any further attempts to serve them the map.
            if not glob.config.osu_api_key:
                log('Fetching beatmap requires osu!api key.', Ansi.LRED)
                return

            # try to get from the osu!api.
            if not (m := await cls.from_md5_osuapi(md5, set_id)):
                return

        # save our map to the cache.
        glob.cache['beatmap'][md5] = {
            'timeout': (glob.config.map_cache_timeout +
                        time.time()),
            'map': m
        }
        return m

    @classmethod
    async def from_md5_sql(cls, md5: str):
        if not (res := await glob.db.fetch(
            'SELECT id, set_id, status, '
            'artist, title, version, creator, '
            'last_update, frozen, plays, passes, '
            'mode, bpm, cs, od, ar, hp, diff '
            'FROM maps WHERE md5 = %s',
            [md5]
        )): return

        return cls(**res, md5=md5)

    @classmethod
    async def from_md5_osuapi(cls, md5: str,
                              set_id: Optional[int] = None):
        if set_id:
            # cache the whole set's data.
            url = 'https://old.ppy.sh/api/get_beatmaps'
            params = {'k': glob.config.osu_api_key, 's': set_id}

            async with glob.http.get(url, params=params) as resp:
                if not resp or resp.status != 200:
                    return # osu!api request failed.

                # we want all maps returned, so get full json
                if not (apidata := await resp.json()):
                    return

            res = await glob.db.fetchall(
                'SELECT id, last_update, status, frozen '
                'FROM maps WHERE set_id = %s',
                [set_id], _dict=True
            )

            # get a tuple of the ones we
            # currently have in our database.
            current_data = {r['id']: {k: r[k] for k in set(r) - {'id'}}
                            for r in res}

            for bmap in apidata:
                # check if we have the map in our database already.
                if (map_id := int(bmap['beatmap_id'])) in current_data:
                    # if we do have the map, check if the osu!api
                    # is sending us a newer version of the map.

                    # convert the map's last_update time to datetime.
                    date_format = '%Y-%m-%d %H:%M:%S'
                    bmap['last_update'] = datetime.strptime(
                        bmap['last_update'], date_format
                    )

                    if bmap['last_update'] > current_data[map_id]['last_update']:
                        # the map we're receiving is indeed newer, check if the
                        # map's status is frozen in sql - if so, update the
                        # api's value before inserting it into the database.
                        api_status = RankedStatus.from_osuapi(int(bmap['approved']))

                        if current_data[map_id]['frozen'] \
                        and api_status != current_data[map_id]['status']:
                            # keep the ranked status of maps through updates,
                            # if we've specified to (by 'freezing' it).
                            bmap['approved'] = current_data[map_id]['status']
                            bmap['frozen'] = 1
                        else:
                            # map is not frozen, update
                            # it's status from the osu!api.
                            bmap['approved'] = api_status
                            bmap['frozen'] = 0
                    else:
                        # map is not newer than our current
                        # version, simply skip this map.
                        continue
                else:
                    # map not found in our database.
                    # copy the status from the osu!api,
                    # and do not freeze it's ranked status.
                    bmap['approved'] = RankedStatus.from_osuapi(int(bmap['approved']))
                    bmap['frozen'] = 0

                # since these are all straight off the osu!api,
                # they will always be the most up to date.
                await glob.db.execute(
                    'REPLACE INTO maps (id, set_id, status, '
                    'md5, artist, title, version, creator, '
                    'last_update, frozen, mode, bpm, cs, '
                    'od, ar, hp, diff) VALUES ('
                    '%s, %s, %s, %s, %s, %s, %s, %s, '
                    '%s, %s, %s, %s, %s, %s, %s, %s, %s)', [
                        bmap['beatmap_id'], bmap['beatmapset_id'],
                        int(bmap['approved']), bmap['file_md5'],
                        bmap['artist'], bmap['title'], bmap['version'],
                        bmap['creator'], bmap['last_update'],
                        bmap['frozen'], bmap['mode'], bmap['bpm'],
                        bmap['diff_size'], bmap['diff_overall'],
                        bmap['diff_approach'], bmap['diff_drain'],
                        bmap['difficultyrating']
                    ]
                )

            log(f'Retrieved full set {set_id} from the osu!api.', Ansi.LGREEN)
            return await cls.from_md5_sql(md5)

        url = 'https://old.ppy.sh/api/get_beatmaps'
        params = {'k': glob.config.osu_api_key, 'h': md5}

        async with glob.http.get(url, params=params) as resp:
            if not resp or resp.status != 200:
                return # osu!api request failed.

            if not (json := await resp.json()):
                return

            # just take the first map result
            apidata = json[0]

        m = cls()
        m.md5 = md5
        m.id = int(apidata['beatmap_id'])
        m.set_id = int(apidata['beatmapset_id'])
        m.status = RankedStatus.from_osuapi(int(apidata['approved']))
        m.artist, m.title, m.version, m.creator = (
            apidata['artist'],
            apidata['title'],
            apidata['version'],
            apidata['creator']
        )

        date_format = '%Y-%m-%d %H:%M:%S'
        m.last_update = datetime.strptime(
            apidata['last_update'], date_format
        )

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
            # if a map with this id exists, check if the api
            # data if newer than the data we have server-side;
            # the map may have been updated by its creator.
            if m.last_update > res['last_update']:
                if res['frozen'] and m.status != res['status']:
                    # keep the ranked status of maps through updates,
                    # if we've specified to (by 'freezing' it).
                    m.status = res['status']
                    m.frozen = res['frozen']

                await m.save_to_sql()
        else:
            # new map, just save to sql.
            await m.save_to_sql()

        log(f'Retrieved {m.full} from the osu!api.', Ansi.LGREEN)
        return m

    async def cache_pp(self, mods: Mods) -> None:
        """Cache some common acc pp values for specified mods."""
        self.pp_cache[mods] = [0.0, 0.0, 0.0, 0.0, 0.0]

        ppcalc = await PPCalculator.from_id(self.id, mode=self.mode, mods=mods)

        for idx, acc in enumerate((90, 95, 98, 99, 100)):
            ppcalc.acc = acc

            pp, _ = await ppcalc.perform() # don't need sr
            self.pp_cache[mods][idx] = pp

    async def save_to_sql(self) -> None:
        """Save the the object into sql."""
        if any(x is None for x in (
            self.md5, self.id, self.set_id, self.status,
            self.artist, self.title, self.version, self.creator,
            self.last_update, self.frozen, self.mode, self.bpm,
            self.cs, self.od, self.ar, self.hp, self.diff
        )):
            log('Tried to save invalid beatmap to SQL!', Ansi.LRED)
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
