# -*- coding: utf-8 -*-

from constants.gamemodes import GameMode
from typing import Optional, Callable
from enum import IntEnum, unique
from functools import partial, wraps
import os
import time
import copy
import random
import orjson
import aiofiles

from cmyui import AsyncConnection, rstring, log, Ansi, _isdecimal
from urllib.parse import unquote

import packets
from constants.mods import Mods
from constants.clientflags import ClientFlags
from constants import regexes
from objects.score import Score, SubmissionStatus
from objects.player import Privileges
from objects.beatmap import Beatmap, RankedStatus
from objects import glob

# for /web/ requests, we send the
# data directly back in the event.

# TODO:
# osu-rate.php: beatmap rating on score submission.
# osu-osz2-bmsubmit-upload.php: beatmap submission upload
# osu-osz2-bmsubmit-getid.php: beatmap submission getinfo

glob.web_map = {}

def web_handler(uri: str) -> Callable:
    """Register a handler in `glob.web_map`."""
    def register_cb(cb: Callable) -> Callable:
        glob.web_map |= {uri: cb}
        return cb

    return register_cb

def _required_args(args: set[str], argset: str) -> Callable:
    def wrapper(f: Callable) -> Callable:

        # modify the handler code to ensure that
        # all arguments are sent in the request.
        @wraps(f)
        async def handler(conn: AsyncConnection) -> Optional[bytes]:
            _argset = getattr(conn, argset)
            if all(x in _argset for x in args):
                # all args given, call the
                # handler with the conn.
                return await f(conn)

        return handler
    return wrapper

required_args = partial(_required_args, argset='args')
required_mpargs = partial(_required_args, argset='multipart_args')
required_files = partial(_required_args, argset='files')

def get_login(name_p: str, pass_p: str, auth_error: bytes = b'') -> Callable:
    def wrapper(f: Callable) -> Callable:

        # modify the handler code to get the player
        # object before calling the handler itself.
        @wraps(f)
        async def handler(conn: AsyncConnection) -> Optional[bytes]:
            name = passwd = None

            for argset in (conn.args, conn.multipart_args):
                if name_p in argset and pass_p in argset:
                    name = argset[name_p]
                    passwd = argset[pass_p]

            if not (name and passwd):
                return auth_error

            p = await glob.players.get_login(unquote(name), passwd)

            if not p:
                return auth_error

            return await f(p, conn)

        return handler
    return wrapper

@web_handler('bancho_connect.php')
async def banchoConnect(conn: AsyncConnection) -> Optional[bytes]:
    if 'v' in conn.args:
        # TODO: implement verification..?
        # long term. For now, just send an empty reply
        # so their client immediately attempts login.

        # NOTE: you can actually return an endpoint here
        # for the client to use as a bancho endpoint.
        return b'allez-vous owo'

    # TODO: perhaps handle this..?
    NotImplemented

""" TODO: beatmap submission system
required_params_bmsubmit_upload = frozenset({
    'u', 'h', 't', 'vv', 'z', 's'
})
@web_handler('osu-osz2-bmsubmit-upload.php')
async def osuMapBMSubmitUpload(conn: AsyncConnection) -> Optional[bytes]:
    if not all(x in conn.args for x in required_params_bmsubmit_upload):
        log(f'bmsubmit-upload req missing params.', Ansi.LRED)
        return

    if not 'osz2' in conn.files:
        log(f'bmsubmit-upload sent without an osz2.', Ansi.LRED)
        return

    ...

required_params_bmsubmit_getid = frozenset({
    'h', 's', 'b', 'z', 'vv'
})
@web_handler('osu-osz2-bmsubmit-getid.php')
async def osuMapBMSubmitGetID(conn: AsyncConnection) -> Optional[bytes]:
    if not all(x in conn.args for x in required_params_bmsubmit_getid):
        log(f'bmsubmit-getid req missing params.', Ansi.LRED)
        return

    #s - setid
    #b - beatmapids ',' delim
    #z - hash
    #vv - ver

    pname = unquote(conn.args['u'])
    phash = conn.args['h']

    if not (p := await glob.players.get_login(pname, phash)):
        return

    _ids = conn.args['b'].split(',')

    if not conn.args['s'].isdecimal() \
    or not all(x.isdecimal() for x in _ids):
        return b'-1\nInvalid submission.'

    map_ids = [int(x) for x in _ids]
    set_id = int(conn.args['s'])

    md5_exists = await glob.db.fetch(
        'SELECT 1 FROM maps '
        'WHERE md5 = %s',
        [conn.args['z']]
    ) is not None

    if set_id != -1 or any(map_ids) or md5_exists:
        # TODO: check if they are the creator
        res = await glob.db.fetch(
            'SELECT creator FROM maps '
            'WHERE server = \'gulag\' '
            'AND '
        )

        return b'1' # ownership error

    # get basic info for their new map

    # 1: ownership | 3: alreadyranked

    ...
"""

