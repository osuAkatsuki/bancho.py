# -*- coding: utf-8 -*-

import functools
from collections import defaultdict
#from dataclasses import dataclass
from datetime import timedelta
from datetime import datetime
from enum import IntEnum
from enum import unique
from typing import Optional

import aiomysql
from cmyui.logging import Ansi
from cmyui.logging import log

import utils.misc
from constants.gamemodes import GameMode
from constants.mods import Mods
from objects import glob
from utils.misc import escape_enum
from utils.misc import pymysql_encode
from utils.recalculator import PPCalculator

__all__ = ('RankedStatus', 'Beatmap')

BASE_DOMAIN = glob.config.domain

OSUAPI_GET_BEATMAPS = 'https://old.ppy.sh/api/get_beatmaps'

DEFAULT_LAST_UPDATE = datetime(1970, 1, 1)
MAP_CACHE_TIMEOUT = timedelta(hours=4)

IGNORED_BEATMAP_CHARS = dict.fromkeys(map(ord, r':\/*<>?"|'), None)

# for some ungodly reason, different values are used to
# represent different ranked statuses all throughout osu!
# This drives me and probably everyone else pretty insane,
# but we have nothing to do but deal with it B).

@unique
@pymysql_encode(escape_enum)
class RankedStatus(IntEnum):
    """Server side osu! beatmap ranked statuses.
       Same as used in osu!'s /web/getscores.php.
    """
    NotSubmitted = -1
    Pending = 0
    UpdateAvailable = 1
    Ranked = 2
    Approved = 3
    Qualified = 4
    Loved = 5

    def __str__(self) -> str:
        return gulagstatus2str_dict[self.value]

    @property
    def osu_api(self) -> int:
        """Convert the value to osu!api status."""
        # XXX: only the ones that exist are mapped.
        return gulag2osuapistatus_dict[self.value]

    @staticmethod
    def from_osuapi(osuapi_status: int) -> 'RankedStatus':
        """Convert from osu!api status."""
        return osu2gulagstatus_dict[osuapi_status]

    @staticmethod
    def from_osudirect(osudirect_status: int) -> 'RankedStatus':
        """Convert from osu!direct status."""
        return direct2gulagstatus_dict[osudirect_status]

    @staticmethod
    def from_str(status_str: str) -> 'RankedStatus':
        """Convert from string value.""" # could perhaps have `'unranked': cls.Pending`?
        return str2gulagstatus_dict[status_str]

osu2gulagstatus_dict = defaultdict(
    lambda: RankedStatus.UpdateAvailable, {
        -2: RankedStatus.Pending, # graveyard
        -1: RankedStatus.Pending, # wip
        0:  RankedStatus.Pending,
        1:  RankedStatus.Ranked,
        2:  RankedStatus.Approved,
        3:  RankedStatus.Qualified,
        4:  RankedStatus.Loved
    }
)

direct2gulagstatus_dict = defaultdict(
    lambda: RankedStatus.UpdateAvailable, {
        0: RankedStatus.Ranked,
        2: RankedStatus.Pending,
        3: RankedStatus.Qualified,
        #4: all ranked statuses lol
        5: RankedStatus.Pending, # graveyard
        7: RankedStatus.Ranked, # played before
        8: RankedStatus.Loved
    }
)

gulag2osuapistatus_dict = {
    RankedStatus.Pending: 0,
    RankedStatus.Ranked: 1,
    RankedStatus.Approved: 2,
    RankedStatus.Qualified: 3,
    RankedStatus.Loved: 4
}

str2gulagstatus_dict = defaultdict(
    lambda: RankedStatus.UpdateAvailable, {
        'pending': RankedStatus.Pending,
        'ranked': RankedStatus.Ranked,
        'approved': RankedStatus.Approved,
        'qualified': RankedStatus.Qualified,
        'loved': RankedStatus.Loved
    }
)

