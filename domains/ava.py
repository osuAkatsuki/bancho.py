# -*- coding: utf-8 -*-

import re
from pathlib import Path
from typing import Optional
from typing import Union

from cmyui.web import Connection
from cmyui.web import Domain

from objects import glob

HTTPResponse = Optional[Union[bytes, tuple[int, bytes]]]

""" ava: avatar server (for both ingame & external) """

BASE_DOMAIN = glob.config.domain
domain = Domain({f'a.{BASE_DOMAIN}', 'a.ppy.sh'})

AVATARS_PATH = Path.cwd() / '.data/avatars'
DEFAULT_AVATAR = AVATARS_PATH / 'default.jpg'
@domain.route(re.compile(r'^/(?:\d{1,10}(?:\.(?:jpg|jpeg|png))?|favicon\.ico)?$'))
async def get_avatar(conn: Connection) -> HTTPResponse:
    filename = conn.path[1:]

    if '.' in filename:
        # user id & file extension provided
        path = AVATARS_PATH / filename
        if not path.exists():
            path = DEFAULT_AVATAR
    elif filename not in ('', 'favicon.ico'):
        # user id provided - determine file extension
        for ext in ('jpg', 'jpeg', 'png'):
            path = AVATARS_PATH / f'{filename}.{ext}'
            if path.exists():
                break
        else:
            # no file exists
            path = DEFAULT_AVATAR
    else:
        # empty path or favicon, serve default avatar
        path = DEFAULT_AVATAR

    ext = 'png' if path.suffix == '.png' else 'jpeg'
    conn.resp_headers['Content-Type'] = f'image/{ext}'
    return path.read_bytes()