from objects.player import Player

@web_handler('osu-screenshot.php')
@required_mpargs({'u', 'p', 'v'})
@get_login('u', 'p')
async def osuScreenshot(p: Player, conn: AsyncConnection) -> Optional[bytes]:
    if 'ss' not in conn.files:
        log(f'screenshot req missing file.', Ansi.LRED)
        return

    filename = f'{rstring(8)}.png'

    async with aiofiles.open(f'.data/ss/{filename}', 'wb') as f:
        await f.write(conn.files['ss'])

    log(f'{p} uploaded {filename}.')
    return filename.encode()

@web_handler('osu-getfriends.php')
@required_args({'u', 'h'})
@get_login('u', 'h')
async def osuGetFriends(p: Player, conn: AsyncConnection) -> Optional[bytes]:
    return '\n'.join(str(i) for i in p.friends).encode()

@web_handler('osu-getbeatmapinfo.php')
@required_args({'u', 'h'})
@get_login('u', 'h')
async def osuGetBeatmapInfo(p: Player, conn: AsyncConnection) -> Optional[bytes]:
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

@web_handler('osu-getfavourites.php')
@required_args({'u', 'h'})
@get_login('u', 'h')
async def osuGetFavourites(p: Player, conn: AsyncConnection) -> Optional[bytes]:
    favourites = await glob.db.fetchall(
        'SELECT setid FROM favourites '
        'WHERE userid = %s',
        [p.id]
    )

    return '\n'.join(favourites).encode()

@web_handler('osu-addfavourite.php')
@required_args({'u', 'h', 'a'})
@get_login('u', 'h', b'Please login to add favourites!')
async def osuAddFavourite(p: Player, conn: AsyncConnection) -> Optional[bytes]:
    # make sure set id is valid
    if not conn.args['a'].isdecimal():
        return b'Invalid beatmap set id.'

    # check if they already have this favourited.
    if await glob.db.fetch(
        'SELECT 1 FROM favourites '
        'WHERE userid = %s AND setid = %s',
        [p.id, conn.args['a']]
    ): return b"You've already favourited this beatmap!"

    # add favourite
    await glob.db.execute(
        'INSERT INTO favourites '
        'VALUES (%s, %s)',
        [p.id, conn.args['a']]
    )

@web_handler('lastfm.php')
@required_args({'b', 'action', 'us', 'ha'})
@get_login('us', 'ha')
async def lastFM(p: Player, conn: AsyncConnection) -> Optional[bytes]:
    if conn.args['b'][0] != 'a':
        # not anticheat related, tell the
        # client not to send any more for now.
        return b'-3'

    flags = ClientFlags(int(conn.args['b'][1:]))

    if flags & (ClientFlags.HQAssembly | ClientFlags.HQFile):
        # Player is currently running hq!osu; could possibly
        # be a separate client, buuuut prooobably not lol.

        await p.ban(glob.bot, f'hq!osu running ({flags})')
        return b'-3'

    if flags & ClientFlags.RegistryEdits:
        # Player has registry edits left from
        # hq!osu's multiaccounting tool. This
        # does not necessarily mean they are
        # using it now, but they have in the past.

        if random.randrange(32) == 0:
            # Random chance (1/32) for a ban.
            await p.ban(glob.bot, f'hq!osu relife 1/32')
            return b'-3'

        p.enqueue(await packets.notification('\n'.join([
            "Hey!",
            "It appears you have hq!osu's multiaccounting tool (relife) enabled.",
            "This tool leaves a change in your registry that the osu! client can detect.",
            "Please re-install relife and disable the program to avoid possible ban."
        ])))

        await p.logout()
        return b'-3'

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
@required_args({'u', 'h', 'r', 'q', 'm', 'p'})
@get_login('u', 'h')
async def osuSearchHandler(p: Player, conn: AsyncConnection) -> Optional[bytes]:
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

