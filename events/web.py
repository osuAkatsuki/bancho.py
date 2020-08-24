from typing import Optional, Callable, Final, List
from enum import IntEnum, unique
from time import time
from os.path import exists
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
async def banchoConnect(req: Request) -> Optional[bytes]:
    if 'v' in req.args:
        # TODO: implement verification..?
        # Long term. For now, just send an empty reply
        # so their client immediately attempts login.
        return b'allez-vous owo'

    # TODO: perhaps handle this..?
    return

""" TODO: beatmap submission system """
#required_params_bmsubmit_upload = frozenset({
#    'u', 'h', 't', 'vv', 'z', 's'
#})
#@web_handler('osu-osz2-bmsubmit-upload.php')
#async def osuMapBMSubmitUpload(req: Request) -> Optional[bytes]:
#    if not all(x in req.args for x in required_params_bmsubmit_upload):
#        printlog(f'bmsubmit-upload req missing params.', Ansi.LIGHT_RED)
#        return
#
#    if not 'osz2' in req.files:
#        printlog(f'bmsubmit-upload sent without an osz2.', Ansi.LIGHT_RED)
#        return
#
#    ...
#
#required_params_bmsubmit_getid = frozenset({
#    'h', 's', 'b', 'z', 'vv'
#})
#@web_handler('osu-osz2-bmsubmit-getid.php')
#async def osuMapBMSubmitGetID(req: Request) -> Optional[bytes]:
#    if not all(x in req.args for x in required_params_bmsubmit_getid):
#        printlog(f'bmsubmit-getid req missing params.', Ansi.LIGHT_RED)
#        return
#
#    return b'6\nDN'
#

