# -*- coding: utf-8 -*-

from constants.gamemodes import GameMode
from typing import Any, Optional, Callable
from enum import IntEnum, unique
from collections import defaultdict
from functools import partial, wraps
from pathlib import Path
import re
import time
import copy
import hashlib
import bcrypt
import random
import orjson
import aiofiles
from typing import TYPE_CHECKING

from urllib.parse import unquote
from cmyui import (Connection, Domain,
                   _isdecimal, rstring,
                   log, Ansi)

import packets

from constants.mods import Mods
from constants.clientflags import ClientFlags
from constants import regexes

from objects.score import Score, SubmissionStatus
from objects.player import Privileges
from objects.beatmap import Beatmap, RankedStatus
from objects import glob

from utils.misc import point_of_interest

if TYPE_CHECKING:
    from objects.player import Player

# TODO:
# osu-rate.php: beatmap rating on score submission.
# osu-osz2-bmsubmit-upload.php: beatmap submission upload
# osu-osz2-bmsubmit-getid.php: beatmap submission getinfo

""" osu: handle connections from web, api, and beyond? """

domain = Domain(re.compile(f'osu(\.ppy\.sh|\.{config.domain})$'))

# Some helper decorators (used for /web/ connections)

def _required_args(args: set[str], argset: str) -> Callable:
    def wrapper(f: Callable) -> Callable:

        # modify the handler code to ensure that
        # all arguments are sent in the request.
        @wraps(f)
        async def handler(conn: Connection) -> Optional[bytes]:
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
        async def handler(conn: Connection) -> Optional[bytes]:
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

""" /web/ handlers """

@domain.route('/web/bancho_connect.php')
async def banchoConnect(conn: Connection) -> Optional[bytes]:
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
@domain.route('/web/osu-osz2-bmsubmit-upload.php')
async def osuMapBMSubmitUpload(conn: Connection) -> Optional[bytes]:
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
@domain.route('/web/osu-osz2-bmsubmit-getid.php')
async def osuMapBMSubmitGetID(conn: Connection) -> Optional[bytes]:
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

@domain.route('/web/osu-screenshot.php', methods=['POST'])
@required_mpargs({'u', 'p', 'v'})
@get_login('u', 'p')
async def osuScreenshot(p: 'Player', conn: Connection) -> Optional[bytes]:
    if 'ss' not in conn.files:
        log(f'screenshot req missing file.', Ansi.LRED)
        return (400, b'')

    filename = f'{rstring(8)}.png'

    async with aiofiles.open(f'.data/ss/{filename}', 'wb') as f:
        await f.write(conn.files['ss'])

    log(f'{p} uploaded {filename}.')
    return filename.encode()

@domain.route('/web/osu-getfriends.php')
@required_args({'u', 'h'})
@get_login('u', 'h')
async def osuGetFriends(p: 'Player', conn: Connection) -> Optional[bytes]:
    return '\n'.join(map(str, p.friends)).encode()

@domain.route('/web/osu-getbeatmapinfo.php', methods=['POST'])
@required_args({'u', 'h'})
@get_login('u', 'h')
async def osuGetBeatmapInfo(p: 'Player', conn: Connection) -> Optional[bytes]:
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

    for _ in data['Ids']:
        # still have yet to see
        # this actually used..
        point_of_interest()

    return '\n'.join(ret).encode()

@domain.route('/web/osu-getfavourites.php')
@required_args({'u', 'h'})
@get_login('u', 'h')
async def osuGetFavourites(p: 'Player', conn: Connection) -> Optional[bytes]:
    favourites = await glob.db.fetchall(
        'SELECT setid FROM favourites '
        'WHERE userid = %s',
        [p.id]
    )

    return '\n'.join(favourites).encode()

@domain.route('/web/osu-addfavourite.php')
@required_args({'u', 'h', 'a'})
@get_login('u', 'h', b'Please login to add favourites!')
async def osuAddFavourite(p: 'Player', conn: Connection) -> Optional[bytes]:
    # make sure set id is valid
    if not conn.args['a'].isdecimal():
        return (400, b'Invalid beatmap set id.')

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

