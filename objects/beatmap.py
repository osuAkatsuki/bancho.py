# -*- coding: utf-8 -*-

from typing import Final
from enum import IntEnum, unique
from requests import get as req_get
from collections import defaultdict

from console import printlog, Ansi
from objects import glob

__all__ = ('Beatmap',)

# For some ungodly reason, different values are used to
# represent different ranked statuses all throughout osu!
# This drives me and probably everyone else pretty insane,
# but we have nothing to do but deal with it B).

@unique
class RankedStatus(IntEnum):
    # Statuses used in getscores.php.
    # We'll use these for storing things
    # on the gulag side, and convert other
    # status enums to this instead for use.
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

    status: :class:`RankedStatus`
        The beatmap's name, including difficulty.
        # XXX: diff may be split off one day?
    """
    __slots__ = ('md5', 'id', 'set_id', 'artist', 'title', 'version', 'status')

    def __init__(self):
        self.md5 = ''
        self.id = 0
        self.set_id = 0

        self.artist = ''
        self.title = ''
        self.version = ''

        self.status = RankedStatus(0)

    @property
    def filename(self) -> str:
        return f'{self.id}.osu'

    def __repr__(self) -> str:
        return f'{self.artist} - {self.title} [{self.version}]'

    @classmethod
    def from_md5(cls, md5: str):
        # Try to get from sql.
        if (m := cls.from_md5_sql(md5)):
            return m

        # Not in sql, get from osu!api.
        if glob.config.osu_api_key:
            return cls.from_md5_osuapi(md5)

        printlog('Fetching beatmap requires osu!api key.', Ansi.LIGHT_RED)

    @classmethod
    def from_md5_sql(cls, md5: str):
        if not (res := glob.db.fetch(
            'SELECT id, set_id, status, artist, title, version '
            'FROM maps WHERE md5 = %s',
            [md5], _dict = False
        )): return

        m = cls()
        m.md5 = md5
        m.id, m.set_id = res[:2]
        m.status = RankedStatus(res[2])
        m.artist, m.title, m.version = res[3:]
        return m

    @classmethod
    def from_md5_osuapi(cls, md5: str):
        if not (r := req_get(
            'https://old.ppy.sh/api/get_beatmaps?k={key}&h={md5}'.format(
                key = glob.config.osu_api_key, md5 = md5
            )
        )) or r.text == '[]':
            return # osu!api request failed.

        apidata = r.json()[0]

        m = cls()
        m.md5 = md5

        m.id, m.set_id = (int(x) for x in (apidata['beatmap_id'], apidata['beatmapset_id']))
        m.status = RankedStatus.from_osuapi_status(int(apidata['approved']))
        m.artist, m.title, m.version = \
            apidata['artist'], apidata['title'], apidata['version']

        # Save this beatmap to our database.
        m.save_to_sql()
        printlog(f'Retrieved {m} from the osu!api.', Ansi.LIGHT_GREEN)
        return m

    def save_to_sql(self) -> None:
        if any(x is None for x in (
            self.md5, self.id, self.set_id, self.status,
            self.artist, self.title, self.version
        )):
            printlog('Tried to save invalid beatmap to SQL!', Ansi.LIGHT_RED)
            return

        glob.db.execute(
            'INSERT INTO maps (id, set_id, status, md5, '
            'artist, title, version) VALUES '
            '(%s, %s, %s, %s, %s, %s, %s)', [
                self.id, self.set_id, int(self.status), self.md5,
                self.artist, self.title, self.version
            ]
        )
