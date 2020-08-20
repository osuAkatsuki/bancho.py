from typing import Optional, Callable, Final, List
from enum import IntEnum, unique
from time import time
from os.path import exists
from requests import get as req_get
from random import randrange
from cmyui.utils import rstring
from urllib.parse import unquote
from re import compile as re_comp

import packets
from constants.mods import Mods
from constants.clientflags import ClientFlags
from constants.gamemodes import GameMode
from objects.score import Score, SubmissionStatus
from objects.player import Privileges
from objects.beatmap import Beatmap, RankedStatus
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
def banchoConnect(req: Request) -> Optional[bytes]:
    if 'v' in req.args:
        # TODO: implement verification..?
        # Long term. For now, just send an empty reply
        # so their client immediately attempts login.
        return b'allez-vous owo'

    # TODO: perhaps handle this..?
    return

required_params_screemshot = frozenset({
    'u', 'p', 'v'
})
@web_handler('osu-screenshot.php')
def osuScreenshot(req: Request) -> Optional[bytes]:
    if not all(x in req.args for x in required_params_screemshot):
        printlog(f'screenshot req missing params.')
        return

    if 'ss' not in req.files:
        printlog(f'screenshot req missing file.')
        return

    if not (p := glob.players.get_from_cred(req.args['u'], req.args['p'])):
        return

    filename = f'{rstring(8)}.png'

    with open(f'screenshots/{filename}', 'wb+') as f:
        f.write(req.files['ss'])

    printlog(f'{p} uploaded {filename}.')
    return filename.encode()

required_params_lastFM = frozenset({
    'b', 'action', 'us', 'ha'
})
@web_handler('lastfm.php')
def lastFM(req: Request) -> Optional[bytes]:
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

@unique
class DirectDisplaySetting(IntEnum):
    Ranked = 0
    Pending = 2
    Qualified = 3
    All = 4
    Graveyard = 5
    RankedPlayed = 7
    Loved = 8

ranked_from_direct = {
    DirectDisplaySetting.Ranked: RankedStatus.Ranked,
    DirectDisplaySetting.Pending: RankedStatus.Pending,
    DirectDisplaySetting.Qualified: RankedStatus.Qualified,
    DirectDisplaySetting.Graveyard: RankedStatus.Pending,
    DirectDisplaySetting.RankedPlayed: RankedStatus.Ranked, # TODO
    DirectDisplaySetting.Loved: RankedStatus.Loved
}
required_params_osuSearch = frozenset({
    'u', 'h', 'r', 'q', 'm', 'p'
})
@web_handler('osu-search.php')
def osuSearchHandler(req: Request) -> Optional[bytes]:
    if not all(x in req.args for x in required_params_osuSearch):
        printlog(f'osu-search req missing params.')
        return

    if not (p := glob.players.get_from_cred(req.args['u'], req.args['h'])):
        return

    if not req.args['p'].isnumeric():
        return

    query = req.args['q'].replace('+', ' ') # TODO: allow empty
    offset = int(req.args['p']) * 100

    # Get all set data.
    if not (res := glob.db.fetchall(
        'SELECT DISTINCT set_id, artist, '
        'title, status, creator, last_update '
        'FROM maps WHERE title LIKE %s '
        'LIMIT %s, 100', # paginate through sql lol
        [f"%{query}%", offset]
    )): return b'-1\nNo matches found.'

    # We'll construct the response as a list of
    # strings, then join and encode when returning.
    ret = [f'{len(res)}']

    # For each beatmap set
    for bmapset in res:
        # retrieve the data for each difficulty
        if not (bmaps := glob.db.fetchall(
            # Remove ',' from diffname since it's our split char.
            "SELECT REPLACE(version, ',', '') AS version, "
            'mode, cs, od, ar, hp, diff '
            'FROM maps WHERE set_id = %s '
            # Order difficulties by mode > star rating > ar.
            'ORDER BY mode ASC, diff ASC, ar ASC',
            [bmapset['set_id']]
        )): continue

        # Construct difficulty-specific information.
        diffs = ','.join(
            '[{diff:.2f}⭐] {version} {{CS{cs} OD{od} AR{ar} HP{hp}}}@{mode}'.format(**row)
            for row in bmaps
        )

        ret.append(
            '{set_id}.osz|{artist}|{title}|{creator}|'
            '{status}|10.0|{last_update}|{set_id}|' # TODO: rating
            '0|0|0|0|0|{diffs}'.format(**bmapset, diffs=diffs)
        ) # 0s are threadid, has_vid, has_story, filesize, filesize_novid

    return '\n'.join(ret).encode()

