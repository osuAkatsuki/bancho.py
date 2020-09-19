# -*- coding: utf-8 -*-

from typing import Optional, Callable, Final, List
from enum import IntEnum, unique
import os
import time
import random
import aiofiles
from cmyui import AsyncConnection, rstring
from urllib.parse import unquote

import packets
from constants.mods import Mods
from constants.clientflags import ClientFlags
from constants.gamemodes import GameMode
from constants import regexes
from objects.score import Score, SubmissionStatus
from objects.player import Privileges
from objects.beatmap import Beatmap, RankedStatus
from objects import glob
from console import plog, Ansi

# For /web/ requests, we send the
# data directly back in the event.

# TODO:
# osu-rate.php: beatmap rating on score submission.
# osu-osz2-bmsubmit-upload.php: beatmap submission upload
# osu-osz2-bmsubmit-getid.php: beatmap submission getinfo

glob.web_map = {}

def web_handler(uri: str) -> Callable:
    def register_callback(callback: Callable) -> Callable:
        glob.web_map.update({uri: callback})
        return callback
    return register_callback

@web_handler('bancho_connect.php')
async def banchoConnect(conn: AsyncConnection) -> Optional[bytes]:
    if 'v' in conn.args:
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
#async def osuMapBMSubmitUpload(conn: AsyncConnection) -> Optional[bytes]:
#    if not all(x in conn.args for x in required_params_bmsubmit_upload):
#        await plog(f'bmsubmit-upload req missing params.', Ansi.LIGHT_RED)
#        return
#
#    if not 'osz2' in conn.files:
#        await plog(f'bmsubmit-upload sent without an osz2.', Ansi.LIGHT_RED)
#        return
#
#    ...
#
#required_params_bmsubmit_getid = frozenset({
#    'h', 's', 'b', 'z', 'vv'
#})
#@web_handler('osu-osz2-bmsubmit-getid.php')
#async def osuMapBMSubmitGetID(conn: AsyncConnection) -> Optional[bytes]:
#    if not all(x in conn.args for x in required_params_bmsubmit_getid):
#        await plog(f'bmsubmit-getid req missing params.', Ansi.LIGHT_RED)
#        return
#
#    return b'6\nDN'

required_params_screemshot = frozenset({
    'u', 'p', 'v'
})
@web_handler('osu-screenshot.php')
async def osuScreenshot(conn: AsyncConnection) -> Optional[bytes]:
    if not all(x in conn.args for x in required_params_screemshot):
        await plog(f'screenshot req missing params.', Ansi.LIGHT_RED)
        return

    if 'ss' not in conn.files:
        await plog(f'screenshot req missing file.', Ansi.LIGHT_RED)
        return

    pname = unquote(conn.args['u'])
    phash = conn.args['p']

    if not (p := await glob.players.get_login(pname, phash)):
        return

    filename = f'{rstring(8)}.png'

    async with aiofiles.open(f'screenshots/{filename}', 'wb') as f:
        await f.write(conn.files['ss'])

    await plog(f'{p} uploaded {filename}.')
    return filename.encode()