@web_handler('osu-search-set.php')
@required_args({'u', 'h'})
@get_login('u', 'h')
async def osuSearchSetHandler(p: Player, conn: AsyncConnection) -> Optional[bytes]:
    # Since we only need set-specific data, we can basically
    # just do same same query with either bid or bsid.
    if 's' in conn.args:
        # gulag chat menu: if the argument is negative,
        # check if it's in the players menu options.
        if conn.args['s'][0] == '-':
            opt_id = int(conn.args['s'])

            if opt_id not in p.menu_options:
                return # negative set id, non-menu

            opt = p.menu_options[opt_id]

            if time.time() > opt['timeout']:
                # the option has expired.
                del p.menu_options[opt_id]
                return

            # we have a menu option. activate it.
            await opt['callback']()

            if not opt['reusable']:
                # remove the option from the player
                del p.menu_options[opt_id]

            return
        else:
            # this is just a normal request
            k, v = ('set_id', conn.args['s'])
    elif 'b' in conn.args:
        k, v = ('id', conn.args['b'])
    else:
        return # invalid args

    # Get all set data.
    bmapset = await glob.db.fetch(
        'SELECT DISTINCT set_id, artist, '
        'title, status, creator, last_update '
        f'FROM maps WHERE {k} = %s', [v]
    )

    if not bmapset:
        # TODO: get from osu!
        return

    # TODO: rating
    return ('{set_id}.osz|{artist}|{title}|{creator}|'
            '{status}|10.0|{last_update}|{set_id}|'
            '0|0|0|0|0').format(**bmapset).encode()
    # 0s are threadid, has_vid, has_story, filesize, filesize_novid

UNDEF = 9999
autoban_pp = (
    # high ceiling values for autoban as a very simple form
    #  of "anticheat", simply ban a user if they are not
    # whitelisted, and submit a score of too high caliber.
    # Values below are in form (non_fl, fl), as fl has custom
    # vals as it finds quite a few additional cheaters on the side.
    (700,   600),   # vn!std
    (UNDEF, UNDEF), # vn!taiko
    (UNDEF, UNDEF), # vn!catch
    (UNDEF, UNDEF), # vn!mania

    (1200,  800),   # rx!std
    (UNDEF, UNDEF), # rx!taiko
    (UNDEF, UNDEF), # rx!catch

    (UNDEF, UNDEF)  # ap!std
)
del UNDEF

@web_handler('osu-submit-modular-selector.php')
@required_mpargs({'x', 'ft', 'score', 'fs', 'bmk', 'iv',
                  'c1', 'st', 'pass', 'osuver', 's'})
