# -*- coding: utf-8 -*-

from typing import Optional, Callable
from enum import IntEnum, unique
import os
import time
import copy
import random
import orjson
import asyncio
import aiofiles
from cmyui import AsyncConnection, rstring
from urllib.parse import unquote

import packets
from constants.mods import Mods
from constants.clientflags import ClientFlags
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
        glob.web_map |= {uri: callback}
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
    if not all(x in conn.multipart_args for x in required_params_screemshot):
        await plog(f'screenshot req missing params.', Ansi.LIGHT_RED)
        return

    if 'ss' not in conn.files:
        await plog(f'screenshot req missing file.', Ansi.LIGHT_RED)
        return

    pname = unquote(conn.multipart_args['u'])
    phash = conn.multipart_args['p']

    if not (p := await glob.players.get_login(pname, phash)):
        return

    filename = f'{rstring(8)}.png'

    async with aiofiles.open(f'.data/ss/{filename}', 'wb') as f:
        await f.write(conn.files['ss'])

    await plog(f'{p} uploaded {filename}.')
    return filename.encode()

required_params_osuGetFriends = frozenset({
    'u', 'h'
})
@web_handler('osu-getfriends.php')
async def osuGetFriends(conn: AsyncConnection) -> Optional[bytes]:
    if not all(x in conn.args for x in required_params_osuGetFriends):
        await plog(f'getfriends req missing params.', Ansi.LIGHT_RED)
        return

    pname = unquote(conn.args['u'])
    phash = conn.args['h']

    if not (p := await glob.players.get_login(pname, phash)):
        return

    return '\n'.join(str(i) for i in p.friends).encode()