required_params_lastFM = frozenset({
    'b', 'action', 'us', 'ha'
})
@web_handler('lastfm.php')
async def lastFM(conn: AsyncConnection) -> Optional[bytes]:
    if not all(x in conn.args for x in required_params_lastFM):
        await plog(f'lastfm req missing params.', Ansi.LIGHT_RED)
        return

    pname = unquote(conn.args['us'])
    phash = conn.args['ha']

    if not (p := await glob.players.get_login(pname, phash)):
        return

    if conn.args['b'][0] != 'a':
        # not anticheat related
        return

    flags = ClientFlags(int(conn.args['b'][1:]))

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

        if random.randrange(32) == 0:
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
async def osuSearchHandler(conn: AsyncConnection) -> Optional[bytes]:
    if not all(x in conn.args for x in required_params_osuSearch):
        await plog(f'osu-search req missing params.', Ansi.LIGHT_RED)
        return

    pname = unquote(conn.args['u'])
    phash = conn.args['h']

    if not (p := await glob.players.get_login(pname, phash)):
        return

    if not conn.args['p'].isdecimal():
        return

    query = conn.args['q'].replace('+', ' ') # TODO: allow empty
    offset = int(conn.args['p']) * 100

    sql_query: List[str] = [
        'SELECT DISTINCT set_id, artist, title,',
        'status, creator, last_update FROM maps',
        'LIMIT %s, 100'
    ]

    sql_params = [offset]

    if query not in ('Newest', 'Top Rated', 'Most Played'):
        # They're searching something specifically.
        sql_query.insert(2, 'WHERE title LIKE %s')
        sql_params.insert(0, f'%{query}%')

    if not (res := await glob.db.fetchall(' '.join(sql_query), sql_params)):
        return b'-1\nNo matches found.'

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
async def osuSearchSetHandler(conn: AsyncConnection) -> Optional[bytes]:
    # Since we only need set-specific data, we can basically
    # just do same same query with either bid or bsid.
    if 's' in conn.args:
        k, v = ('set_id', conn.args['s'])
    elif 'b' in conn.args:
        k, v = ('id', conn.args['b'])
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
async def submitModularSelector(conn: AsyncConnection) -> Optional[bytes]:
    mp_args = conn.multipart_args

    if not all(x in mp_args for x in required_params_submitModular):
        await plog(f'submit-modular-selector req missing params.', Ansi.LIGHT_RED)
        return b'error: no'

    # Parse our score data into a score obj.
    s: Score = await Score.from_submission(
        mp_args['score'], mp_args['iv'],
        mp_args['osuver'], mp_args['pass']
    )

    if not s:
        await plog('Failed to parse a score - invalid format.', Ansi.LIGHT_RED)
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
        await plog(f'{s.player} submitted a duplicate score.', Ansi.LIGHT_YELLOW)
        return b'error: no'

    if conn.args['i']:
        breakpoint()

    gm = GameMode(s.game_mode + (4 if s.mods & Mods.RELAX and s.game_mode != 3 else 0))

    if not s.player.priv & Privileges.Whitelisted:
        # Get the PP cap for the current context.
        pp_cap = autorestrict_pp[gm][s.mods & Mods.FLASHLIGHT != 0]

        if s.pp > pp_cap:
            await plog(f'{s.player} restricted for submitting '
                       f'{s.pp:.2f} score on gm {s.game_mode}.',
                       Ansi.LIGHT_RED)

            await s.player.restrict()
            return b'error: ban'

    if s.status == SubmissionStatus.BEST:
        # Our score is our best score.
        # Update any preexisting personal best
        # records with SubmissionStatus.SUBMITTED.
        await glob.db.execute(
            f'UPDATE {table} SET status = 1 '
            'WHERE status = 2 AND map_md5 = %s '
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
        if 'score' not in conn.files or conn.files['score'] == b'\r\n':
            await plog(f'{s.player} submitted a score without a replay!', Ansi.LIGHT_RED)
            await s.player.restrict()
        else:
            # Save our replay
            async with aiofiles.open(f'replays/{s.id}.osr', 'wb') as f:
                await f.write(conn.files['score'])

    time_elapsed = mp_args['st' if s.passed else 'ft']

    if not time_elapsed.isdecimal():
        return

    s.time_elapsed = int(time_elapsed) / 1000

    # Get the user's stats for current mode.
    stats = s.player.stats[gm]

    stats.playtime += s.time_elapsed
    stats.tscore += s.score
    if s.bmap.status in (RankedStatus.Ranked, RankedStatus.Approved):
        stats.rscore += s.score

    await glob.db.execute(
        'UPDATE stats SET rscore_{0:sql} = %s, '
        'tscore_{0:sql} = %s, playtime_{0:sql} = %s '
        'WHERE id = %s'.format(gm), [
            stats.rscore, stats.tscore,
            stats.playtime, s.player.id
        ]
    )

    if s.status == SubmissionStatus.BEST and s.rank == 1 \
    and (announce_chan := glob.channels.get('#announce')):
        # Announce the user's #1 score.
        prev_n1 = await glob.db.fetch(
            'SELECT u.id, name FROM users u '
            f'LEFT JOIN {table} s ON u.id = s.userid '
            'WHERE s.map_md5 = %s AND game_mode = %s '
            'ORDER BY pp DESC LIMIT 1, 1',
            [s.bmap.md5, s.game_mode]
        )

        ann: List[str] = [f'{s.player.embed} achieved #1 on {s.bmap.embed}.']

        if prev_n1: # If there was previously a score on the map, add old #1.
            ann.append('(Prev: [https://osu.ppy.sh/u/{id} {name}])'.format(**prev_n1))

        await announce_chan.send(glob.bot, ' '.join(ann))

    # Update the user.
    s.player.recent_scores[gm] = s
    await s.player.update_stats(gm)

    await plog(f'{s.player} submitted a score! ({gm!r}, {s.status})', Ansi.LIGHT_GREEN)
    return b'well done bro'

required_params_getReplay = frozenset({
    'c', 'm', 'u', 'h'
})
@web_handler('osu-getreplay.php')
async def getReplay(conn: AsyncConnection) -> Optional[bytes]:
    if not all(x in conn.args for x in required_params_getReplay):
        await plog(f'get-scores req missing params.', Ansi.LIGHT_RED)
        return

    pname = unquote(conn.args['u'])
    phash = conn.args['h']

    if await glob.players.get_login(pname, phash):
        path = f"replays/{conn.args['c']}.osr"
        if not os.path.exists(path):
            return b''

        async with aiofiles.open(path, 'rb') as f:
            content = await f.read()

        return content

required_params_getScores = frozenset({
    's', 'vv', 'v', 'c',
    'f', 'm', 'i', 'mods',
    'h', 'a', 'us', 'ha'
})
@web_handler('osu-osz2-getscores.php')
async def getScores(conn: AsyncConnection) -> Optional[bytes]:
    if not all(x in conn.args for x in required_params_getScores):
        await plog(f'get-scores req missing params.', Ansi.LIGHT_RED)
        return

    pname = unquote(conn.args['us'])
    phash = conn.args['ha']

    if not (p := await glob.players.get_login(pname, phash)):
        return

    if not conn.args['mods'].isdecimal():
        return b'-1|false'

    mods = int(conn.args['mods'])

    res: List[bytes] = []

    if mods & Mods.RELAX:
        table = 'scores_rx'
        scoring = 'pp'
    else:
        table = 'scores_vn'
        scoring = 'score'

    if not (bmap := await Beatmap.from_md5(conn.args['c'], set_id=int(conn.args['i']))):
        # Couldn't find in db or at osu! api by md5.
        # Check if we have the map in our db (by filename).

        filename = conn.args['f'].replace('+', ' ')
        if not (re := regexes.mapfile.match(unquote(filename))):
            await plog(f'Requested invalid file - {filename}.', Ansi.LIGHT_RED)
            return

        set_exists = await glob.db.fetch(
            'SELECT 1 FROM maps WHERE '
            'artist = %s AND title = %s '
            'AND creator = %s AND version = %s', [
                re['artist'], re['title'],
                re['creator'], re['version']
            ]
        )

        if set_exists:
            # Map can be updated.
            return b'1|false'
        else:
            # Map is unsubmitted.
            # Add this map to the unsubmitted cache, so
            # that we don't have to make this request again.
            glob.cache['unsubmitted'].add(conn.args['c'])

        return f'{1 if set_exists else -1}|false'.encode()

    if bmap.status < RankedStatus.Ranked:
        # Only show leaderboards for ranked,
        # approved, qualified, or loved maps.
        return f'{int(bmap.status)}|false'.encode()

    # statuses: 0: failed, 1: passed but not top, 2: passed top
    scores = await glob.db.fetchall(
        f'SELECT s.id, s.{scoring} AS _score, s.max_combo, '
        's.n50, s.n100, s.n300, s.nmiss, s.nkatu, s.ngeki, '
        's.perfect, s.mods, s.play_time time, u.name, u.id userid '
        f'FROM {table} s LEFT JOIN users u ON u.id = s.userid '
        'WHERE s.map_md5 = %s AND s.status = 2 AND game_mode = %s '
        f'ORDER BY _score DESC LIMIT 50', [conn.args['c'], conn.args['m']]
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
            conn.args['c'], conn.args['m'], p.id
        ]
    )

    if p_best:
        # Calculate the rank of the score.
        p_best_rank = 1 + (await glob.db.fetch(
            f'SELECT COUNT(*) AS count FROM {table} '
            'WHERE map_md5 = %s AND game_mode = %s '
            f'AND status = 2 AND {scoring} > %s', [
                conn.args['c'], conn.args['m'],
                p_best['_score']
            ]
        ))['count']

        res.append(
            score_fmt.format(
                **p_best,
                name = p.name, userid = p.id,
                score = int(p_best['_score']),
                has_replay = '1', rank = p_best_rank
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
async def checkUpdates(conn: AsyncConnection) -> Optional[bytes]:
    if (action := conn.args['action']) not in _valid_actions:
        return b'Invalid action.'

    if (stream := conn.args['stream']) not in _valid_streams:
        return b'Invalid stream.'

    cache = glob.cache['update'][stream]
    current_time = int(time.time())

    if cache[action] and cache['timeout'] > current_time:
        return cache[action]

    url = 'https://old.ppy.sh/web/check-updates.php'
    async with glob.http.get(url, params = conn.args) as resp:
        if not resp or resp.status != 200:
            return b'Failed to retrieve data from osu!'

        result = await resp.read()

    # Update the cached result.
    cache[action] = result
    cache['timeout'] = (glob.config.updates_cache_timeout +
                        current_time)

    return result

async def updateBeatmap(conn: AsyncConnection) -> Optional[bytes]:
    if not (re := regexes.mapfile.match(unquote(conn.path[10:]))):
        await plog(f'Requested invalid map update {conn.path}.', Ansi.LIGHT_RED)
        return b''

    if not (res := await glob.db.fetch(
        'SELECT id, md5 FROM maps WHERE '
        'artist = %s AND title = %s '
        'AND creator = %s AND version = %s', [
            re['artist'], re['title'],
            re['creator'], re['version']
        ]
    )): return b'' # no map found

    if os.path.exists(filepath := f"pp/maps/{res['id']}.osu"):
        # Map found on disk.

        async with aiofiles.open(filepath, 'rb') as f:
            content = await f.read()
    else:
        # We don't have map, get from osu!
        async with glob.http.get(f"https://old.ppy.sh/osu/{res['id']}") as resp:
            if not resp or resp.status != 200:
                await plog(f'Could not find map {filepath}!', Ansi.LIGHT_RED)
                return

            content = await resp.read()

        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(content)

    return content