async def osuSubmitModularSelector(conn: AsyncConnection) -> Optional[bytes]:
    mp_args = conn.multipart_args

    # Parse our score data into a score obj.
    s = await Score.from_submission(
        mp_args['score'], mp_args['iv'],
        mp_args['osuver'], mp_args['pass']
    )

    if not s:
        log('Failed to parse a score - invalid format.', Ansi.LRED)
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

    # attempt to update their stats if their
    # gm/gm-affecting-mods change at all.
    if s.mode != s.player.status.mode:
        s.player.status.mods = s.mods
        s.player.status.mode = s.mode
        glob.players.enqueue(await packets.userStats(s.player))

    table = s.mode.sql_table

    # Check for score duplicates
    # TODO: might need to improve?
    res = await glob.db.fetch(
        f'SELECT 1 FROM {table} WHERE mode = %s '
        'AND map_md5 = %s AND userid = %s AND mods = %s '
        'AND score = %s', [
            s.mode.as_vanilla, s.bmap.md5,
            s.player.id, int(s.mods), s.score
        ]
    )

    if res:
        log(f'{s.player} submitted a duplicate score.', Ansi.LYELLOW)
        return b'error: no'

    time_elapsed = mp_args['st' if s.passed else 'ft']

    if not time_elapsed.isdecimal():
        return

    s.time_elapsed = int(time_elapsed)

    if 'i' in conn.files:
        breakpoint()

    if not s.player.priv & Privileges.Whitelisted:
        # Get the PP cap for the current context.
        pp_cap = autoban_pp[s.mode][s.mods & Mods.FLASHLIGHT != 0]

        if s.pp > pp_cap:
            log(f'{s.player} banned for submitting '
                 f'{s.pp:.2f} score on gm {s.mode!r}.',
                 Ansi.LRED)

            await s.player.ban(glob.bot, f'[{s.mode!r}] autoban @ {s.pp:.2f}')
            return b'error: ban'

    if s.status == SubmissionStatus.BEST:
        # Our score is our best score.
        # Update any preexisting personal best
        # records with SubmissionStatus.SUBMITTED.
        await glob.db.execute(
            f'UPDATE {table} SET status = 1 '
            'WHERE status = 2 AND map_md5 = %s '
            'AND userid = %s AND mode = %s',
            [s.bmap.md5, s.player.id, s.mode.as_vanilla]
        )

    s.id = await glob.db.execute(
        f'INSERT INTO {table} VALUES (NULL, '
        '%s, %s, %s, %s, %s, %s, '
        '%s, %s, %s, %s, %s, %s, '
        '%s, %s, %s, %s, '
        '%s, %s, %s, %s)', [
            s.bmap.md5, s.score, s.pp, s.acc, s.max_combo, int(s.mods),
            s.n300, s.n100, s.n50, s.nmiss, s.ngeki, s.nkatu,
            s.grade, int(s.status), s.mode.as_vanilla, s.play_time,
            s.time_elapsed, s.client_flags, s.player.id, s.perfect
        ]
    )

    if s.status != SubmissionStatus.FAILED:
        # All submitted plays should have a replay.
        # If not, they may be using a score submitter.
        if 'score' not in conn.files or conn.files['score'] == b'\r\n':
            log(f'{s.player} submitted a score without a replay!', Ansi.LRED)
            await s.player.ban(glob.bot, f'submitted score with no replay')
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
    stats = s.player.gm_stats
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
        additive = s.score

        if s.prev_best:
            # we previously had a score, so remove
            # it's score from our ranked score.
            additive -= s.prev_best.score

        stats.rscore += additive

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
            [s.bmap.md5, s.mode.as_vanilla]
        )

        performance = f'{s.pp:.2f}pp' if s.pp else f'{s.score}'

        ann = [f'\x01ACTION achieved #1 on {s.bmap.embed} {s.mods!r} with {s.acc:.2f}% for {performance}.']

        if prev_n1: # If there was previously a score on the map, add old #1.
            ann.append('(Previously: [https://osu.ppy.sh/u/{id} {name}])'.format(**prev_n1))

        await announce_chan.send(s.player, ' '.join(ann), to_client=True)

    # Update the user.
    s.player.recent_scores[s.mode] = s
    await s.player.update_stats(s.mode)

    """ score submission charts """

    if s.status == SubmissionStatus.FAILED or s.mode >= GameMode.rx_std:
        # basically, the osu! client and the way bancho handles this
        # is dumb. if you submit a failed play on bancho, it will
        # still generate the charts and send it to the client, even
        # when the client can't (and doesn't use them).. so instead,
        # we'll send back an empty error, which will just tell the
        # client that the score submission process is complete.. lol
        # (also no point on rx/ap since you can't see the charts atm xd)
        ret = b'error: no'

    else:
        # XXX: really not a fan of how this is done atm,
        # but it's kinda just something that's probably
        # going to be ugly no matter what i do lol :v
        charts = []

        # append beatmap info chart (#1)
        charts.append(
            f'beatmapId:{s.bmap.id}|'
            f'beatmapSetId:{s.bmap.set_id}|'
            f'beatmapPlaycount:{s.bmap.plays}|'
            f'beatmapPasscount:{s.bmap.passes}|'
            f'approvedDate:{s.bmap.last_update}'
        )

        # append beatmap ranking chart (#2)
        charts.append('|'.join((
            'chartId:beatmap',
            f'chartUrl:https://akatsuki.pw/b/{s.bmap.id}',
            'chartName:Beatmap Ranking',

            ( # we had a score on the map prior to this
                f'rankBefore:{s.prev_best.rank}|rankAfter:{s.rank}|'
                f'rankedScoreBefore:{s.prev_best.score}|rankedScoreAfter:{s.score}|'
                f'totalScoreBefore:{s.prev_best.score}|totalScoreAfter:{s.score}|'
                f'maxComboBefore:{s.prev_best.max_combo}|maxComboAfter:{s.max_combo}|'
                f'accuracyBefore:{s.prev_best.acc:.2f}|accuracyAfter:{s.acc:.2f}|'
                f'ppBefore:{s.prev_best.pp:.4f}|ppAfter:{s.pp:.4f}|'
                f'onlineScoreId:{s.id}'
            ) if s.prev_best else ( # we don't, this is our first
                f'rankBefore:|rankAfter:{s.rank}|'
                f'rankedScoreBefore:|rankedScoreAfter:{s.score}|' # these are
                f'totalScoreBefore:|totalScoreAfter:{s.score}|' # prolly wrong
                f'maxComboBefore:|maxComboAfter:{s.max_combo}|'
                f'accuracyBefore:|accuracyAfter:{s.acc:.2f}|'
                f'ppBefore:|ppAfter:{s.pp:.4f}|'
                f'onlineScoreId:{s.id}'
            )
        )))#'|'.join(beatmap_chart))

        # append overall ranking chart (#3)
        charts.append('|'.join((
            'chartId:overall',
            f'chartUrl:https://akatsuki.pw/u/{s.player.id}',
            'chartName:Overall Ranking',

            # TODO: achievements
            ( # we have a score on the account prior to this
                f'rankBefore:{prev_stats.rank}|rankAfter:{stats.rank}|'
                f'rankedScoreBefore:{prev_stats.rscore}|rankedScoreAfter:{stats.rscore}|'
                f'totalScoreBefore:{prev_stats.tscore}|totalScoreAfter:{stats.tscore}|'
                f'maxComboBefore:{prev_stats.max_combo}|maxComboAfter:{stats.max_combo}|'
                f'accuracyBefore:{prev_stats.acc:.2f}|accuracyAfter:{stats.acc:.2f}|'
                f'ppBefore:{prev_stats.pp:.4f}|ppAfter:{stats.pp:.4f}|'
                # f'achievements-new:taiko-skill-pass-2+Katsu Katsu Katsu+Hora! Ikuzo!/taiko-skill-fc-2+To Your Own Beat+Straight and steady.|'
                f'onlineScoreId:{s.id}'
            ) if prev_stats else ( # this is the account's first score
                f'rankBefore:|rankAfter:{stats.rank}|'
                f'rankedScoreBefore:|rankedScoreAfter:{stats.rscore}|'
                f'totalScoreBefore:|totalScoreAfter:{stats.tscore}|'
                f'maxComboBefore:|maxComboAfter:{stats.max_combo}|'
                f'accuracyBefore:|accuracyAfter:{stats.acc:.2f}|'
                f'ppBefore:|ppAfter:{stats.pp:.4f}|'
                # f'achievements-new:taiko-skill-pass-2+Katsu Katsu Katsu+Hora! Ikuzo!/taiko-skill-fc-2+To Your Own Beat+Straight and steady.|'
                f'onlineScoreId:{s.id}'
            )

        )))

        ret = '\n'.join(charts).encode()

    log(f'[{s.mode!r}] {s.player} submitted a score! ({s.status!r})', Ansi.LGREEN)
    return ret