@web_handler('osu-search-set.php')
def osuSearchSetHandler(req: Request) -> Optional[bytes]:
    # Since we only need set-specific data, we can basically
    # just do same same query with either bid or bsid.
    if 's' in req.args:
        k, v = ('set_id', req.args['s'])
    elif 'b' in req.args:
        k, v = ('id', req.args['b'])
    else:
        return b''

    # Get all set data.
    # XXX: order by anything?
    if not (bmapset := glob.db.fetch(
        'SELECT DISTINCT set_id, artist, '
        'title, status, creator, last_update '
        f'FROM maps WHERE {k} = %s', [v]
    )): return b''

    # TODO: rating
    return ('{set_id}.osz|{artist}|{title}|{creator}|'
            '{status}|10.0|{last_update}|{set_id}|'
            '0|0|0|0|0').format(**bmapset).encode()
    # 0s are threadid, has_vid, has_story, filesize, filesize_novid

@unique
class RankingType(IntEnum):
    Local:   Final[int] = 0
    Top:     Final[int] = 1
    Mods:    Final[int] = 2
    Friends: Final[int] = 3
    Country: Final[int] = 4

UNDEF = 9999
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
    elif not s.bmap:
        # Map does not exist, most likely unsubmitted.
        return b'error: no'
    elif s.bmap.status == RankedStatus.Pending:
        # XXX: Perhaps will accept in the future,
        return b'error: no' # not now though.

    table = 'scores_rx' if s.mods & Mods.RELAX else 'scores_vn'

    # Check for score duplicates
    # TODO: might need to improve?
    res = glob.db.fetch(
        f'SELECT 1 FROM {table} WHERE game_mode = %s '
        'AND map_md5 = %s AND userid = %s AND mods = %s '
        'AND score = %s', [s.game_mode, s.bmap.md5,
                           s.player.id, s.mods, s.score]
    )

    if res:
        printlog(f'{s.player} submitted a duplicate score.', Ansi.LIGHT_YELLOW)
        return b'error: no'

    if req.args['i']:
        breakpoint()

    gm = GameMode(s.game_mode + (4 if s.player.rx and s.game_mode != 3 else 0))

    if not s.player.priv & Privileges.Whitelisted:
        # Get the PP cap for the current context.
        pp_cap = autorestrict_pp[gm][s.mods & Mods.FLASHLIGHT != 0]

        if s.pp > pp_cap:
            printlog(f'{s.player} restricted for submitting {s.pp:.2f} score on gm {s.game_mode}.', Ansi.LIGHT_RED)
            s.player.restrict()
            return b'error: ban'

    if s.status == SubmissionStatus.BEST:
        # Our score is our best score.
        # Update any preexisting personal best
        # records with SubmissionStatus.SUBMITTED.
        glob.db.execute(
            f'UPDATE {table} SET status = 1 '
            'WHERE status = 2 and map_md5 = %s '
            'AND userid = %s', [s.bmap.md5, s.player.id])

    s.id = glob.db.execute(
        f'INSERT INTO {table} VALUES (NULL, '
        '%s, %s, %s, %s, %s, %s, '
        '%s, %s, %s, %s, %s, %s, '
        '%s, %s, %s, '
        '%s, %s, %s'
        ')', [
            s.bmap.md5, s.score, s.pp, s.acc, s.max_combo, s.mods,
            s.n300, s.n100, s.n50, s.nmiss, s.ngeki, s.nkatu,
            int(s.status), s.game_mode, s.play_time,
            s.client_flags, s.player.id, s.perfect
        ]
    )

    if s.status != SubmissionStatus.FAILED:
        # All submitted plays should have a replay.
        # If not, they may be using a score submitter.
        if 'score' not in req.files or req.files['score'] == b'\r\n':
            printlog(f'{s.player} submitted a score without a replay!', Ansi.LIGHT_RED)
            s.player.restrict()
        else:
            # Save our replay
            with open(f'replays/{s.id}.osr', 'wb') as f:
                f.write(req.files['score'])

    s.player.stats[gm].tscore += s.score
    if s.bmap.status in {RankedStatus.Ranked, RankedStatus.Approved}:
        s.player.stats[gm].rscore += s.score

    glob.db.execute(
        'UPDATE stats SET rscore_{0:sql} = %s, '
        'tscore_{0:sql} = %s WHERE id = %s'.format(gm), [
            s.player.stats[gm].rscore,
            s.player.stats[gm].tscore,
            s.player.id
        ]
    )

    if s.status == SubmissionStatus.BEST and s.rank == 1:
        # Announce the user's #1 score.
        if announce_chan := glob.channels.get('#announce'):
            announce_chan.send(glob.bot, f'{s.player.embed} achieved #1 on {s.bmap.embed}.')

    # Update the user.
    s.player.recent_scores[gm] = s
    s.player.update_stats(gm)

    printlog(f'{s.player} submitted a score! ({s.status})', Ansi.LIGHT_GREEN)
    return b'well done bro'

