from typing import Optional, Callable
from enum import IntEnum, unique
from time import time
from requests import get as req_get

from constants.mods import Mods
from objects import glob
from cmyui.web import Request
from console import printlog

# For /web/ requests, we send the
# data directly back in the event.

glob.web_map = {}

def web_handler(uri: str) -> Callable:
    def register_callback(callback: Callable) -> Callable:
        glob.web_map.update({uri: callback})
        return callback
    return register_callback

@unique
class RankingType(IntEnum):
    Local = 0
    Top = 1
    Mods = 2
    Friends = 3
    Country = 4

required_params_submitModular = frozenset({
    'x', 'ft', 'score', 'fs', 'bmk', 'iv',
    'c1', 'st', 'pass', 'osuver', 's'
})
@web_handler('osu-submit-modular.php')
def submitModularSelector(req: Request) -> Optional[bytes]:
    if not all(x in req.args for x in required_params_submitModular):
        printlog(f'submit-modular req missing params.')
        return

    pass

required_params_getScores = frozenset({
    's', 'vv', 'v', 'c',
    'f', 'm', 'i', 'mods',
    'h', 'a', 'us', 'ha'
})
@web_handler('osu-osz2-getscores.php')
def getScores(req: Request) -> Optional[bytes]:
    if not all(x in req.args for x in required_params_getScores):
        printlog(f'get-scores req missing params.')
        return

    if len(req.args['c']) != 32:
        return

    if not req.args['mods'].isnumeric():
        return

    req.args['mods'] = int(req.args['mods'])

    res: List[bytes] = []

    if req.args['mods'] & Mods.RELAX:
        table = 'scores_rx'
        scoring = 'pp'
    else:
        table = 'scores_vn'
        scoring = 'score'

    if not (bmap := glob.db.fetch(
        'SELECT id, set_id, status, name FROM maps WHERE md5 = %s',
        [req.args['c']]
    )):
        if not (r := req_get(
            'https://old.ppy.sh/api/get_beatmaps?k={key}&h={md5}'.format(
                key = glob.config.osu_api_key, md5 = req.args['c']
            )
        )):
            # Request to osu!api failed.
            return

        if r.text == '[]':
            # API returned an empty set.
            # TODO: return unsubmitted status.
            return

        _apidata = r.json()[0]
        bmap = {
            'id': int(_apidata['beatmap_id']),
            'set_id': int(_apidata['beatmapset_id']),
            'status': int(_apidata['approved']),
            'name': '{artist} - {title} [{version}]'.format(**_apidata),
            'md5': _apidata['file_md5']
        }

        glob.db.execute(
            'INSERT INTO maps (id, set_id, status, name, md5) VALUES '
            '(%(id)s, %(set_id)s, %(status)s, %(name)s, %(md5)s)', bmap
        )

    # statuses: 0: failed, 1: passed but not top, 2: passed top
    scores = glob.db.fetchall(
        f'SELECT s.id, s.{scoring}, s.max_combo, '
        's.n300, s.n100, s.n50, s.nmiss, s.nkatu, s.ngeki, '
        's.perfect, s.mods, s.play_time time, u.name, u.id userid '
        f'FROM {table} s '
        'LEFT JOIN users u ON u.id = s.userid '
        'WHERE s.map_md5 = %s AND s.status = 2 '
        f'ORDER BY {scoring} DESC LIMIT 50', [req.args['c']]
    )

    # Syntax
    # int(status)|bool(server_has_osz)|int(bid)|int(bsid)|int(len(scores))
    # int(online_offset)
    # str(map_name)
    # round(float(map_rating), 1)
    # score_id|username|score|combo|n50|n100|n300|nmiss|nkatu|ngeki|bool(perfect)|mods|userid|int(rank)|int(time)|int(server_has_replay)

    # osu api -> osu
    status_to_osu = lambda s: {
        4: 5, # Loved
        3: 4, # qualified
        2: 3, # approved
        1: 2, # ranked
        0: 0, # pending
        -1: -1, # not submitted
        -2: 0 # pending
    }[s]

    res.append('|'.join(str(i) for i in (
        status_to_osu(bmap['status']), # ranked status
        'false', # server has osz2
        bmap['id'], # bid
        bmap['set_id'], # bsid
        len(scores)
    )).encode())

    res.extend((
        b'0', # online offset
        bmap['name'].encode(), #mapname
        b'10.0' # map rating
    ))

    res.append(b'') # TOOD: personal best

    if not scores:
        res.append(b'')
        return b'\n'.join(res)

    res.extend(
        b'{id}|{name}|{score}|{max_combo}|'
        b'{n50}|{n100}|{n300}|{nmiss}|{nkatu}|{ngeki}|'
        b'{perfect}|{mods}|{userid}|{rank}|'
        b'{time}|0'.format(rank = idx, **s) # TODO: 0 is has_replay
        for idx, s in enumerate(scores)
    )

    return b'\n'.join(res)

valid_osu_streams = frozenset({
    'cuttingedge', 'stable40', 'beta40', 'stable'
})
@web_handler('check-updates.php')
def checkUpdates(req: Request) -> Optional[bytes]:
    if req.args['action'] != 'check':
        print('Received a request to update with an invalid action.')
        return

    if req.args['stream'] not in valid_osu_streams:
        print('Received a request to update a nonexistant stream?')
        return

    current_time = int(time())

    # If possible, use cached result.
    cache = glob.cache['update'][req.args['stream']]
    if cache['timeout'] > current_time:
        return cache['result']

    if not (res := req_get(
        'https://old.ppy.sh/web/check-updates.php?{p}'.format(
            p = '&'.join(f'{k}={v}' for k, v in req.args.items())
    ))): return

    result = res.text.encode()

    # Overwrite cache
    glob.cache['update'][req.args['stream']] = {
        'result': result,
        'timeout': current_time + 3600
    }

    return result