@web_handler('osu-getreplay.php')
@required_args({'u', 'h', 'm', 'c'})
@get_login('u', 'h')
async def getReplay(p: Player, conn: AsyncConnection) -> Optional[bytes]:
    path = f".data/osr/{conn.args['c']}.osr"
    if not os.path.exists(path):
        return

    async with aiofiles.open(path, 'rb') as f:
        return await f.read()

""" XXX: going to be slightly more annoying than expected to set this up :P
@web_handler('osu-session.php')
@required_mpargs({'u', 'h', 'action'})
@get_login('u', 'h')
async def osuSession(p: Player, conn: AsyncConnection) -> Optional[bytes]:
    mp_args = conn.multipart_args

    if mp_args['action'] not in ('check', 'submit'):
        return # invalid action

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
            log('Received performance report but found no score', Ansi.LRED)
            return

        # TODO: timing checks

        #if version != p.osu_ver:
        #    breakpoint()

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
"""

@web_handler('osu-rate.php')
@required_args({'u', 'p', 'c'})
@get_login('u', 'p', b'auth fail')
async def osuRate(conn: AsyncConnection) -> Optional[bytes]:
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

@web_handler('osu-osz2-getscores.php')
@required_args({'s', 'vv', 'v', 'c', 'f', 'm',
                'i', 'mods', 'h', 'a', 'us', 'ha'})