@domain.route('/web/lastfm.php')
@required_args({'b', 'action', 'us', 'ha'})
@get_login('us', 'ha')
async def lastFM(p: 'Player', conn: Connection) -> Optional[bytes]:
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

        p.enqueue(packets.notification('\n'.join([
            "Hey!",
            "It appears you have hq!osu's multiaccounting tool (relife) enabled.",
            "This tool leaves a change in your registry that the osu! client can detect.",
            "Please re-install relife and disable the program to avoid any restrictions."
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

@domain.route('/web/osu-search.php')
@required_args({'u', 'h', 'r', 'q', 'm', 'p'})
@get_login('u', 'h')
async def osuSearchHandler(p: 'Player', conn: Connection) -> Optional[bytes]:
    if not conn.args['p'].isdecimal():
        return (400, b'')

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

#    # XXX: some work on gulag's possible future mirror
#    query = conn.args['q'].replace('+', ' ') # TODO: allow empty
#    offset = int(conn.args['p']) * 100
#
#    sql_query = [
#        'SELECT DISTINCT set_id, artist, title,',
#        'status, creator, last_update FROM maps',
#        'LIMIT %s, 100'
#    ]
#
#    sql_params = [offset]
#
#    # TODO: actually support the buttons lol
#    if query not in ('Newest', 'Top Rated', 'Most Played'):
#        # They're searching something specifically.
#        sql_query.insert(2, 'WHERE title LIKE %s')
#        sql_params.insert(0, f'%{query}%')
#
#    if not (res := await glob.db.fetchall(' '.join(sql_query), sql_params)):
#        return b'-1\nNo matches found.'
#
#    # We'll construct the response as a list of
#    # strings, then join and encode when returning.
#    ret = [f'{len(res)}']
#
#    # For each beatmap set
#    for bmapset in res:
#        # retrieve the data for each difficulty
#        if not (bmaps := await glob.db.fetchall(
#            # Remove ',' from diffname since it's our split char.
#            "SELECT REPLACE(version, ',', '') AS version, "
#            'mode, cs, od, ar, hp, diff '
#            'FROM maps WHERE set_id = %s '
#            # Order difficulties by mode > star rating > ar.
#            'ORDER BY mode ASC, diff ASC, ar ASC',
#            [bmapset['set_id']]
#        )): continue
#
#        # Construct difficulty-specific information.
#        diffs = ','.join(
#            '[{diff:.2f}⭐] {version} {{CS{cs} OD{od} AR{ar} HP{hp}}}@{mode}'.format(**row)
#            for row in bmaps
#        )
#
#        ret.append(
#            '{set_id}.osz|{artist}|{title}|{creator}|'
#            '{status}|10.0|{last_update}|{set_id}|' # TODO: rating
#            '0|0|0|0|0|{diffs}'.format(**bmapset, diffs=diffs)
#        ) # 0s are threadid, has_vid, has_story, filesize, filesize_novid
#
#    return '\n'.join(ret).encode()

@domain.route('/web/osu-search-set.php')
@required_args({'u', 'h'})
@get_login('u', 'h')
async def osuSearchSetHandler(p: 'Player', conn: Connection) -> Optional[bytes]:
    # Since we only need set-specific data, we can basically
    # just do same same query with either bid or bsid.
    if 's' in conn.args:
        # gulag chat menu: if the argument is negative,
        # check if it's in the players menu options.
        if conn.args['s'][0] == '-':
            opt_id = int(conn.args['s'])

            if opt_id not in p.menu_options:
                return b'no voila'

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

            # send back some random syntactically valid
            # beatmap info so that the client doesn't open
            # a webpage when clicking an unknown url.
            return b'voila'
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
    # of "anticheat", simply ban a user if they are not
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

@domain.route('/web/osu-submit-modular-selector.php', methods=['POST'])
@required_mpargs({'x', 'ft', 'score', 'fs', 'bmk', 'iv',
                  'c1', 'st', 'pass', 'osuver', 's'})
async def osuSubmitModularSelector(conn: Connection) -> Optional[bytes]:
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
        glob.players.enqueue(packets.userStats(s.player))

    table = s.mode.sql_table

    # Check for score duplicates
    # TODO: might need to improve?
    res = await glob.db.fetch(
        f'SELECT 1 FROM {table} '
        'WHERE play_time > DATE_SUB(NOW(), INTERVAL 2 MINUTE) ' # last 2mins
        'AND mode = %s AND map_md5 = %s '
        'AND userid = %s AND mods = %s '
        'AND score = %s AND play_time', [
            s.mode.as_vanilla, s.bmap.md5,
            s.player.id, int(s.mods), s.score
        ]
    )

    if res:
        log(f'{s.player} submitted a duplicate score.', Ansi.LYELLOW)
        return b'error: no'

    time_elapsed = mp_args['st' if s.passed else 'ft']

    if not time_elapsed.isdecimal():
        return (400, b'?')

    s.time_elapsed = int(time_elapsed)

    if 'i' in conn.files:
        point_of_interest()

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

        ann = [f'\x01ACTION achieved #1 on {s.bmap.embed} +{s.mods!r} with {s.acc:.2f}% for {performance}.']

        if prev_n1: # If there was previously a score on the map, add old #1.
            ann.append('(Previously: [https://osu.ppy.sh/u/{id} {name}])'.format(**prev_n1))

        await announce_chan.send(s.player, ' '.join(ann), to_self=True)

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

        # these should probably just be abstracted
        # into a class of some sort so the if/else
        # part isn't just left in the open like this lol
        def kv_pair(name: str, k: Optional[Any], v: Any) -> str:
            return f'{name}Before:{k or ""}|{name}After:{v}'

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
            f'chartUrl:https://{glob.config.domain}/b/{s.bmap.id}',
            'chartName:Beatmap Ranking',

            *((
                kv_pair('rank', s.prev_best.rank, s.rank),
                kv_pair('rankedScore', s.prev_best.score, s.score),
                kv_pair('totalScore', s.prev_best.score, s.score),
                kv_pair('maxCombo', s.prev_best.max_combo, s.max_combo),
                kv_pair('accuracy', round(s.prev_best.acc, 2), round(s.acc, 2)),
                kv_pair('pp', s.prev_best.pp, s.pp)
            ) if s.prev_best else (
                kv_pair('rank', None, s.rank),
                kv_pair('rankedScore', None, s.score),
                kv_pair('totalScore', None, s.score),
                kv_pair('maxCombo', None, s.max_combo),
                kv_pair('accuracy', None, round(s.acc, 2)),
                kv_pair('pp', None, s.pp)
            )),

            f'onlineScoreId:{s.id}'
        )))

        # append overall ranking chart (#3)
        charts.append('|'.join((
            'chartId:overall',
            f'chartUrl:https://{glob.config.domain}/u/{s.player.id}',
            'chartName:Overall Ranking',

            # TODO: achievements
            *((
                kv_pair('rank', prev_stats.rank, stats.rank),
                kv_pair('rankedScore', prev_stats.rscore, stats.rscore),
                kv_pair('totalScore', prev_stats.tscore, stats.tscore),
                kv_pair('maxCombo', prev_stats.max_combo, stats.max_combo),
                kv_pair('accuracy', round(prev_stats.acc, 2), round(stats.acc, 2)),
                kv_pair('pp', prev_stats.pp, stats.pp),
            ) if prev_stats else (
                kv_pair('rank', None, stats.rank),
                kv_pair('rankedScore', None, stats.rscore),
                kv_pair('totalScore', None, stats.tscore),
                kv_pair('maxCombo', None, stats.max_combo),
                kv_pair('accuracy', None, round(stats.acc, 2)),
                kv_pair('pp', None, stats.pp),
            ))
        )))

        ret = '\n'.join(charts).encode()

    log(f'[{s.mode!r}] {s.player} submitted a score! ({s.status!r})', Ansi.LGREEN)
    return ret

REPLAYS_PATH = Path.cwd() / '.data/osr'
@domain.route('/web/osu-getreplay.php')
@required_args({'u', 'h', 'm', 'c'})
@get_login('u', 'h')
async def getReplay(p: 'Player', conn: Connection) -> Optional[bytes]:
    path = REPLAYS_PATH / f'{conn.args["c"]}.osr'

    if not path.exists():
        return # osu! expects empty resp for no replay

    async with aiofiles.open(path, 'rb') as f:
        return await f.read()

# XXX: going to be slightly more annoying than expected to set this up :P
#@domain.route('/web/osu-session.php', methods=['POST'])
#@required_mpargs({'u', 'h', 'action'})
#@get_login('u', 'h')
#async def osuSession(p: 'Player', conn: Connection) -> Optional[bytes]:
#    mp_args = conn.multipart_args
#
#    if mp_args['action'] not in ('check', 'submit'):
#        return # invalid action
#
#    if mp_args['action'] == 'submit':
#        # client is submitting a performance session after a score
#        # we'll save some basic information, and do some basic checks,
#        # could surely be useful for anticheat and debugging purposes.
#        data = orjson.loads(mp_args['content'])
#
#        if data['Tags']['Replay'] == 'True':
#            # the user was viewing a replay,
#            # no need to save to sql.
#            return
#
#        # so, osu! sends a 'Fullscreen' param and a 'Beatmap'
#        # param, but both of them are the fullscreen value? lol
#
#        op_sys = data['Tags']['OS']
#        fullscreen = data['Tags']['Fullscreen'] == 'True'
#        fps_cap = data['Tags']['FrameSync']
#        compatibility = data['Tags']['Compatibility'] == 'True'
#        version = data['Tags']['Version'] # osu! version
#        start_time = data['StartTime']
#        end_time = data['EndTime']
#        frame_count = data['ProcessedFrameCount']
#        spike_frames = data['SpikeFrameCount']
#
#        aim_rate = data['AimFrameRate']
#        if aim_rate == 'Infinity':
#            aim_rate = 0
#
#        completion = data['Completion']
#        identifier = data['Identifier']
#        average_frametime = data['AverageFrameTime'] * 1000
#
#        if identifier:
#            point_of_interest()
#
#        # chances are, if we can't find a very
#        # recent score by a user, it just hasn't
#        # submitted yet.. we'll allow 5 seconds
#
#        rscore: Optional[Score] = None
#        retries = 0
#        ctime = time.time()
#
#        cache = glob.cache['performance_reports']
#
#        while retries < 5:
#            if (rscore := p.recent_score) and rscore.id not in cache:
#                # only accept scores submitted
#                # within the last 5 seconds.
#
#                if ((ctime + retries) - (rscore.play_time - 5)) > 0:
#                    break
#
#            retries += 1
#            await asyncio.sleep(1)
#        else:
#            # STILL no score found..
#            # this can happen if they submit a duplicate score,
#            # perhaps i should add some kind of system to prevent
#            # this from happening or re-think this overall.. i'd
#            # imagine this can be useful for old client det. tho :o
#            log('Received performance report but found no score', Ansi.LRED)
#            return
#
#        # TODO: timing checks
#
#        #if version != p.osu_ver:
#        #    point_of_interest()
#
#        # remember that we've already received a report
#        # for this score, so that we don't overwrite it.
#        glob.cache['performance_reports'].add(rscore.id)
#
#        await glob.db.execute(
#            'INSERT INTO performance_reports VALUES '
#            '(%s, %s, %s, %s, %s, %s, %s,'
#            ' %s, %s, %s, %s, %s, %s, %s)', [
#                rscore.id,
#                op_sys, fullscreen, fps_cap,
#                compatibility, version,
#                start_time, end_time,
#                frame_count, spike_frames,
#                aim_rate, completion,
#                identifier, average_frametime
#            ]
#        )
#
#    else:
#        # TODO: figure out what this wants?
#        # seems like it adds the response from server
#        # to some kind of internal buffer, dunno why tho
#        return

@domain.route('/web/osu-rate.php')
@required_args({'u', 'p', 'c'})
@get_login('u', 'p', b'auth fail')
async def osuRate(p: 'Player', conn: Connection) -> Optional[bytes]:
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

@domain.route('/web/osu-osz2-getscores.php')
@required_args({'s', 'vv', 'v', 'c', 'f', 'm',
                'i', 'mods', 'h', 'a', 'us', 'ha'})
@get_login('us', 'ha')
async def getScores(p: 'Player', conn: Connection) -> Optional[bytes]:
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
        glob.players.enqueue(packets.userStats(p))

    table = mode.sql_table
    scoring = 'pp' if mode >= GameMode.rx_std else 'score'

    if not (bmap := await Beatmap.from_md5(map_md5, map_set_id)):
        # couldn't find in db or at osu! api by md5.
        # check if we have the map in our db (by filename).

        filename = conn.args['f'].replace('+', ' ')
        if not (re := regexes.mapfile.match(unquote(filename))):
            log(f'Requested invalid file - {filename}.', Ansi.LRED)
            return (400, b'invalid map file syntax.')

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
        # a little cursed, but my wrapper doesn't like being
        # passed iterables yet, and nor does the lower lv api xd
        friends_str = ','.join(map(str, p.friends))
        query.append(f'AND s.userid IN ({friends_str}, {p.id})')
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

@domain.route('/web/osu-comment.php', methods=['POST'])
@required_mpargs({'u', 'p', 'b', 's',
                  'm', 'r', 'a'})
@get_login('u', 'p')
async def osuComment(p: 'Player', conn: Connection) -> Optional[bytes]:
    mp_args = conn.multipart_args

    action = mp_args['a']

    if action == 'get':
        # client is requesting all comments
        comments = glob.db.iterall(
            "SELECT c.time, c.target_type, c.colour, "
            "c.comment, u.priv FROM comments c "
            "LEFT JOIN users u ON u.id = c.userid "
            "WHERE (c.target_type = 'replay' AND c.target_id = %s) "
            "OR (c.target_type = 'song' AND c.target_id = %s) "
            "OR (c.target_type = 'map' AND c.target_id = %s) ",
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

            ret.append('{time}\t{target_type}\t'
                       '{fmt}\t{comment}'.format(fmt=fmt, **com))

        return '\n'.join(ret).encode()

    elif action == 'post':
        # client is submitting a new comment

        # get the comment's target scope
        target_type = mp_args['target']
        if target_type not in ('song', 'map', 'replay'):
            return (400, b'Invalid target_type.')

        # get the corresponding id from the request
        target_id = mp_args[{'song': 's', 'map': 'b',
                             'replay': 'r'}[target_type]]

        if not target_id.isdecimal():
            return (400, b'Invalid target id.')

        # get some extra params
        sttime = mp_args['starttime']
        comment = mp_args['comment']

        if 'f' in mp_args and p.priv & Privileges.Donator:
            # only supporters can use colours.
            # XXX: colour may still be none,
            # since mp_args is a defaultdict.
            colour = mp_args['f']
        else:
            colour = None

        # insert into sql
        await glob.db.execute(
            'INSERT INTO comments (target_id, target_type, '
            'userid, time, comment, colour) VALUES '
            '(%s, %s, %s, %s, %s, %s)',
            [target_id, target_type, p.id,
             sttime, comment, colour]
        )

        return # empty resp is fine

    else:
        # invalid action
        return (400, b'Invalid action.')

@domain.route('/web/osu-markasread.php')
@required_args({'u', 'h', 'channel'})
@get_login('u', 'h')
async def osuMarkAsRead(p: 'Player', conn: Connection) -> Optional[bytes]:
    if not (t_name := unquote(conn.args['channel'])):
        return # no channel specified

    if not (t := await glob.players.get(name=t_name, sql=True)):
        return

    # mark any unread mail from this user as read.
    await glob.db.execute(
        'UPDATE `mail` SET `read` = 1 '
        'WHERE `to_id` = %s AND `from_id` = %s '
        'AND `read` = 0',
        [p.id, t.id]
    )

@domain.route('/web/osu-getseasonal.php')
async def osuSeasonal(conn: Connection) -> Optional[bytes]:
    return orjson.dumps(glob.config.seasonal_bgs)

@domain.route('/web/osu-error.php', methods=['POST'])
async def osuError(conn: Connection) -> Optional[bytes]:
    ...

@domain.route('/web/check-updates.php')
@required_args({'action', 'stream'})
async def checkUpdates(conn: Connection) -> Optional[bytes]:
    action = conn.args['action']
    stream = conn.args['stream']

    if action not in ('check', 'path', 'error'):
        return (400, b'Invalid action.')

    if stream not in ('cuttingedge', 'stable40', 'beta40', 'stable'):
        return (400, b'Invalid stream.')

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
            return (503, b'Failed to retrieve data from osu!')

        result = await resp.read()

    # update the cached result.
    cache[action] = result
    cache['timeout'] = (glob.config.updates_cache_timeout +
                        current_time)

    return result

""" /api/ Handlers """
# TODO: add oauth so we can do more stuff owo..
# also, give me ideas for api things
# POST /api/set_avatar

@domain.route('/api/get_online')
async def api_get_online(conn: Connection) -> Optional[bytes]:
    """Get the current amount of online players."""
    # TODO: perhaps add peak(s)? (24h, 5d, 3w, etc.)
    return f'{{"online":{len(glob.players)-1}}}'.encode()

@domain.route('/api/get_user')
async def api_get_user(conn: Connection) -> Optional[bytes]:
    """Get user info/stats from a specified name or id."""
    if 'name' not in conn.args and 'id' not in conn.args:
        return (400, b'Must provide either id or name!')

    if 'scope' not in conn.args \
    or conn.args['scope'] not in ('info', 'stats'):
        return (400, b'Must provide scope (info/stats).')

    if 'id' in conn.args:
        if not conn.args['id'].isdecimal():
            return (400, b'Invalid player id.')

        pid = conn.args['id']
    else:
        if not 2 <= len(name := unquote(conn.args['name'])) < 16:
            return (400, b'Invalid player name.')

        # get their id from username.
        pid = await glob.db.fetch(
            'SELECT id FROM users '
            'WHERE safe_name = %s',
            [name]
        )

        if not pid:
            return (404, b'User not found.')

        pid = pid['id']

    if conn.args['scope'] == 'info':
        # return user info
        query = ('SELECT id, name, safe_name, '
                 'priv, country, silence_end ' # silence_end public?
                 'FROM users WHERE id = %s')
    else:
        # return user stats
        query = 'SELECT * FROM stats WHERE id = %s'

    res = await glob.db.fetch(query, [pid])
    return orjson.dumps(res) if res else b'User not found.'

@domain.route('/api/get_scores')
async def api_get_scores(conn: Connection) -> Optional[bytes]:
    if 'name' not in conn.args and 'id' not in conn.args:
        return (400, b'Must provide either player id or name!')

    if 'id' in conn.args:
        if not conn.args['id'].isdecimal():
            return (400, b'Invalid player id.')

        pid = conn.args['id']
    else:
        if not 2 <= len(name := unquote(conn.args['name'])) < 16:
            return (400, b'Invalid player name.')

        # get their id from username.
        pid = await glob.db.fetch(
            'SELECT id FROM users '
            'WHERE safe_name = %s',
            [name]
        )

        if not pid:
            return (404, b'User not found.')

        pid = pid['id']

    if 'mods' in conn.args:
        if not conn.args['mods'].isdecimal():
            return (400, b'Invalid mods.')

        mods = Mods(int(conn.args['mods']))

        if mods & Mods.RELAX:
            mods &= ~Mods.RELAX
            table = 'scores_rx'
        elif mods & Mods.AUTOPILOT:
            mods &= ~Mods.AUTOPILOT
            table = 'scores_ap'
        else:
            table = 'scores_vn'
    else:
        mods = Mods.NOMOD
        table = 'scores_vn'

    if 'limit' in conn.args:
        if not conn.args['limit'].isdecimal():
            return (400, b'Invalid limit.')

        limit = min(int(conn.args['limit']), 100)
    else:
        limit = 100

    query = ['SELECT id, map_md5, score, pp, acc, max_combo, mods, '
             'n300, n100, n50, nmiss, ngeki, nkatu, grade, status, '
             'mode, play_time, time_elapsed, userid, perfect '
             f'FROM {table} WHERE userid = %s']
    params = [pid]

    if mods:
        query.append('WHERE mods & %s > 0')
        params.append(int(mods))

    query.append('ORDER BY id DESC LIMIT %s')
    params.append(limit)

    res = await glob.db.fetchall(' '.join(query), params)
    return orjson.dumps(res) if res else b'No scores found.'

""" Misc handlers """

SCREENSHOTS_PATH = Path.cwd() / '.data/ss'
@domain.route(re.compile(r'^/ss/[a-zA-Z0-9]{8}\.png$'))
async def get_screenshot(conn: Connection) -> Optional[bytes]:
    if len(conn.path) != 16:
        return (400, b'Invalid request.')

    path = SCREENSHOTS_PATH / conn.path[4:]

    if not path.exists():
        return (404, b'Screenshot not found.')

    async with aiofiles.open(path, 'rb') as f:
        return await f.read()

@domain.route(re.compile(r'^/d/\d{1,10}$'))
async def get_osz(conn: Connection) -> Optional[bytes]:
    """Handle a map download request (osu.ppy.sh/d/*)."""
    mirror_url = f'{glob.config.mirror}/d/{conn.path[3:]}'
    conn.add_resp_header(f'Location: {mirror_url}')
    return (302, b'')

BEATMAPS_PATH = Path.cwd() / '.data/osu'
@domain.route(re.compile(r'^/web/maps/'))
async def get_updated_beatmap(conn: Connection) -> Optional[bytes]:
    if not (re := regexes.mapfile.match(unquote(conn.path[10:]))):
        log(f'Requested invalid map update {conn.path}.', Ansi.LRED)
        return (400, b'Invalid map file syntax.')

    if not (res := await glob.db.fetch(
        'SELECT id, md5 FROM maps WHERE '
        'artist = %s AND title = %s '
        'AND creator = %s AND version = %s', [
            re['artist'], re['title'],
            re['creator'], re['version']
        ]
    )): return (404, b'Map not found.')

    path = BEATMAPS_PATH / f'{res["id"]}.osu'

    if path.exists():
        # map found on disk.
        async with aiofiles.open(path, 'rb') as f:
            content = await f.read()
    else:
        # we don't have map, get from osu!
        url = f"https://old.ppy.sh/osu/{res['id']}"

        async with glob.http.get(url) as resp:
            if not resp or resp.status != 200:
                log(f'Could not find map {path}!', Ansi.LRED)
                return (404, b'Could not find map on osu! server.')

            content = await resp.read()

        async with aiofiles.open(path, 'wb') as f:
            await f.write(content)

    return content

""" ingame registration """

@domain.route('/users', methods=['POST'])
async def register_account(conn: Connection) -> Optional[bytes]:
    mp_args = conn.multipart_args

    name = mp_args['user[username]']
    email = mp_args['user[user_email]']
    pw_txt = mp_args['user[password]']

    if not all((name, email, pw_txt)) or 'check' not in mp_args:
        return (400, b'Missing required params')

    # ensure all args passed
    # are safe for registration.
    errors = defaultdict(list)

    # Usernames must:
    # - be within 2-15 characters in length
    # - not contain both ' ' and '_', one is fine
    # - not be in the config's `disallowed_names` list
    # - not already be taken by another player
    if not regexes.username.match(name):
        errors['username'].append('Must be 2-15 characters in length.')

    if '_' in name and ' ' in name:
        errors['username'].append('May contain "_" and " ", but not both.')

    if name in glob.config.disallowed_names:
        errors['username'].append('Disallowed username; pick another.')

    if await glob.db.fetch('SELECT 1 FROM users WHERE name = %s', name):
        errors['username'].append('Username already taken by another player.')

    # Emails must:
    # - match the regex `^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{1,24}$`
    # - not already be taken by another player
    if not regexes.email.match(email):
        errors['user_email'].append('Invalid email syntax.')

    if await glob.db.fetch('SELECT 1 FROM users WHERE email = %s', email):
        errors['user_email'].append('Email already taken by another player.')

    # Passwords must:
    # - be within 8-32 characters in length
    # - have more than 3 unique characters
    # - not be in the config's `disallowed_passwords` list
    if not 8 < len(pw_txt) <= 32:
        errors['password'].append('Must be 8-32 characters in length.')

    if len(set(pw_txt)) <= 3:
        errors['password'].append('Must have more than 3 unique characters.')

    if pw_txt.lower() in glob.config.disallowed_passwords:
        errors['password'].append('That password was deemed too simple.')

    if errors:
        # we have errors to send back.
        errors_full = {'form_error': {'user': errors}}
        return (400, orjson.dumps(errors_full))

    if mp_args['check'] == '0':
        # the client isn't just checking values,
        # they want to register the account now.
        # make the md5 & bcrypt the md5 for sql.
        pw_md5 = hashlib.md5(pw_txt.encode()).hexdigest().encode()
        pw_bcrypt = bcrypt.hashpw(pw_md5, bcrypt.gensalt())
        glob.cache['bcrypt'][pw_bcrypt] = pw_md5 # cache result for login

        safe_name = name.lower().replace(' ', '_')

        # add to `users` table.
        user_id = await glob.db.execute(
            'INSERT INTO users '
            '(name, safe_name, email, pw_bcrypt, creation_time, latest_activity) '
            'VALUES (%s, %s, %s, %s, UNIX_TIMESTAMP(), UNIX_TIMESTAMP())',
            [name, safe_name, email, pw_bcrypt]
        )

        # add to `stats` table.
        await glob.db.execute(
            'INSERT INTO stats '
            '(id) VALUES (%s)',
            [user_id]
        )

        log(f'<{name} ({user_id})> has registered!', Ansi.LGREEN)

    return b'ok' # success
