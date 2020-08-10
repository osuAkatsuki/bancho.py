from typing import Optional, Callable, Final
from enum import IntEnum, unique
from time import time
from requests import get as req_get
from random import randrange

import packets
from constants.mods import Mods
from constants.clientflags import ClientFlags
from objects.score import Score, SubmissionStatus
from objects.player import Player, Privileges
from objects import glob
from cmyui.web import Request
from console import printlog, Ansi

# For /web/ requests, we send the
# data directly back in the event.

# TODO:
# osu-rate.php: Beatmap rating on score submission.
glob.web_map = {}

def web_handler(uri: str) -> Callable:
    def register_callback(callback: Callable) -> Callable:
        glob.web_map.update({uri: callback})
        return callback
    return register_callback

@web_handler('bancho_connect.php')
def banchoConnectHandler(req: Request) -> Optional[bytes]:
    if 'v' in req.args:
        # TODO: implement verification..?
        # Long term. For now, just send an empty reply
        # so their client immediately attempts login.
        return b'allez-vous owo'

    # TODO: perhaps handle this..?
    return

required_params_lastFM = frozenset({
    'b', 'action', 'us', 'ha'
})
@web_handler('lastfm.php')
def lastFMHandler(req: Request) -> Optional[bytes]:
    if not all(x in req.args for x in required_params_lastFM):
        printlog(f'lastfm req missing params.')
        return

    if not (p := glob.players.get_from_cred(req.args['us'], req.args['ha'])):
        return

    if not req.args['b'].startswith('a') \
    or not req.args['b'][1:].isnumeric():
        return # Non-anticheat related.

    flags = ClientFlags(int(req.args['b'][1:]))

    if flags & (ClientFlags.HQAssembly | ClientFlags.HQFile):
        # Player is currently running hq!osu; could possibly
        # be a separate client, buuuut prooobably not lol.

        p.restrict()
        return

    if flags & ClientFlags.RegistryEdits:
        # Player has registry edits left from
        # hq!osu's multiaccounting tool. This
        # does not necessarily mean they are
        # using it now, but they have in the past.

        if randrange(32) == 0:
            # Random chance (1/32) for a restriction.
            p.restrict()
            return

        p.enqueue(packets.notification('\n'.join([
            "Hey!",
            "It appears you have hq!osu's multiaccounting tool (relife) enabled.",
            "This tool leaves a change in your registry that the osu! client can detect.",
            "Please re-install relife and disable the program to avoid possible restriction."
        ])))
        return

    """ These checks only worked for ~5 hours from release. rumoi's quick!
    if flags & (ClientFlags.libeay32Library | ClientFlags.aqnMenuSample):
        # AQN has been detected in the client, either
        # through the 'libeay32.dll' library being found
        # onboard, or from the menu sound being played in
        # the AQN menu while being in an inappropriate menu
        # for the context of the sound effect.
        pass
    """

@web_handler('osu-search.php')
def osuSearchHandler(req: Request) -> Optional[bytes]:
    # u: username
    # h: password md5
    # r: ranked option selection
    # q: querystring
    # m: gamemode
    # p: page
    if not (p := glob.players.get_from_cred(req.args['u'], req.args['h'])):
        return

    p.enqueue(packets.notification('Hey! osu!direct is not currently working.'))
    print(req.args['r'])

@unique
class RankingType(IntEnum):
    Local:   Final[int] = 0
    Top:     Final[int] = 1
    Mods:    Final[int] = 2
    Friends: Final[int] = 3
    Country: Final[int] = 4

UNDEF = (1 << 31) - 1
autorestrict_pp = (
    # Values for autorestriction. This is the simplest
    # form of "anticheat", simply ban a user if they are not
    # whitelisted, and submit a score of too high caliber.
    # Values below are in form (non_fl, fl), as fl has custom
    # vals as it finds quite a few additional cheaters on the side.
    (700, 600),     # vn!std
    (UNDEF, UNDEF), # vn!taiko
    (UNDEF, UNDEF), # vn!catch
    (UNDEF, UNDEF), # vn!mania

    (1500, 1000),   # rx!std
    (UNDEF, UNDEF), # rx!taiko
    (UNDEF, UNDEF), # rx!catch
    (UNDEF, UNDEF)  # rx!mania
)
del UNDEF