@get_login('us', 'ha')
async def getScores(p: Player, conn: AsyncConnection) -> Optional[bytes]:
    isdecimal_n = partial(_isdecimal, _negative=True)

    # make sure all int args are integral
    if not all(isdecimal_n(conn.args[k]) for k in ('mods', 'v', 'm', 'i')):
        return b'-1|false'

    map_md5 = conn.args['c']

    mods = int(conn.args['mods'])
    mode = GameMode.from_params(int(conn.args['m']), mods)

    map_set_id = int(conn.args['i'])
    rank_type = RankingType(int(conn.args['v']))

    # attempt to update their stats if their
    # gm/gm-affecting-mods change at all.
    if mode != p.status.mode:
        p.status.mods = mods
        p.status.mode = mode
        glob.players.enqueue(await packets.userStats(p))

    table = mode.sql_table
    scoring = 'pp' if mode >= GameMode.rx_std else 'score'

    if not (bmap := await Beatmap.from_md5(map_md5, map_set_id)):
        # couldn't find in db or at osu! api by md5.
        # check if we have the map in our db (by filename).

        filename = conn.args['f'].replace('+', ' ')
        if not (re := regexes.mapfile.match(unquote(filename))):
            log(f'Requested invalid file - {filename}.', Ansi.LRED)
            return

        set_exists = await glob.db.fetch(
            'SELECT 1 FROM maps '
            'WHERE artist = %s AND title = %s '
            'AND creator = %s AND version = %s', [
                re['artist'], re['title'],
                re['creator'], re['version']
            ]
        )

        if set_exists:
            # map can be updated.
            return b'1|false'
        else:
            # map is unsubmitted.
            # add this map to the unsubmitted cache, so
            # that we don't have to make this request again.
            glob.cache['unsubmitted'].add(map_md5)

        return f'{1 if set_exists else -1}|false'.encode()

    if bmap.status < RankedStatus.Ranked:
        # only show leaderboards for ranked,
        # approved, qualified, or loved maps.
        return f'{int(bmap.status)}|false'.encode()

    # statuses: 0: failed, 1: passed but not top, 2: passed top
    query = [
        f'SELECT s.id, s.{scoring} AS _score, '
        's.max_combo, s.n50, s.n100, s.n300, '
        's.nmiss, s.nkatu, s.ngeki, s.perfect, s.mods, '
        'UNIX_TIMESTAMP(s.play_time) time, u.name, u.id userid '
        f'FROM {table} s LEFT JOIN users u ON u.id = s.userid '
        'WHERE s.map_md5 = %s AND s.status = 2 AND mode = %s'
    ]

    params = [map_md5, conn.args['m']]

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

    res: list[str] = []

    # ranked status, serv has osz2, bid, bsid, len(scores)
    res.append(f'{int(bmap.status)}|false|{bmap.id}|'
               f'{bmap.set_id}|{len(scores) if scores else 0}')

    # offset, name, rating
    res.append(f'0\n{bmap.full}\n10.0')

    if not scores:
        # simply return an empty set.
        return '\n'.join(res + ['', '']).encode()

    p_best = await glob.db.fetch(
        f'SELECT id, {scoring} AS _score, '
        'max_combo, n50, n100, n300, '
        'nmiss, nkatu, ngeki, perfect, mods, '
        'UNIX_TIMESTAMP(play_time) time '
        f'FROM {table} '
        'WHERE map_md5 = %s AND mode = %s '
        'AND userid = %s AND status = 2 '
        'ORDER BY _score DESC LIMIT 1', [
            map_md5, conn.args['m'], p.id
        ]
    )

    score_fmt = ('{id}|{name}|{score}|{max_combo}|'
                 '{n50}|{n100}|{n300}|{nmiss}|{nkatu}|{ngeki}|'
                 '{perfect}|{mods}|{userid}|{rank}|{time}|{has_replay}')

    if p_best:
        # calculate the rank of the score.
        p_best_rank = 1 + (await glob.db.fetch(
            f'SELECT COUNT(*) AS count FROM {table} '
            'WHERE map_md5 = %s AND mode = %s '
            f'AND status = 2 AND {scoring} > %s', [
                map_md5, conn.args['m'],
                p_best['_score']
            ]
        ))['count']

        res.append(
            score_fmt.format(
                **p_best,
                name = p.name, userid = p.id,
                score = int(p_best['_score']),
                has_replay = '1', rank = p_best_rank
            )
        )
    else:
        res.append('')

    res.extend(
        score_fmt.format(
            **s, score = int(s['_score']),
            has_replay = '1', rank = idx + 1
        ) for idx, s in enumerate(scores)
    )

    return '\n'.join(res).encode()

