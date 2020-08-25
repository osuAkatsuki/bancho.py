# -*- coding: utf-8 -*-

import orjson
from typing import Callable, Optional
from cmyui.web import AsyncRequest
from urllib.parse import unquote

from objects import glob

glob.api_map = {}

def api_handler(uri: str) -> Callable:
    def register_callback(callback: Callable) -> Callable:
        glob.api_map.update({uri: callback})
        return callback
    return register_callback

@api_handler('get_stats')
async def getStats(req: AsyncRequest) -> Optional[bytes]:
    if 'name' not in req.args and 'id' not in req.args:
        return b'Must provide either id or name!'

    if 'id' in req.args:
        if isinstance(req.args['id'], str):
            return b'Invalid player id.'

        pid = req.args['id']
    else:
        if len(name := unquote(req.args['name'])) > 16:
            return b'Invalid player name.'

        # Get their id from username.
        pid = await glob.db.fetch(
            'SELECT id FROM users '
            'WHERE name = %s',
            [name]
        )

        if not pid:
            return b'User not found.'

        pid = pid['id']

    res = await glob.db.fetch(
        'SELECT * FROM stats '
        f'WHERE id = %s',
        [pid]
    )

    return orjson.dumps(res) if res else b'User not found.'
