# -*- coding: utf-8 -*-

import re
import aiofiles
from pathlib import Path
from cmyui import Connection, Domain

""" ava: avatar server (for both ingame & external) """

domain = Domain('a.ppy.sh')

AVATARS_PATH = Path.cwd() / '.data/avatars'
DEFAULT_AVATAR = AVATARS_PATH / 'default.jpg'
@domain.route(re.compile(r'^/\d{1,10}(?:\.jpg)?$'))
async def get_avatar(conn: Connection) -> None:
    path = AVATARS_PATH / f'{conn.path[1:]}.jpg'

    if not path.exists():
        path = DEFAULT_AVATAR

    async with aiofiles.open(path, 'rb') as f:
        await conn.send(200, await f.read())