@web_handler('osu-comment.php')
@required_mpargs({'u', 'p', 'b', 's',
                  'm', 'r', 'a'})
@get_login('u', 'p')
async def osuComment(p: Player, conn: AsyncConnection) -> Optional[bytes]:
    mp_args = conn.multipart_args

    action = mp_args['a']

    if action == 'get':
        # client is requesting all comments
        comments = glob.db.iterall(
            "SELECT c.time, c.target, c.colour, "
            "c.comment, u.priv FROM comments c "
            "LEFT JOIN users u ON u.id = c.userid "
            "WHERE (c.target = 'replay' AND c.id = %s) "
            "OR (c.target = 'song' AND c.id = %s) "
            "OR (c.target = 'map' AND c.id = %s) ",
            [mp_args['r'], mp_args['s'], mp_args['b']]
        )

        ret: list[str] = []

        async for com in comments:
            # TODO: maybe support player/creator colours?
            # pretty expensive for very low gain, but completion :D
            if com['priv'] & Privileges.Nominator:
                fmt = 'bat'
            elif com['priv'] & Privileges.Donator:
                fmt = 'supporter'
            else:
                fmt = ''

            if com['colour']:
                fmt += f'|{com["colour"]}'

            ret.append('{time}\t{target}\t'
                       '{fmt}\t{comment}'.format(fmt=fmt, **com))

        return '\n'.join(ret).encode()

    elif action == 'post':
        # client is submitting a new comment

        # get the comment's target scope
        target = mp_args['target']
        if target not in ('song', 'map', 'replay'):
            return b'Invalid target.'

        # get the corresponding id from the request
        com_id = mp_args[{'song': 's', 'map': 'b',
                          'replay': 'r'}[target]]

        if not com_id.isdecimal():
            return b'Invalid corresponding id.'

        # get some extra params
        sttime = mp_args['starttime']
        comment = mp_args['comment']

        if p.priv & Privileges.Donator:
            # only supporters can use colours.
            # XXX: colour may still be none,
            # since mp_args is a defaultdict.
            colour = mp_args['f']
        else:
            colour = None

        # insert into sql
        await glob.db.execute(
            'INSERT INTO comments '
            'VALUES (%s, %s, %s, %s, %s, %s)',
            [com_id, target, p.id,
             sttime, comment, colour]
        )

        return # empty resp is fine

    else:
        # invalid action
        return b'Invalid action.'

