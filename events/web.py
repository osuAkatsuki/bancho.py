from typing import Dict, Tuple, Optional
from enum import IntEnum, unique
from time import time
from requests import get as req_get

from constants.mods import Mods
from objects import glob
from objects.web import Request
from console import printlog

Headers = Tuple[str]
GET_Params = Dict[str, str]

# For /web/ requests, we send the
# data directly back in the event.

@unique
class RankingType(IntEnum):
    Local = 0
    Top = 1
    Mods = 2
    Friends = 3
    Country = 4

# URI: /osu-osz2-getscores.php
required_params_getScores = (
    's', 'vv', 'v', 'c',
    'f', 'm', 'i', 'mods',
    'h', 'a', 'us', 'ha'
)
#def getScores(headers: Headers, params: GET_Params) -> Optional[bytes]:
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
        if not (r := req_get(f"https://old.ppy.sh/api/get_beatmaps?k={glob.config.osu_api_key}&h={req.args['c']}")):
            return # TODO: conv ranked status from api to osu format

        if r.text == '[]':
            return # no api data TODO: return unsubmitted

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

    res.append('|'.join(str(i) for i in [
        status_to_osu(bmap['status']), # ranked status
        'false', # server has osz2
        bmap['id'], # bid
        bmap['set_id'], # bsid
        len(scores)
    ]).encode())

    res.append(b'0') # offset
    res.append(bmap['name'].encode())
    res.append(b'10.0') # map rating
    res.append(b'') # TODO personal best

    if scores:
        res.extend( # destroys pep8 but i think this is most readable.
            b'{id}|{name}|{score}|{max_combo}|{n50}|{n100}|{n300}|{nmiss}|{nkatu}|{ngeki}|{perfect}|{mods}|{userid}|{rank}|{time}|{has_replay}'.format(
                rank = idx, has_replay = '0', **s
            ) for idx, s in enumerate(scores)
        )
    else:
        res.append(b'')

    return b'\n'.join(res)

# URI: /check-updates.php
#def checkUpdates(headers: Headers, params: GET_Params) -> Optional[bytes]:
def checkUpdates(req: Request) -> Optional[bytes]:
    if req.args['action'] != 'check':
        print(f'Received a request to update with an invalid action.')
        return

    if req.args['stream'] not in {'cuttingedge', 'stable40', 'beta40', 'stable'}:
        print('Received a request to update a nonexistant stream?')
        return

    current_time = int(time())

    # If possible, use cached result (lasts 1 hour).
    cache = glob.cache['update'][req.args['stream']]
    if cache['timeout'] > current_time:
        return cache['result']

    if not (res := req_get(
        'https://old.ppy.sh/web/check-updates.php?{params}'.format(
            params = '&'.join(f'{k}={v}' for k, v in req.args.items())
        )
    )): return

    result = res.text.encode()

    # Overwrite cache
    glob.cache['update'][req.args['stream']] = {
        'result': result,
        'timeout': current_time + 3600
    }

    return result