required_params_getReplay = frozenset({
    'c', 'm', 'u', 'h'
})
@web_handler('osu-getreplay.php')
def getReplay(req: Request) -> Optional[bytes]:
    if not all(x in req.args for x in required_params_getReplay):
        printlog(f'get-scores req missing params.')
        return

    path = f"replays/{req.args['c']}.osr"
    if not exists(path):
        return b''

    with open(path, 'rb') as f:
        data = f.read()

    return data

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

    if not (bmap := Beatmap.from_md5(req.args['c'])):
        # Couldn't find in db or at osu! api.
        # The beatmap must not be submitted.
        return b'-1|false'

    if bmap.status < 2:
        # Only show leaderboards for ranked,
        # approved, qualified, or loved maps.
        return f'{int(bmap.status)}|false'.encode()

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

    # ranked status, serv has osz2, bid, bsid, len(scores)
    res.append(f'{int(bmap.status)}|false|{bmap.id}|{bmap.set_id}|{len(scores)}'.encode())

    # offset, name, rating
    res.append(f'0\n{bmap.full}\n10.0'.encode())

    # TODO: personal best
    res.append(b'')

    if not scores:
        # Simply return an empty set.
        return b'\n'.join(res + [b''])

    res.extend(
        '{id}|{name}|{score}|{max_combo}|'
        '{n50}|{n100}|{n300}|{nmiss}|{nkatu}|{ngeki}|'
        '{perfect}|{mods}|{userid}|{rank}|{time}|{has_replay}'.format(
            **s, score = int(s['_score']), has_replay = '1', rank = idx
        ).encode() for idx, s in enumerate(scores)
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

_map_regex = re_comp(r'^(?P<artist>.+) - (?P<title>.+) \((?P<creator>.+)\) \[(?P<version>.+)\]\.osu$')
def updateBeatmap(req: Request) -> Optional[bytes]:
    # XXX: This currently works in updating the map, but
    # seems to get the checksum something like that wrong?
    # Will have to look into it :P
    if not (re := _map_regex.match(unquote(req.uri[10:]))):
        printlog(f'Requested invalid map update {req.uri}.', Ansi.RED)
        return b''

    if not (res := glob.db.fetch(
        'SELECT id, md5 FROM maps WHERE '
        'artist = %s AND title = %s '
        'AND creator = %s AND version = %s', [
            re['artist'], re['title'],
            re['creator'], re['version']
        ]
    )): return b'' # no map found

    if exists(filepath := f"pp/maps/{res['id']}.osu"):
        # Map found on disk.
        with open(filepath, 'rb') as f:
            content = f.read()
    else:
        # We don't have map, get from osu!
        if not (r := req_get(f"https://old.ppy.sh/osu/{res['id']}")):
            raise Exception(f'Could not find map {filepath}!')

        content = r.content

        with open(filepath, 'wb+') as f:
            f.write(content)

    return content