@web_handler('osu-markasread.php')
@required_args({'u', 'h', 'channel'})
@get_login('u', 'h')
async def osuMarkAsRead(p: Player, conn: AsyncConnection) -> Optional[bytes]:
    if not (t_name := unquote(conn.args['channel'])):
        return b'' # no channel specified

    if not (t := await glob.players.get_by_name(t_name, sql=True)):
        return

    # mark any unread mail from this user as read.
    await glob.db.execute(
        'UPDATE `mail` SET `read` = 1 '
        'WHERE `to_id` = %s AND `from_id` = %s '
        'AND `read` = 0',
        [p.id, t.id]
    )

@web_handler('osu-getseasonal.php')
async def osuSeasonal(conn: AsyncConnection) -> Optional[bytes]:
    return orjson.dumps(glob.config.seasonal_bgs)

@web_handler('osu-error.php')
async def osuError(conn: AsyncConnection) -> Optional[bytes]:
    ...

@web_handler('check-updates.php')
@required_args({'action', 'stream'})
async def checkUpdates(conn: AsyncConnection) -> Optional[bytes]:
    action = conn.args['action']
    stream = conn.args['stream']

    if action not in ('check', 'path', 'error'):
        return b'Invalid action.'

    if stream not in ('cuttingedge', 'stable40', 'beta40', 'stable'):
        return b'Invalid stream.'

    if action == 'error':
        # client is just reporting an error updating
        return

    cache = glob.cache['update'][stream]
    current_time = int(time.time())

    if cache[action] and cache['timeout'] > current_time:
        return cache[action]

    url = 'https://old.ppy.sh/web/check-updates.php'
    async with glob.http.get(url, params = conn.args) as resp:
        if not resp or resp.status != 200:
            return b'Failed to retrieve data from osu!'

        result = await resp.read()

    # update the cached result.
    cache[action] = result
    cache['timeout'] = (glob.config.updates_cache_timeout +
                        current_time)

    return result

async def updateBeatmap(conn: AsyncConnection) -> Optional[bytes]:
    if not (re := regexes.mapfile.match(unquote(conn.path[10:]))):
        log(f'Requested invalid map update {conn.path}.', Ansi.LRED)
        return

    if not (res := await glob.db.fetch(
        'SELECT id, md5 FROM maps WHERE '
        'artist = %s AND title = %s '
        'AND creator = %s AND version = %s', [
            re['artist'], re['title'],
            re['creator'], re['version']
        ]
    )): return # no map found

    if os.path.exists(filepath := f".data/osu/{res['id']}.osu"):
        # map found on disk.

        async with aiofiles.open(filepath, 'rb') as f:
            content = await f.read()
    else:
        # we don't have map, get from osu!
        url = f"https://old.ppy.sh/osu/{res['id']}"

        async with glob.http.get(url) as resp:
            if not resp or resp.status != 200:
                log(f'Could not find map {filepath}!', Ansi.LRED)
                return

            content = await resp.read()

        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(content)

    return content

# some depreacted handlers - no longer used in regular connections.
# XXX: perhaps these could be turned into decorators to allow
# for better specialization of params? perhaps prettier too :P
async def deprecated_handler(conn: AsyncConnection) -> Optional[bytes]:
    args = conn.args or conn.multipart_args # cant support both :/.. could union
    pname = phash = None

    for p in ('u', 'us'):
        if pname := args[p]:
            break
    else:
        return

    for p in ('h', 'ha', 'p'):
        if phash := args[p]:
            break
    else:
        return

    if not (p := await glob.players.get_login(unquote(pname), phash)):
        return

    log(f'{p} used deprecated handler {conn.path!r}.', Ansi.LRED)

# won't work for submit modular cuz it's special case lol
#osuSubmitModular = web_handler('osu-submit-modular.php')(deprecated_handler)
