

import os
import re
import aiofiles
from cmyui import Connection, Domain

""" ava: avatar server (for both ingame & external) """

domain = Domain('a.ppy.sh')

DEFAULT_AVA = f'.data/avatars/default.jpg'
@domain.route(re.compile(r'^/\d{1,10}(?:\.jpg)?$'))
async def get_avatar(conn: Connection) -> None:
    _path = f'.data/avatars/{conn.path[1:]}.jpg'
    path = (os.path.exists(_path) and _path) or DEFAULT_AVA

    async with aiofiles.open(path, 'rb') as f:
        await conn.send(200, await f.read())
