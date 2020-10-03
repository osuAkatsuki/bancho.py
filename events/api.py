# -*- coding: utf-8 -*-

from cmyui import AsyncConnection
import orjson
from typing import Callable, Optional
from urllib.parse import unquote

from objects import glob

glob.api_map = {}

def api_handler(uri: str) -> Callable:
    def register_callback(callback: Callable) -> Callable:
        glob.api_map |= {uri: callback}
        return callback
    return register_callback

@api_handler('get_online')
async def getOnline(conn: AsyncConnection) -> Optional[bytes]:
    """Get the current amount of online players."""
    # TODO: perhaps add peak(s)? (24h, 1w, 1m, etc.)
    return f'{{"online":{len(glob.players)-1}}}'.encode()

@api_handler('get_stats')
async def getStats(conn: AsyncConnection) -> Optional[bytes]:
    """Get the stats of a specified user (by id or name)."""
    if 'name' not in conn.args and 'id' not in conn.args:
        return b'Must provide either id or name!'

    if 'id' in conn.args:
        if not conn.args['id'].isdecimal():
            return b'Invalid player id.'

        pid = conn.args['id']
    else:
        if len(name := unquote(conn.args['name'])) > 16:
            return b'Invalid player name.'

        # Get their id from username.
        pid = await glob.db.fetch(
            'SELECT id FROM users '
            'WHERE name_safe = %s',
            [name]
        )

        if not pid:
            return b'User not found.'

        pid = pid['id']

    res = await glob.db.fetch(
        'SELECT * FROM stats '
        'WHERE id = %s',
        [pid]
    )

    return orjson.dumps(res) if res else b'User not found.'
