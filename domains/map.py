# -*- coding: utf-8 -*-

import re
from typing import Optional

from cmyui.web import Connection
from cmyui.web import Domain

from objects import glob

""" bmap: static beatmap info (thumbnails, previews, etc.) """

BASE_DOMAIN = glob.config.domain
domain = Domain({f'b.{BASE_DOMAIN}', 'b.ppy.sh'})

# for now, just send everything to osu!
# eventually if we do bmap submission, we'll need this.
@domain.route(re.compile(r'^.+$'))
async def everything(conn: Connection) -> Optional[bytes]:
    conn.resp_headers['Location'] = f'https://b.ppy.sh{conn.path}'
    return (301, b'')