required_params_osuGetBeatmapInfo = frozenset({
    'u', 'h'
})
@web_handler('osu-getbeatmapinfo.php')
async def osuGetBeatmapInfo(conn: AsyncConnection) -> Optional[bytes]:
    if not all(x in conn.args for x in required_params_osuGetBeatmapInfo):
        await plog(f'getmapinfo req missing params.', Ansi.LIGHT_RED)
        return

    pname = unquote(conn.args['u'])
    phash = conn.args['h']

    if not (p := await glob.players.get_login(pname, phash)):
        return

    data = orjson.loads(conn.body)
    ret = []

    to_osuapi_status = lambda s: {
        0: 0,
        2: 1,
        3: 2,
        4: 3,
        5: 4
    }[s]

    for idx, fname in enumerate(data['Filenames']):
        # Attempt to regex pattern match the filename.
        # If there is no match, simply ignore this map.
        # XXX: Sometimes a map will be requested without a
        # diff name, not really sure how to handle this? lol
        if not (r := regexes.mapfile.match(fname)):
            continue

        # try getting the map from sql
        res = await glob.db.fetch(
            'SELECT id, set_id, status, md5 '
            'FROM maps WHERE artist = %s AND '
            'title = %s AND creator = %s AND '
            'version = %s', [
                r['artist'], r['title'],
                r['creator'], r['version']
            ]
        )

        if not res:
            # no map found
            continue

        # convert from gulag -> osu!api status
        res['status'] = to_osuapi_status(res['status'])

        # try to get the user's grades on the map osu!
        # only allows us to send back one per gamemode,
        # so we'll just send back relax for the time being..
        # XXX: perhaps user-customizable in the future?
        ranks = ['N', 'N', 'N', 'N']

        async for score in glob.db.iterall(
            'SELECT grade, mode FROM scores_rx '
            'WHERE map_md5 = %s AND userid = %s '
            'AND status = 2',
            [res['md5'], p.id]
        ): ranks[score['mode']] = score['grade']

        ret.append('{i}|{id}|{set_id}|{md5}|{status}|{ranks}'.format(
            i = idx, ranks = '|'.join(ranks), **res
        ))

    for bid in data['Ids']:
        breakpoint()

    return '\n'.join(ret).encode()

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

    url = f'{glob.config.mirror}/api/search'
    params = {
        'amount': 100,
        'offset': conn.args['p'],
        'query': conn.args['q']
    }

    if conn.args['m'] != '-1':
        params |= {'mode': conn.args['m']}

    if conn.args['r'] != '4': # 4 = all
        # convert to osu!api status
        status = RankedStatus.from_osudirect(int(conn.args['r']))
        params |= {'status': status.osu_api}

    async with glob.http.get(url, params = params) as resp:
        if not resp or resp.status != 200:
            return b'Failed to retrieve data from mirror!'

        result = await resp.json()

    lresult = len(result) # send over 100 if we receive
                          # 100 matches, so the client
                          # knows there are more to get
    ret = [f"{'101' if lresult == 100 else lresult}"]
    diff_rating = lambda map: map['DifficultyRating']

    for bmap in result:
        diffs = ','.join(
            '[{DifficultyRating:.2f}⭐] {DiffName} '
            '{{CS{CS} OD{OD} AR{AR} HP{HP}}}@{Mode}'.format(**row)
            for row in sorted(bmap['ChildrenBeatmaps'], key = diff_rating)
        )

        ret.append(
            '{SetID}.osz|{Artist}|{Title}|{Creator}|'
            '{RankedStatus}|10.0|{LastUpdate}|{SetID}|' # TODO: rating
            '0|0|0|0|0|{diffs}'.format(**bmap, diffs=diffs)
        ) # 0s are threadid, has_vid, has_story, filesize, filesize_novid

    return '\n'.join(ret).encode()

    """ XXX: some work on gulag's possible future mirror
    query = conn.args['q'].replace('+', ' ') # TODO: allow empty
    offset = int(conn.args['p']) * 100

    sql_query = [
        'SELECT DISTINCT set_id, artist, title,',
        'status, creator, last_update FROM maps',
        'LIMIT %s, 100'
    ]

    sql_params = [offset]

    # TODO: actually support the buttons lol
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
    """

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
    s = await Score.from_submission(
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

    rx = s.mods & Mods.RELAX != 0
    table = 'scores_rx' if rx else 'scores_vn'

    # Check for score duplicates
    # TODO: might need to improve?
    res = await glob.db.fetch(
        f'SELECT 1 FROM {table} WHERE mode = %s '
        'AND map_md5 = %s AND userid = %s AND mods = %s '
        'AND score = %s', [s.mode % 4, s.bmap.md5,
                           s.player.id, int(s.mods), s.score]
    )

    if res:
        await plog(f'{s.player} submitted a duplicate score.', Ansi.LIGHT_YELLOW)
        return b'error: no'

    time_elapsed = mp_args['st' if s.passed else 'ft']

    if not time_elapsed.isdecimal():
        return

    s.time_elapsed = int(time_elapsed)

    if 'i' in conn.files:
        breakpoint()

    if not s.player.priv & Privileges.Whitelisted:
        # Get the PP cap for the current context.
        pp_cap = autorestrict_pp[s.mode][s.mods & Mods.FLASHLIGHT != 0]

        if s.pp > pp_cap:
            await plog(f'{s.player} restricted for submitting '
                       f'{s.pp:.2f} score on gm {s.mode!r}.',
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
            'AND userid = %s AND mode = %s',
            [s.bmap.md5, s.player.id, s.mode % 4]
        )

    s.id = await glob.db.execute(
        f'INSERT INTO {table} VALUES (NULL, '
        '%s, %s, %s, %s, %s, %s, '
        '%s, %s, %s, %s, %s, %s, '
        '%s, %s, %s, %s, '
        '%s, %s, %s, %s'
        ')', [
            s.bmap.md5, s.score, s.pp, s.acc, s.max_combo, int(s.mods),
            s.n300, s.n100, s.n50, s.nmiss, s.ngeki, s.nkatu,
            s.grade, int(s.status), s.mode % 4, s.play_time,
            s.time_elapsed, s.client_flags, s.player.id, s.perfect
        ]
    )

    if s.status != SubmissionStatus.FAILED:
        # All submitted plays should have a replay.
        # If not, they may be using a score submitter.
        if 'score' not in conn.files or conn.files['score'] == b'\r\n':
            await plog(f'{s.player} submitted a score without a replay!', Ansi.LIGHT_RED)
            await s.player.restrict()
        else:
            # TODO: the replay is currently sent from the osu!
            # client compressed with LZMA; this compression can
            # be improved pretty decently by serializing it
            # manually, so we'll probably do that in the future.
            async with aiofiles.open(f'.data/osr/{s.id}.osr', 'wb') as f:
                await f.write(conn.files['score'])

    """ Update the user's & beatmap's stats """

    # get the current stats, and take a
    # shallow copy for the response charts.
    stats = s.player.stats[s.mode]
    prev_stats = copy.copy(stats)

    # update playtime & plays
    stats.playtime += s.time_elapsed / 1000
    stats.plays += 1

    s.bmap.plays += 1
    if s.passed:
        s.bmap.passes += 1

    # update max combo
    if s.max_combo > stats.max_combo:
        stats.max_combo = s.max_combo

    # update total score
    stats.tscore += s.score

    # if this is our (new) best play on
    # the map, update our ranked score.
    if s.status == SubmissionStatus.BEST \
    and s.bmap.status in (RankedStatus.Ranked,
                          RankedStatus.Approved):
        # add our new ranked score.
        stats.rscore += s.score

        if s.prev_best:
            # we previously had a score, so remove
            # it's score from our ranked score.
            stats.rscore -= s.prev_best.score

    # update user with new stats
    await glob.db.execute(
        'UPDATE stats SET rscore_{0:sql} = %s, '
        'tscore_{0:sql} = %s, playtime_{0:sql} = %s, '
        'plays_{0:sql} = %s, maxcombo_{0:sql} = %s '
        'WHERE id = %s'.format(s.mode), [
            stats.rscore, stats.tscore,
            stats.playtime, stats.plays,
            stats.max_combo, s.player.id
        ]
    )

    # update beatmap with new stats
    await glob.db.execute(
        'UPDATE maps SET plays = %s, '
        'passes = %s WHERE md5 = %s',
        [s.bmap.plays, s.bmap.passes, s.bmap.md5]
    )

    if s.status == SubmissionStatus.BEST and s.rank == 1 \
    and (announce_chan := glob.channels['#announce']):
        # Announce the user's #1 score.
        prev_n1 = await glob.db.fetch(
            'SELECT u.id, name FROM users u '
            f'LEFT JOIN {table} s ON u.id = s.userid '
            'WHERE s.map_md5 = %s AND s.mode = %s '
            'AND s.status = 2 ORDER BY pp DESC LIMIT 1, 1',
            [s.bmap.md5, s.mode % 4]
        )

        ann = [f'[{s.mode!r}] {s.player.embed} achieved #1 on {s.bmap.embed}.']

        if prev_n1: # If there was previously a score on the map, add old #1.
            ann.append('(Previously: [https://osu.ppy.sh/u/{id} {name}])'.format(**prev_n1))

        await announce_chan.send(glob.bot, ' '.join(ann))

    # Update the user.
    s.player.recent_scores[s.mode] = s
    await s.player.update_stats(s.mode)

    """ score submission charts """

    if s.status == SubmissionStatus.FAILED or rx:
        # basically, the osu! client and the way bancho handles this
        # is dumb. if you submit a failed play on bancho, it will
        # still generate the charts and send it to the client, even
        # when the client can't (and doesn't use them).. so instead,
        # we'll send back an empty error, which will just tell the
        # client that the score submission process is complete.. lol
        # (also no point on rx since you can't see the charts atm xd)
        ret = b'error: no'

    else:
        # XXX: really not a fan of how this is done atm,
        # but it's kinda just something that's probably
        # going to be ugly no matter what i do lol :v
        charts = []

        # generate beatmap info chart (#1)
        charts.append(
            f'beatmapId:{s.bmap.id}|'
            f'beatmapSetId:{s.bmap.set_id}|'
            f'beatmapPlaycount:{s.bmap.plays}|'
            f'beatmapPasscount:{s.bmap.passes}|'
            f'approvedDate:{s.bmap.last_update}'
        )

        # generate beatmap ranking chart (#2)
        beatmap_chart = [
            'chartId:beatmap',
            f'chartUrl:https://akatsuki.pw/b/{s.bmap.id}',
            'chartName:Beatmap Ranking'
        ]

        if s.prev_best:
            # we had a score on the map before
            beatmap_chart.append(
                f'rankBefore:{s.prev_best.rank}|rankAfter:{s.rank}|'
                f'rankedScoreBefore:{s.prev_best.score}|rankedScoreAfter:{s.score}|'
                f'totalScoreBefore:{s.prev_best.score}|totalScoreAfter:{s.score}|'
                f'maxComboBefore:{s.prev_best.max_combo}|maxComboAfter:{s.max_combo}|'
                f'accuracyBefore:{s.prev_best.acc:.2f}|accuracyAfter:{s.acc:.2f}|'
                f'ppBefore:{s.prev_best.pp:.4f}|ppAfter:{s.pp:.4f}|'
                f'onlineScoreId:{s.id}'
            )

        else:
            # this is our first score on the map
            beatmap_chart.append(
                f'rankBefore:|rankAfter:{s.rank}|'
                f'rankedScoreBefore:|rankedScoreAfter:{s.score}|' # these are
                f'totalScoreBefore:|totalScoreAfter:{s.score}|' # prolly wrong
                f'maxComboBefore:|maxComboAfter:{s.max_combo}|'
                f'accuracyBefore:|accuracyAfter:{s.acc:.2f}|'
                f'ppBefore:|ppAfter:{s.pp:.4f}|'
                f'onlineScoreId:{s.id}'
            )

        charts.append('|'.join(beatmap_chart))

        # generate overall ranking chart (#3)
        overall_chart = [
            'chartId:overall',
            f'chartUrl:https://akatsuki.pw/u/{s.player.id}',
            'chartName:Overall Ranking'
        ]

        # TODO: achievements before onlineScoreId
        # f'achievements-new:taiko-skill-pass-2+Katsu Katsu Katsu+Hora! Ikuzo!/taiko-skill-fc-2+To Your Own Beat+Straight and steady.|'

        if prev_stats:
            overall_chart.append(
                f'rankBefore:{prev_stats.rank}|rankAfter:{stats.rank}|'
                f'rankedScoreBefore:{prev_stats.rscore}|rankedScoreAfter:{stats.rscore}|'
                f'totalScoreBefore:{prev_stats.tscore}|totalScoreAfter:{stats.tscore}|'
                f'maxComboBefore:{prev_stats.max_combo}|maxComboAfter:{stats.max_combo}|'
                f'accuracyBefore:{prev_stats.acc:.2f}|accuracyAfter:{stats.acc:.2f}|'
                f'ppBefore:{prev_stats.pp:.4f}|ppAfter:{stats.pp:.4f}|'
                f'onlineScoreId:{s.id}'
            )

        else:
            overall_chart.append(
                f'rankBefore:|rankAfter:{stats.rank}|'
                f'rankedScoreBefore:|rankedScoreAfter:{stats.rscore}|'
                f'totalScoreBefore:|totalScoreAfter:{stats.tscore}|'
                f'maxComboBefore:|maxComboAfter:{stats.max_combo}|'
                f'accuracyBefore:|accuracyAfter:{stats.acc:.2f}|'
                f'ppBefore:|ppAfter:{stats.pp:.4f}|'
                f'onlineScoreId:{s.id}'
            )

        charts.append('|'.join(overall_chart))

        ret = '\n'.join(charts).encode()

    await plog(f'{s.player} submitted a score! ({s.mode!r}, {s.status!r})', Ansi.LIGHT_GREEN)
    return ret

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
        path = f".data/osr/{conn.args['c']}.osr"
        if not os.path.exists(path):
            return b''

        async with aiofiles.open(path, 'rb') as f:
            return await f.read()

required_params_osuSession = frozenset({
    'u', 'h', 'action'
})
@web_handler('osu-session.php')
async def osuSession(conn: AsyncConnection) -> Optional[bytes]:
    mp_args = conn.multipart_args

    if not all(x in mp_args for x in required_params_osuSession):
        await plog(f'osu-rate req missing params.', Ansi.LIGHT_RED)
        return

    if mp_args['action'] not in ('check', 'submit'):
        return # invalid action

    pname = unquote(mp_args['u'])
    phash = mp_args['h']

    if not (p := await glob.players.get_login(pname, phash)):
        return

    if mp_args['action'] == 'submit':
        # client is submitting a performance session after a score
        # we'll save some basic information, and do some basic checks,
        # could surely be useful for anticheat and debugging purposes.
        data = orjson.loads(mp_args['content'])

        if data['Tags']['Replay'] == 'True':
            # the user was viewing a replay,
            # no need to save to sql.
            return

        # so, osu! sends a 'Fullscreen' param and a 'Beatmap'
        # param, but both of them are the fullscreen value? lol

        op_sys = data['Tags']['OS']
        fullscreen = data['Tags']['Fullscreen'] == 'True'
        fps_cap = data['Tags']['FrameSync']
        compatibility = data['Tags']['Compatibility'] == 'True'
        version = data['Tags']['Version'] # osu! version
        start_time = data['StartTime']
        end_time = data['EndTime']
        frame_count = data['ProcessedFrameCount']
        spike_frames = data['SpikeFrameCount']

        aim_rate = data['AimFrameRate']
        if aim_rate == 'Infinity':
            aim_rate = 0

        completion = data['Completion']
        identifier = data['Identifier']
        average_frametime = data['AverageFrameTime'] * 1000

        if identifier:
            breakpoint()

        # chances are, if we can't find a very
        # recent score by a user, it just hasn't
        # submitted yet.. we'll allow 5 seconds

        rscore: Optional[Score] = None
        retries = 0
        ctime = time.time()

        cache = glob.cache['performance_reports']

        while retries < 5:
            if (rscore := p.recent_score) and rscore.id not in cache:
                # only accept scores submitted
                # within the last 5 seconds.

                if ((ctime + retries) - (rscore.play_time - 5)) > 0:
                    break

            retries += 1
            await asyncio.sleep(1)
        else:
            # STILL no score found..
            # this can happen if they submit a duplicate score,
            # perhaps i should add some kind of system to prevent
            # this from happening or re-think this overall.. i'd
            # imagine this can be useful for old client det. tho :o
            await plog('Received performance report but found no score', Ansi.LIGHT_RED)
            return

        # TODO: timing checks

        if version != p.osu_version:
            breakpoint()

        # remember that we've already received a report
        # for this score, so that we don't overwrite it.
        glob.cache['performance_reports'].add(rscore.id)

        await glob.db.execute(
            'INSERT INTO performance_reports VALUES '
            '(%s, %s, %s, %s, %s, %s, %s,'
            ' %s, %s, %s, %s, %s, %s, %s)', [
                rscore.id,
                op_sys, fullscreen, fps_cap,
                compatibility, version,
                start_time, end_time,
                frame_count, spike_frames,
                aim_rate, completion,
                identifier, average_frametime
            ]
        )

    else:
        # TODO: figure out what this wants?
        # seems like it adds the response from server
        # to some kind of internal buffer, dunno why tho
        return

required_params_osuRate = frozenset({
    'u', 'p', 'c'
})
@web_handler('osu-rate.php')
async def osuRate(conn: AsyncConnection) -> Optional[bytes]:
    if not all(x in conn.args for x in required_params_osuRate):
        await plog(f'osu-rate req missing params.', Ansi.LIGHT_RED)
        return

    pname = unquote(conn.args['u'])
    phash = conn.args['p']

    if not (p := await glob.players.get_login(pname, phash)):
        return b'auth fail'

    map_md5 = conn.args['c']

    if 'v' not in conn.args:
        # check if we have the map in our cache;
        # if not, the map probably doesn't exist.
        if map_md5 not in glob.cache['beatmap']:
            return b'no exist'

        cached = glob.cache['beatmap'][map_md5]['map']

        # only allow rating on maps with a leaderboard.
        if cached.status < RankedStatus.Ranked:
            return b'not ranked'

        # osu! client is checking whether we can rate the map or not.
        alreadyvoted = await glob.db.fetch(
            'SELECT 1 FROM ratings WHERE '
            'map_md5 = %s AND userid = %s',
            [map_md5, p.id]
        )

        # the client hasn't rated the map, so simply
        # tell them that they can submit a rating.
        if not alreadyvoted:
            return b'ok'
    else:
        # the client is submitting a rating for the map.
        if not (rating := conn.args['v']).isdecimal():
            return

        await glob.db.execute(
            'INSERT INTO ratings '
            'VALUES (%s, %s, %s)',
            [p.id, map_md5, int(rating)]
        )

    ratings = [x[0] for x in await glob.db.fetchall(
        'SELECT rating FROM ratings '
        'WHERE map_md5 = %s',
        [map_md5], _dict = False
    )]

    # send back the average rating
    avg = sum(ratings) / len(ratings)
    return f'alreadyvoted\n{avg}'.encode()

@unique
class RankingType(IntEnum):
    Local   = 0
    Top     = 1
    Mods    = 2
    Friends = 3
    Country = 4

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

    if not conn.args['mods'].isdecimal() \
    or not conn.args['v'].isdecimal():
        return b'-1|false'

    mods = int(conn.args['mods'])

    # update rx value and send their stats if changed
    # XXX: this doesn't work consistently, but i'll
    # keep it in anyways i suppose lol.. no harm :D
    rx = mods & Mods.RELAX > 0
    if p.rx != rx:
        p.rx = rx
        glob.players.enqueue(await packets.userStats(p))

    rank_type = RankingType(int(conn.args['v']))

    res: list[bytes] = []

    if rx:
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
    query = [
        f'SELECT s.id, s.{scoring} AS _score, s.max_combo, '
        's.n50, s.n100, s.n300, s.nmiss, s.nkatu, s.ngeki, '
        's.perfect, s.mods, s.play_time time, u.name, u.id userid '
        f'FROM {table} s LEFT JOIN users u ON u.id = s.userid '
        'WHERE s.map_md5 = %s AND s.status = 2 AND mode = %s'
    ]

    params = [conn.args['c'], conn.args['m']]

    if rank_type == RankingType.Mods:
        query.append('AND s.mods = %s')
        params.append(mods)
    elif rank_type == RankingType.Friends:
        query.append( # kinda ugly doe
            'AND s.userid IN ((SELECT user2 FROM friendships '
            'WHERE user1 = {0}), {0})'.format(p.id)
        )
    elif rank_type == RankingType.Country:
        query.append('AND u.country = %s')
        params.append(p.country[1]) # letters, not id

    query.append(f'ORDER BY _score DESC LIMIT 50')

    scores = await glob.db.fetchall(' '.join(query), params)

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
        'WHERE map_md5 = %s AND mode = %s '
        'AND userid = %s AND status = 2 '
        'ORDER BY _score DESC LIMIT 1', [
            conn.args['c'], conn.args['m'], p.id
        ]
    )

    if p_best:
        # Calculate the rank of the score.
        p_best_rank = 1 + (await glob.db.fetch(
            f'SELECT COUNT(*) AS count FROM {table} '
            'WHERE map_md5 = %s AND mode = %s '
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

_valid_actions = frozenset({'check', 'path', 'error'})
_valid_streams = frozenset({'cuttingedge', 'stable40',
                            'beta40', 'stable'})
@web_handler('check-updates.php')
async def checkUpdates(conn: AsyncConnection) -> Optional[bytes]:
    if (action := conn.args['action']) not in _valid_actions:
        return b'Invalid action.'

    if (stream := conn.args['stream']) not in _valid_streams:
        return b'Invalid stream.'

    if action == 'error':
        # client is just reporting an error updating
        return b''

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

    if os.path.exists(filepath := f".data/osu/{res['id']}.osu"):
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