gulagstatus2str_dict = {
    RankedStatus.NotSubmitted: 'Unsubmitted',
    RankedStatus.Pending: 'Unranked',
    RankedStatus.UpdateAvailable: 'Outdated',
    RankedStatus.Ranked: 'Ranked',
    RankedStatus.Approved: 'Approved',
    RankedStatus.Qualified: 'Qualified',
    RankedStatus.Loved: 'Loved'
}

async def osuapiv1_getbeatmaps(**params) -> Optional[dict[str, object]]:
    """Fetch data from the osu!api with a beatmap's md5."""
    if glob.app.debug:
        log(f'Doing osu!api (getbeatmaps) request {params}', Ansi.LMAGENTA)

    params['k'] = glob.config.osu_api_key

    async with glob.http.get(OSUAPI_GET_BEATMAPS, params=params) as resp:
        if (
            resp and resp.status == 200 and
            resp.content.total_bytes != 2 # b'[]'
        ):
            return await resp.json()

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
    __slots__ = ('set', 'md5', 'id', 'set_id',
                 'artist', 'title', 'version', 'creator',
                 'filename', 'last_update', 'total_length',
                 'max_combo', 'status', 'frozen',
                 'plays', 'passes', 'mode', 'bpm',
                 'cs', 'od', 'ar', 'hp',
                 'diff', 'pp_cache')

    def __init__(self, **kwargs) -> None:
        self.set: Optional[BeatmapSet] = None

        self.md5 = kwargs.get('md5', '')
        self.id = kwargs.get('id', 0)
        self.set_id = kwargs.get('set_id', 0)

        self.artist = kwargs.get('artist', '')
        self.title = kwargs.get('title', '')
        self.version = kwargs.get('version', '') # diff name
        self.creator = kwargs.get('creator', '')

        self.filename = kwargs.get('filename', '')

        self.last_update = kwargs.get('last_update', DEFAULT_LAST_UPDATE)
        self.total_length = kwargs.get('total_length', 0)
        self.max_combo = kwargs.get('max_combo', 0)

        self.status = RankedStatus(kwargs.get('status', 0))
        self.frozen = kwargs.get('frozen', False) == 1

        self.plays = kwargs.get('plays', 0)
        self.passes = kwargs.get('passes', 0)

        self.mode = GameMode(kwargs.get('mode', 0))
        self.bpm = kwargs.get('bpm', 0.0)
        self.cs = kwargs.get('cs', 0.0)
        self.od = kwargs.get('od', 0.0)
        self.ar = kwargs.get('ar', 0.0)
        self.hp = kwargs.get('hp', 0.0)

        self.diff = kwargs.get('diff', 0.00)
        self.pp_cache = {0: {}, 1: {}, 2: {}, 3: {}} # {mode_vn: {mods: (acc/score: pp, ...), ...}}

    def __repr__(self) -> str:
        return self.full

    @property
    def full(self) -> str:
        """The full osu! formatted name `self`."""
        return f'{self.artist} - {self.title} [{self.version}]'

    @property
    def url(self) -> str:
        """The osu! beatmap url for `self`."""
        return f'https://osu.{BASE_DOMAIN}/beatmaps/{self.id}'

    @property
    def embed(self) -> str:
        """An osu! chat embed to `self`'s osu! beatmap page."""
        return f'[{self.url} {self.full}]'

    @property
    def awards_pp(self) -> bool:
        """Return whether the map's status awards pp for scores."""
        return self.status in (RankedStatus.Ranked,
                               RankedStatus.Approved)

    # TODO: implement some locking for the map fetch methods

    """ High level API """
    # There are three levels of storage used for beatmaps,
    # the cache (ram), the db (disk), and the osu!api (web).
    # Going down this list gets exponentially slower, so
    # we always prioritze what's fastest when possible.
    # These methods will keep beatmaps reasonably up to
    # date and use the fastest storage available, while
    # populating the higher levels of the cache with new maps.

    @classmethod
    async def from_md5(cls, md5: str, set_id: int = -1) -> Optional['Beatmap']:
        """Fetch a map from the cache, database, or osuapi by md5."""
        bmap = await cls._from_md5_cache(md5)

        if not bmap:
            if set_id <= 0:
                # valid set id not provided, try getting it
                # from the db, or the osu!api. we want to get
                # the whole set cached all at once to minimize
                # osu!api requests overall in the long run.
                res = await glob.db.fetch(
                    'SELECT set_id '
                    'FROM maps '
                    'WHERE md5 = %s',
                    [md5]
                )

                if res:
                    # found set id in db
                    set_id = res['set_id']
                else:
                    # failed to get from db, try osu!api
                    api_data = await osuapiv1_getbeatmaps(h=md5)

                    if not api_data:
                        return

                    set_id = int(api_data[0]['beatmapset_id'])

            # we have a valid set id, fetch the whole set.
            if not await BeatmapSet.from_bsid(set_id):
                return

            # fetching the set will put all maps in cache
            bmap = await cls._from_md5_cache(md5)

            if not bmap:
                return

        return bmap

    @classmethod
    async def from_bid(cls, bid: int) -> Optional['Beatmap']:
        """Fetch a map from the cache, database, or osuapi by id."""
        bmap = await cls._from_bid_cache(bid)

        if not bmap:
            # try getting the set id either from the db,
            # or the osu!api. we want to get the whole set
            # cached all at once to minimize osu!api
            # requests overall in the long run
            res = await glob.db.fetch(
                'SELECT set_id '
                'FROM maps '
                'WHERE id = %s',
                [bid]
            )

            if res:
                # found set id in db
                set_id = res['set_id']
            else:
                # failed to get from db, try osu!api
                api_data = await osuapiv1_getbeatmaps(b=bid)

                if not api_data:
                    return

                set_id = int(api_data[0]['beatmapset_id'])

            # we have a valid set id, fetch the whole set.
            if not await BeatmapSet.from_bsid(set_id):
                return

            # fetching the set will put all maps in cache
            bmap = await cls._from_bid_cache(bid)

            if not bmap:
                return

        return bmap

    async def cache_pp(self, mods: Mods) -> None:
        """Cache some common acc pp values for specified mods."""
        mode_vn = self.mode.as_vanilla
        self.pp_cache[mode_vn][mods] = [0.0, 0.0, 0.0, 0.0, 0.0]

        ppcalc = await PPCalculator.from_map(self, mods=mods, mode_vn=mode_vn)

        if not ppcalc:
            return

        if mode_vn in (0, 1): # std/taiko, use acc
            for idx, acc in enumerate(glob.config.pp_cached_accs):
                ppcalc.pp_attrs['acc'] = acc

                pp, _ = await ppcalc.perform() # don't need sr
                self.pp_cache[mode_vn][mods][idx] = pp
        elif mode_vn == 2:
            return # unsupported gm
        elif mode_vn == 3: # mania, use score
            for idx, score in enumerate(glob.config.pp_cached_scores):
                ppcalc.pp_attrs['score'] = score

                pp, _ = await ppcalc.perform()
                self.pp_cache[mode_vn][mods][idx] = pp

    """ Lower level API """
    # These functions are meant for internal use under
    # all normal circumstances and should only be used
    # if you're really modifying gulag by adding new
    # features, or perhaps optimizing parts of the code.

    def _parse_from_osuapi_resp(self, osuapi_resp: dict[str, object]) -> None:
        """Change internal data with the data in osu!api format."""
        # NOTE: `self` is not guaranteed to have any attributes
        #       initialized when this is called.
        self.md5 = osuapi_resp['file_md5']
        #self.id = int(osuapi_resp['beatmap_id'])
        self.set_id = int(osuapi_resp['beatmapset_id'])

        self.artist, self.title, self.version, self.creator = (
            osuapi_resp['artist'], osuapi_resp['title'],
            osuapi_resp['version'], osuapi_resp['creator']
        )

        self.filename = (
            '{artist} - {title} ({creator}) [{version}].osu'
        ).format(**osuapi_resp).translate(IGNORED_BEATMAP_CHARS)

        # quite a bit faster than using dt.strptime.
        _last_update = osuapi_resp['last_update']
        self.last_update = datetime(
            year=int(_last_update[0:4]),
            month=int(_last_update[5:7]),
            day=int(_last_update[8:10]),
            hour=int(_last_update[11:13]),
            minute=int(_last_update[14:16]),
            second=int(_last_update[17:19])
        )

        self.total_length = int(osuapi_resp['total_length'])

        if osuapi_resp['max_combo'] is not None:
            self.max_combo = int(osuapi_resp['max_combo'])
        else:
            self.max_combo = 0

        # if a map is 'frozen', we keeps it's status
        # even after an update from the osu!api.
        if not getattr(self, 'frozen', False):
            self.status = RankedStatus.from_osuapi(int(osuapi_resp['approved']))

        self.mode = GameMode(int(osuapi_resp['mode']))
        self.bpm = float(osuapi_resp['bpm'])
        self.cs = float(osuapi_resp['diff_size'])
        self.od = float(osuapi_resp['diff_overall'])
        self.ar = float(osuapi_resp['diff_approach'])
        self.hp = float(osuapi_resp['diff_drain'])

        self.diff = float(osuapi_resp['difficultyrating'])

    @staticmethod
    async def _from_md5_cache(md5: str) -> Optional['Beatmap']:
        """Fetch a map from the cache by md5."""
        if md5 in glob.cache['beatmap']:
            bmap: Beatmap = glob.cache['beatmap'][md5]

            if bmap.set.cache_expired():
                await bmap.set._update_if_available()

            return bmap

    @staticmethod
    async def _from_bid_cache(bid: int) -> Optional['Beatmap']:
        """Fetch a map from the cache by id."""
        if bid in glob.cache['beatmap']:
            bmap: Beatmap = glob.cache['beatmap'][bid]

            if bmap.set.cache_expired():
                await bmap.set._update_if_available()

            return bmap

