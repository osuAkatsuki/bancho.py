# -*- coding: utf-8 -*-

from cmyui import AsyncConnection
import orjson
from typing import Callable, Optional
from urllib.parse import unquote

from constants.mods import Mods
from objects import glob

glob.api_map = {}

def register(uri: str) -> Callable:
    """Register a handler in `glob.api_map`."""
    def register_cb(callback: Callable) -> Callable:
        glob.api_map |= {uri: callback}
        return callback
    return register_cb

""" gulag api layout
  things we wanna be able to get:
    generic:
      total online users (TODO: 24h, 7d, etc. peaks)]

    specific:
      user info [profile & stats] (id, name)
      scores info (id, userid)
      beatmap info (md5, id, set_id, userid? (if bss))

  things we wanna be able to post (when we do post):
    messages (public or private [mail])
    userpage update
    avatar update

"""

@register('get_online')
async def getOnline(conn: AsyncConnection) -> Optional[bytes]:
    """Get the current amount of online players."""
    # TODO: perhaps add peak(s)? (24h, 5d, 3w, etc.)
    return f'Current: {{"online":{len(glob.players)-1}}}'.encode()

@register('get_user')
async def getUser(conn: AsyncConnection) -> Optional[bytes]:
    """Get user info/stats from a specified name or id."""
    if 'name' not in conn.args and 'id' not in conn.args:
        return b'Must provide either id or name!'

    if 'scope' not in conn.args \
    or conn.args['scope'] not in ('info', 'stats'):
        return b'Must provide scope (info/stats).'

    if 'id' in conn.args:
        if not conn.args['id'].isdecimal():
            return b'Invalid player id.'

        pid = conn.args['id']
    else:
        if not 2 <= len(name := unquote(conn.args['name'])) < 16:
            return b'Invalid player name.'

        # get their id from username.
        pid = await glob.db.fetch(
            'SELECT id FROM users '
            'WHERE name_safe = %s',
            [name]
        )

        if not pid:
            return b'User not found.'

        pid = pid['id']

    if conn.args['scope'] == 'info':
        # return user info
        query = ('SELECT id, name, name_safe, '
                 'priv, country, silence_end ' # silence_end public?
                 'FROM users WHERE id = %s')
    else:
        # return user stats
        query = 'SELECT * FROM stats WHERE id = %s'

    res = await glob.db.fetch(query, [pid])
    return orjson.dumps(res) if res else b'User not found.'

@register('get_scores')
async def getScores(conn: AsyncConnection) -> Optional[bytes]:
    if 'name' not in conn.args and 'id' not in conn.args:
        return b'Must provide either player id or name!'

    if 'id' in conn.args:
        if not conn.args['id'].isdecimal():
            return b'Invalid player id.'

        pid = conn.args['id']
    else:
        if not 2 <= len(name := unquote(conn.args['name'])) < 16:
            return b'Invalid player name.'

        # get their id from username.
        pid = await glob.db.fetch(
            'SELECT id FROM users '
            'WHERE name_safe = %s',
            [name]
        )

        if not pid:
            return b'User not found.'

        pid = pid['id']

    if 'mods' in conn.args:
        if not conn.args['mods'].isdecimal():
            return b'Invalid mods.'

        mods = Mods(int(conn.args['mods']))

        if mods & Mods.RELAX:
            mods &= ~Mods.RELAX
            table = 'scores_rx'
        elif mods & Mods.AUTOPILOT:
            mods &= ~Mods.AUTOPILOT
            table = 'scores_ap'
        else:
            table = 'scores_vn'
    else:
        mods = Mods.NOMOD
        table = 'scores_vn'

    if 'limit' in conn.args:
        if not conn.args['limit'].isdecimal():
            return b'Invalid limit.'

        limit = min(int(conn.args['limit']), 100)
    else:
        limit = 100

    res = await glob.db.fetchall(
        'SELECT id, map_md5, score, pp, acc, max_combo, mods, '
        'n300, n100, n50, nmiss, ngeki, nkatu, grade, status, '
        'mode, play_time, time_elapsed, userid, perfect '
        f'FROM {table} WHERE userid = %s '
        'ORDER BY id DESC LIMIT %s',
        [pid, limit]
    )

    return orjson.dumps(res) if res else b'No scores found.'