required_params_screemshot = frozenset({
    'u', 'p', 'v'
})
@web_handler('osu-screenshot.php')
async def osuScreenshot(req: Request) -> Optional[bytes]:
    if not all(x in req.args for x in required_params_screemshot):
        printlog(f'screenshot req missing params.', Ansi.LIGHT_RED)
        return

    if 'ss' not in req.files:
        printlog(f'screenshot req missing file.', Ansi.LIGHT_RED)
        return
    username = unquote(req.args['u'])
    pass_md5 = req.args['p']

    if not (p := await glob.players.get_login(username, pass_md5)):
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
async def lastFM(req: Request) -> Optional[bytes]:
    if not all(x in req.args for x in required_params_lastFM):
        printlog(f'lastfm req missing params.', Ansi.LIGHT_RED)
        return
    username = unquote(req.args['us'])
    pass_md5 = req.args['ha']

    if not (p := await glob.players.get_login(username, pass_md5)):
        return

    if not req.args['b'].startswith('a') \
    or not req.args['b'][1:].isnumeric():
        return # Non-anticheat related.

    flags = ClientFlags(int(req.args['b'][1:]))

    if flags & (ClientFlags.HQAssembly | ClientFlags.HQFile):
        # Player is currently running hq!osu; could possibly
        # be a separate client, buuuut prooobably not lol.

        await p.restrict()
        return

    if flags & ClientFlags.RegistryEdits:
        # Player has registry edits left from
        # hq!osu's multiaccounting tool. This
        # does not necessarily mean they are
        # using it now, but they have in the past.

        if randrange(32) == 0:
            # Random chance (1/32) for a restriction.
            await p.restrict()
            return

        p.enqueue(await packets.notification('\n'.join([
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
async def osuSearchHandler(req: Request) -> Optional[bytes]:
    if not all(x in req.args for x in required_params_osuSearch):
        printlog(f'osu-search req missing params.', Ansi.LIGHT_RED)
        return

    username = unquote(req.args['u'])
    pass_md5 = req.args['h']

    if not (p := await glob.players.get_login(username, pass_md5)):
        return

    if not req.args['p'].isnumeric():
        return

    query = req.args['q'].replace('+', ' ') # TODO: allow empty
    offset = int(req.args['p']) * 100

    # Get all set data.
    if not (res := await glob.db.fetchall(
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
        if not (bmaps := await glob.db.fetchall(
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

# TODO: required params
@web_handler('osu-search-set.php')
async def osuSearchSetHandler(req: Request) -> Optional[bytes]:
    # Since we only need set-specific data, we can basically
    # just do same same query with either bid or bsid.
    if 's' in req.args:
        k, v = ('set_id', req.args['s'])
    elif 'b' in req.args:
        k, v = ('id', req.args['b'])
    else:
        return b''

    # Get all set data.
    bmapset = await glob.db.fetch(
        'SELECT DISTINCT set_id, artist, '
        'title, status, creator, last_update '
        f'FROM maps WHERE {k} = %s', [v]
    )

    if not bmapset:
        # TODO: get from osu!
        return b''

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
    (UNDEF, UNDEF)  # rx!catch
)
del UNDEF

required_params_submitModular = frozenset({
    'x', 'ft', 'score', 'fs', 'bmk', 'iv',
    'c1', 'st', 'pass', 'osuver', 's'
})
@web_handler('osu-submit-modular-selector.php')
async def submitModularSelector(req: Request) -> Optional[bytes]:
    if not all(x in req.args for x in required_params_submitModular):
        printlog(f'submit-modular-selector req missing params.', Ansi.LIGHT_RED)
        return b'error: no'

    # Parse our score data into a score obj.
    s: Score = await Score.from_submission(
        req.args['score'], req.args['iv'],
        req.args['osuver'], req.args['pass']
    )

    if not s:
        printlog('Failed to parse a score - invalid format.', Ansi.LIGHT_RED)
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
    res = await glob.db.fetch(
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

    gm = GameMode(s.game_mode + (4 if s.mods & Mods.RELAX and s.game_mode != 3 else 0))

    if not s.player.priv & Privileges.Whitelisted:
        # Get the PP cap for the current context.
        pp_cap = autorestrict_pp[gm][s.mods & Mods.FLASHLIGHT != 0]

        if s.pp > pp_cap:
            printlog(f'{s.player} restricted for submitting {s.pp:.2f} score on gm {s.game_mode}.', Ansi.LIGHT_RED)
            await s.player.restrict()
            return b'error: ban'

    if s.status == SubmissionStatus.BEST:
        # Our score is our best score.
        # Update any preexisting personal best
        # records with SubmissionStatus.SUBMITTED.
        await glob.db.execute(
            f'UPDATE {table} SET status = 1 '
            'WHERE status = 2 and map_md5 = %s '
            'AND userid = %s', [s.bmap.md5, s.player.id])

    s.id = await glob.db.execute(
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
            await s.player.restrict()
        else:
            # Save our replay
            with open(f'replays/{s.id}.osr', 'wb') as f:
                f.write(req.files['score'])

    if not (time_elapsed := req.args['st' if s.passed else 'ft']).isnumeric():
        return

    s.time_elapsed = int(time_elapsed) / 1000

    # Get the user's stats for current mode.
    stats = s.player.stats[gm]

    stats.playtime += s.time_elapsed
    stats.tscore += s.score
    if s.bmap.status in {RankedStatus.Ranked, RankedStatus.Approved}:
        stats.rscore += s.score

    await glob.db.execute(
        'UPDATE stats SET rscore_{0:sql} = %s, '
        'tscore_{0:sql} = %s, playtime_{0:sql} = %s '
        'WHERE id = %s'.format(gm), [
            stats.rscore, stats.tscore,
            stats.playtime, s.player.id
        ]
    )

    if s.status == SubmissionStatus.BEST and s.rank == 1:
        # Announce the user's #1 score.
        # XXX: Could perhaps add old #1 to the msg?
        # but it would require an extra query ://///
        if announce_chan := glob.channels.get('#announce'):
            await announce_chan.send(glob.bot, f'{s.player.embed} achieved #1 on {s.bmap.embed}.')

    # Update the user.
    s.player.recent_scores[gm] = s
    await s.player.update_stats(gm)

    printlog(f'{s.player} submitted a score! ({s.status})', Ansi.LIGHT_GREEN)
    return b'well done bro'

required_params_getReplay = frozenset({
    'c', 'm', 'u', 'h'
})
@web_handler('osu-getreplay.php')
async def getReplay(req: Request) -> Optional[bytes]:
    if not all(x in req.args for x in required_params_getReplay):
        printlog(f'get-scores req missing params.', Ansi.LIGHT_RED)
        return

    username = unquote(req.args['u'])
    pass_md5 = req.args['h']

    if not (p := await glob.players.get_login(username, pass_md5)):
        return

    path = f"replays/{req.args['c']}.osr"
    if not exists(path):
        return b''

    with open(path, 'rb') as f:
        data = f.read()

    return data

_map_regex = re_comp(r'^(?P<artist>.+) - (?P<title>.+) \((?P<creator>.+)\) \[(?P<version>.+)\]\.osu$')
required_params_getScores = frozenset({
    's', 'vv', 'v', 'c',
    'f', 'm', 'i', 'mods',
    'h', 'a', 'us', 'ha'
})
@web_handler('osu-osz2-getscores.php')
async def getScores(req: Request) -> Optional[bytes]:
    if not all(x in req.args for x in required_params_getScores):
        printlog(f'get-scores req missing params.', Ansi.LIGHT_RED)
        return

    username = unquote(req.args['us'])
    pass_md5 = req.args['ha']

    if not (p := await glob.players.get_login(username, pass_md5)):
        return

    if len(req.args['c']) != 32 or not req.args['mods'].isnumeric():
        return b'-1|false'

    mods = int(req.args['mods'])

    res: List[bytes] = []

    if mods & Mods.RELAX:
        table = 'scores_rx'
        scoring = 'pp'
    else:
        table = 'scores_vn'
        scoring = 'score'

    if not (bmap := await Beatmap.from_md5(req.args['c'])):
        # Couldn't find in db or at osu! api by md5.
        # Check if we have the map in our db (by filename).

        filename = req.args['f'].replace('+', ' ')
        if not (re := _map_regex.match(unquote(filename))):
            printlog(f'Requested invalid file - {filename}.', Ansi.LIGHT_RED)
            return

        set_exists = await glob.db.fetch(
            'SELECT 1 FROM maps WHERE '
            'artist = %s AND title = %s '
            'AND creator = %s AND version = %s', [
                re['artist'], re['title'],
                re['creator'], re['version']
            ]
        )

        return f'{1 if set_exists else -1}|false'.encode()

    if bmap.status < 2:
        # Only show leaderboards for ranked,
        # approved, qualified, or loved maps.
        return f'{int(bmap.status)}|false'.encode()

    # statuses: 0: failed, 1: passed but not top, 2: passed top
    scores = await glob.db.fetchall(
        f'SELECT s.id, s.{scoring} AS _score, s.max_combo, '
        's.n50, s.n100, s.n300, s.nmiss, s.nkatu, s.ngeki, '
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
    res.append(f'{int(bmap.status)}|false|{bmap.id}|{bmap.set_id}|{len(scores) if scores else 0}'.encode())

    # offset, name, rating
    res.append(f'0\n{bmap.full}\n10.0'.encode())

    if not scores:
        # Simply return an empty set.
        return b'\n'.join(res + [b'', b''])

    score_fmt = ('{id}|{name}|{score}|{max_combo}|'
                 '{n50}|{n100}|{n300}|{nmiss}|{nkatu}|{ngeki}|'
                 '{perfect}|{mods}|{userid}|{rank}|{time}|{has_replay}')

    p_best = await glob.db.fetch(
        f'SELECT id, {scoring} AS _score, max_combo, '
        'n50, n100, n300, nmiss, nkatu, ngeki, '
        f'perfect, mods, play_time time FROM {table} '
        'WHERE map_md5 = %s AND game_mode = %s '
        'AND userid = %s AND status = 2 '
        'ORDER BY _score DESC LIMIT 1', [
            req.args['c'], req.args['m'], p.id
        ]
    )

    if p_best:
        # Calculate the rank of the score.
        p_best_rank = (await glob.db.fetch(
            f'SELECT COUNT(*) AS count FROM {table} '
            'WHERE map_md5 = %s AND game_mode = %s '
            f'AND status = 2 AND {scoring} > %s', [
                req.args['c'], req.args['m'],
                p_best['_score']
            ]
        ))['count']

        res.append(
            score_fmt.format(
                **p_best,
                name = p.name, userid = p.id,
                score = int(p_best['_score']),
                has_replay = '1', rank = p_best_rank + 1
            ).encode()
        )
    else:
        res.append(b'')

    res.extend(
        score_fmt.format(
            **s, score = int(s['_score']),
            has_replay = '1', rank = idx + 1
        ).encode() for idx, s in enumerate(scores)
    )

    return b'\n'.join(res)

_valid_actions = frozenset({'check', 'path'})
_valid_streams = frozenset({'cuttingedge', 'stable40',
                            'beta40', 'stable'})
@web_handler('check-updates.php')
async def checkUpdates(req: Request) -> Optional[bytes]:
    if (action := req.args['action']) not in _valid_actions:
        return b'Invalid action.'

    if (stream := req.args['stream']) not in _valid_streams:
        return b'Invalid stream.'

    cache = glob.cache['update'][stream]
    current_time = int(time())

    if cache[action] and cache['timeout'] > current_time:
        return cache[action]

    url = 'https://old.ppy.sh/web/check-updates.php'
    async with glob.http.get(url, params = req.args) as resp:
        if not resp or resp.status != 200:
            return b'Failed to retrieve data from osu!'

        result = await resp.read()

    # Update the cached result.
    cache[action] = result
    cache['timeout'] = current_time + 3600

    return result

async def updateBeatmap(req: Request) -> Optional[bytes]:
    # XXX: This currently works in updating the map, but
    # seems to get the checksum something like that wrong?
    # Will have to look into it :P
    if not (re := _map_regex.match(unquote(req.uri[10:]))):
        printlog(f'Requested invalid map update {req.uri}.', Ansi.LIGHT_RED)
        return b''

    if not (res := await glob.db.fetch(
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
        async with glob.http.get(f"https://old.ppy.sh/osu/{res['id']}") as resp:
            if not resp or resp.status != 200:
                printlog(f'Could not find map {filepath}!', Ansi.LIGHT_RED)
                return

            content = await resp.read()

        with open(filepath, 'wb+') as f:
            f.write(content)

    return content