class BeatmapSet:
    __slots__ = ('id', 'last_osuapi_check', 'maps')

    def __init__(self, **kwargs) -> None:
        self.id = kwargs.get('id', 0)

        self.last_osuapi_check: Optional[datetime] = kwargs.get('last_osuapi_check', None)
        self.maps: list[Beatmap] = kwargs.get('maps', [])

    @functools.lru_cache(maxsize=256)
    def __repr__(self) -> str:
        map_names = []
        for bmap in self.maps:
            name = f'{bmap.artist} - {bmap.title}'
            if name not in map_names:
                map_names.append(name)
        return ', '.join(map_names)

    @property
    def url(self) -> str: # same as above, just no beatmap id
        """The online url for this beatmap set."""
        return f'https://osu.{BASE_DOMAIN}/beatmapsets/{self.id}'

    @functools.cache
    def all_officially_ranked_or_approved(self) -> bool:
        """Whether all of the maps in the set are
           ranked or approved on official servers."""
        for bmap in self.maps:
            if (
                bmap.status not in (RankedStatus.Ranked,
                                    RankedStatus.Approved) or
                bmap.frozen # ranked/approved, but only on gulag
            ):
                return False
        return True

    @functools.cache
    def all_officially_loved(self) -> bool:
        """Whether all of the maps in the set are
           loved on official servers."""
        for bmap in self.maps:
            if (
                bmap.status != RankedStatus.Loved or
                bmap.frozen # loved, but only on gulag
            ):
                return False
        return True

    def cache_expired(self) -> bool:
        """Whether the cached version of the set is
           expired and needs an update from the osu!api."""
        # ranked & approved maps are update-locked.
        if self.all_officially_ranked_or_approved():
            return False

        # TODO: check for further patterns to signify that maps could be
        # checked less often, such as how long since their last update.

        timeout = MAP_CACHE_TIMEOUT

        # loved maps may be updated, but it's less
        # likely for a mapper to remove a leaderboard.
        if self.all_officially_loved():
            timeout *= 4

        return datetime.now() > (self.last_osuapi_check + timeout)

    async def _update_if_available(self) -> None:
        """Fetch newest data from the osu!api, check for differences
           and propogate any update into our cache & database."""
        if api_data := await osuapiv1_getbeatmaps(s=self.id):
            current_maps = {bmap.id: bmap for bmap in self.maps}
            self.last_osuapi_check = datetime.now()

            for api_bmap in api_data:
                bmap_id = int(api_bmap['beatmap_id'])
                if bmap_id not in current_maps:
                    # we don't have this bmap id, add it to cache & db
                    bmap: 'Beatmap' = Beatmap.__new__(Beatmap)
                    bmap.id = bmap_id

                    bmap._parse_from_osuapi_resp(api_bmap)

                    # (some gulag-specific stuff not given by api)
                    bmap.frozen = False
                    bmap.passes = 0
                    bmap.plays = 0
                    bmap.pp_cache = {0: {}, 1: {}, 2: {}, 3: {}}
                elif api_bmap['file_md5'] != current_maps[bmap_id].md5:
                    # this is a newer version than we have
                    bmap = current_maps[bmap_id]
                    bmap._parse_from_osuapi_resp(api_bmap)

            await self._save_to_sql()
        else:
            # we have the map on disk but it's been removed from the osu!api.
            # i want to see how frequently this happens and see some examples
            # of when it's triggered since i'm not 100% sure about it, cheers.
            utils.misc.log_strange_occurrence(
                f'_update_if_available no data, setid: {self.id}'
            )

    async def _save_to_sql(self) -> None:
        """Save the object's attributes into the database."""
        async with glob.db.pool.acquire() as db_conn:
            async with db_conn.cursor() as db_cursor:
                await db_cursor.execute(
                    'REPLACE INTO mapsets '
                    '(server, id, last_osuapi_check) '
                    'VALUES ("osu!", %s, %s)',
                    [self.id, self.last_osuapi_check]
                )

                await db_cursor.executemany(
                    'REPLACE INTO maps ('
                        'server, md5, id, set_id, '
                        'artist, title, version, creator, '
                        'filename, last_update, total_length, '
                        'max_combo, status, frozen, '
                        'plays, passes, mode, bpm, '
                        'cs, od, ar, hp, diff'
                    ') VALUES ('
                        '"osu!", %s, %s, %s, '
                        '%s, %s, %s, %s, '
                        '%s, %s, %s, '
                        '%s, %s, %s, '
                        '%s, %s, %s, %s, '
                        '%s, %s, %s, %s, %s'
                    ')', [(
                        bmap.md5, bmap.id, bmap.set_id,
                        bmap.artist, bmap.title, bmap.version, bmap.creator,
                        bmap.filename, bmap.last_update, bmap.total_length,
                        bmap.max_combo, bmap.status, bmap.frozen,
                        bmap.plays, bmap.passes, bmap.mode, bmap.bpm,
                        bmap.cs, bmap.od, bmap.ar, bmap.hp, bmap.diff
                    ) for bmap in self.maps]
                )

    @staticmethod
    async def _from_bsid_cache(bsid: int) -> Optional['BeatmapSet']:
        """Fetch a mapset from the cache by set id."""
        if bsid in glob.cache['beatmapset']:
            bmap_set: BeatmapSet = glob.cache['beatmapset'][bsid]

            if bmap_set.cache_expired():
                await bmap_set._update_if_available()

            return glob.cache['beatmapset'][bsid]

    @classmethod
    async def _from_bsid_sql(cls, bsid: int) -> Optional['BeatmapSet']:
        """Fetch a mapset from the database by set id."""
        async with glob.db.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as db_cursor:

                await db_cursor.execute(
                    'SELECT last_osuapi_check '
                    'FROM mapsets '
                    'WHERE id = %s',
                    [bsid]
                )
                set_res = await db_cursor.fetchone()

                if not set_res:
                    return

                await db_cursor.execute(
                    'SELECT md5, id, set_id, '
                    'artist, title, version, creator, '
                    'filename, last_update, total_length, '
                    'max_combo, status, frozen, '
                    'plays, passes, mode, bpm, '
                    'cs, od, ar, hp, diff '
                    'FROM maps '
                    'WHERE set_id = %s',
                    [bsid]
                )

                if db_cursor.rowcount == 0:
                    return

                bmap_set = cls(id=bsid, **set_res)

                async for row in db_cursor:
                    bmap = Beatmap(**row)

                    # XXX: tempfix for gulag <v3.4.1,
                    # where filenames weren't stored.
                    if not bmap.filename:
                        bmap.filename = (
                            '{artist} - {title} ({creator}) [{version}].osu'
                        ).format(**row).translate(IGNORED_BEATMAP_CHARS)

                        await glob.db.execute(
                            'UPDATE maps '
                            'SET filename = %s '
                            'WHERE id = %s',
                            [bmap.filename, bmap.id]
                        )

                    bmap.set = bmap_set
                    bmap_set.maps.append(bmap)

        return bmap_set

    @classmethod
    async def _from_bsid_osuapi(cls, bsid: int) -> Optional['BeatmapSet']:
        """Fetch a mapset from the osu!api by set id."""
        if api_data := await osuapiv1_getbeatmaps(s=bsid):
            self: 'BeatmapSet' = cls.__new__(cls)
            self.id = bsid
            self.maps = []
            self.last_osuapi_check = datetime.now()

            # XXX: pre-mapset gulag support
            # select all current beatmaps
            # that're frozen in the db
            res = await glob.db.fetchall(
                'SELECT id, status '
                'FROM maps '
                'WHERE set_id = %s '
                'AND frozen = 1',
                [bsid]
            )

            current_maps = {row['id']: row['status'] for row in res}

            for api_bmap in api_data:
                # newer version available for this map
                bmap: 'Beatmap' = Beatmap.__new__(Beatmap)
                bmap.id = int(api_bmap['beatmap_id'])

                if bmap.id in current_maps:
                    # map is currently frozen, keep it's status.
                    bmap.status = RankedStatus(current_maps[bmap.id])
                    bmap.frozen = True
                else:
                    bmap.frozen = False

                bmap._parse_from_osuapi_resp(api_bmap)

                # (some gulag-specific stuff not given by api)
                bmap.pp_cache = {0: {}, 1: {}, 2: {}, 3: {}}
                bmap.passes = 0
                bmap.plays = 0

                bmap.set = self
                self.maps.append(bmap)

            await self._save_to_sql()
            return self

    @classmethod
    async def from_bsid(cls, bsid: int) -> Optional['Beatmap']:
        """Cache all maps in a set from the osuapi, optionally
           returning beatmaps by their md5 or id."""
        bmap_set = await cls._from_bsid_cache(bsid)
        did_api_request = False

        if not bmap_set:
            bmap_set = await cls._from_bsid_sql(bsid)

            if not bmap_set:
                if not glob.has_internet:
                    return

                bmap_set = await cls._from_bsid_osuapi(bsid)

                if not bmap_set:
                    return

                did_api_request = True

        # cache the individual maps & set for future requests
        beatmapset_cache = glob.cache['beatmapset']
        beatmap_cache = glob.cache['beatmap']

        beatmapset_cache[bsid] = bmap_set

        for bmap in bmap_set.maps:
            beatmap_cache[bmap.md5] = bmap
            beatmap_cache[bmap.id] = bmap

        # TODO: this can be done less often for certain types of maps,
        # such as ones that're ranked on bancho and won't be updated,
        # and perhaps ones that haven't been updated in a long time.
        if not did_api_request and bmap_set.cache_expired():
            await bmap_set._update_if_available()

        return bmap_set