required_params_submitModular = frozenset({
    'x', 'ft', 'score', 'fs', 'bmk', 'iv',
    'c1', 'st', 'pass', 'osuver', 's'
})
@web_handler('osu-submit-modular-selector.php')
def submitModularSelector(req: Request) -> Optional[bytes]:
    if not all(x in req.args for x in required_params_submitModular):
        printlog(f'submit-modular-selector req missing params.')
        return b'error: no'

    # TODO: make some kind of beatmap object.
    # We currently don't check the map's ranked status.

    # Parse our score data into a score obj.
    s: Score = Score.from_submission(
        req.args['score'], req.args['iv'],
        req.args['osuver'], req.args['pass']
    )

    if not s:
        printlog('Failed to parse a score - invalid format.', Ansi.YELLOW)
        return b'error: no'
    elif not s.player:
        # Player is not online, return nothing so that their
        # client will retry submission when they log in.
        return

    if s.game_mode in {2, 3}: # catch, mania
        s.player.enqueue(packets.notification(
            'Score submission only available for std/taiko.'))
        return b'error: no'

    table = 'scores_rx' if s.mods & Mods.RELAX else 'scores_vn'

    # Check for score duplicates
    # TODO: might need to improve?
    res = glob.db.fetch(
        f'SELECT 1 FROM {table} WHERE game_mode = %s '
        'AND map_md5 = %s AND userid = %s AND mods = %s '
        'AND score = %s', [s.game_mode, s.map_md5,
                           s.player.id, s.mods, s.score]
    )

    if res:
        printlog(f'{s.player} submitted a duplicate score.', Ansi.LIGHT_YELLOW)
        return b'error: no'

    if req.args['i']:
        breakpoint()

    if not s.player.priv & Privileges.Whitelisted:
        # Get the PP cap for the current context.
        gm_adjusted = s.game_mode + (4 if s.player.rx and s.game_mode != 3 else 0)
        pp_cap = autorestrict_pp[gm_adjusted][s.mods & Mods.FLASHLIGHT != 0]

        if s.pp > pp_cap:
            printlog(f'{p} restricted for submitting {s.pp} score on gm {s.game_mode}.', Ansi.LIGHT_RED)
            s.player.restrict()
            return b'error: ban'

    if s.status == SubmissionStatus.BEST:
        # Our score is our best score.
        # Update any preexisting personal best
        # records with SubmissionStatus.SUBMITTED.
        glob.db.execute(
            f'UPDATE {table} SET status = 1 '
            'WHERE status = 2 and map_md5 = %s '
            'AND userid = %s', [s.map_md5, s.player.id])

    glob.db.execute(
        f'INSERT INTO {table} VALUES (NULL, '
        '%s, %s, %s, %s, %s, %s, '
        '%s, %s, %s, %s, %s, %s, '
        '%s, %s, %s, '
        '%s, %s, %s'
        ')', [
            s.map_md5, s.score, s.pp, s.acc, s.max_combo, s.mods,
            s.n300, s.n100, s.n50, s.nmiss, s.ngeki, s.nkatu,
            int(s.status), s.game_mode, s.play_time,
            s.client_flags, s.player.id, s.perfect
        ]
    )

    if s.status == SubmissionStatus.BEST and s.rank == 1:
        # Announce the user's #1 score.
        if announce_chan := glob.channels.get('#announce'):
            announce_chan.send(glob.bot, f'{s.player.embed} achieved #1 on {s.map_id}.')

    # Update the user.
    s.player.recent_scores[s.player.status.game_mode] = s
    s.player.update_stats(s.game_mode)

    printlog(f'{s.player} submitted a score! ({s.status})', Ansi.LIGHT_GREEN)
    return b'well done bro'

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

    # Tbh, I don't really care if people request
    # leaderboards from other peoples accounts, or are
    # not logged out.. At the moment, there are no checks
    # that could put anyone's account in danger :P.
    # XXX: could be a ddos problem? lol

    if len(req.args['c']) != 32 \
    or not req.args['mods'].isnumeric():
        return b'-1|false'

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
            return b'-1|false'

        if r.text == '[]':
            # API returned an empty set.
            # TODO: return unsubmitted status.
            return b'-1|false'

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
        f'SELECT s.id, s.{scoring} AS _score, s.max_combo, '
        's.n300, s.n100, s.n50, s.nmiss, s.nkatu, s.ngeki, '
        's.perfect, s.mods, s.play_time time, u.name, u.id userid '
        f'FROM {table} s LEFT JOIN users u ON u.id = s.userid '
        'WHERE s.map_md5 = %s AND s.status = 2 AND game_mode = %s'
        f'ORDER BY _score DESC LIMIT 50', [req.args['c'], req.args['m']]
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
        # Simply return an empty set.
        return b'\n'.join(res + [b''])

    res.extend('|'.join(str(s) for s in (
        s['id'], s['name'], int(s['_score']), s['max_combo'],
        s['n50'], s['n100'], s['n300'], s['nmiss'], s['nkatu'], s['ngeki'],
        s['perfect'], s['mods'], s['userid'], idx, s['time'], '0')).encode()
        for idx, s in enumerate(scores) # rank ^,   has_replay ^ (TODO)
    )

    return b'\n'.join(res)

valid_osu_streams = frozenset({
    'cuttingedge', 'stable40', 'beta40', 'stable'
})
@web_handler('check-updates.php')
def checkUpdates(req: Request) -> Optional[bytes]:
    if req.args['action'] != 'check':
        # TODO: handle more?
        print('Received a request to update with an invalid action.')
        return

    if req.args['stream'] not in valid_osu_streams:
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
