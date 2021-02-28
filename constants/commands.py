# -*- coding: utf-8 -*-

import asyncio
import copy
import importlib
import random
import re
import time
from datetime import datetime
from time import perf_counter_ns as clock_ns
from typing import Callable
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from typing import TYPE_CHECKING
from typing import Union

import cmyui

import packets
from constants import regexes
from constants.gamemodes import GameMode
from constants.mods import Mods
from constants.mods import SPEED_CHANGING_MODS
from constants.privileges import Privileges
from objects import glob
from objects.beatmap import Beatmap
from objects.beatmap import RankedStatus
from objects.clan import Clan
from objects.clan import ClanPrivileges
from objects.match import MapPool
from objects.match import MatchTeams
from objects.match import MatchTeamTypes
from objects.match import MatchWinConditions
from objects.match import SlotStatus
from objects.player import Player
from objects.score import SubmissionStatus
from utils.recalculator import PPCalculator

if TYPE_CHECKING:
    from objects.channel import Channel
    from objects.match import Match

Messageable = Union['Channel', Player]
CommandResponse = dict[str, str]

class Command(NamedTuple):
    triggers: list[str]
    callback: Callable
    priv: Privileges
    hidden: bool
    doc: str

class CommandSet:
    __slots__ = ('trigger', 'doc', 'commands')

    def __init__(self, trigger: str, doc: str) -> None:
        self.trigger = trigger
        self.doc = doc

        self.commands: list[Command] = []

    def add(self, priv: Privileges, aliases: list[str] = [],
            hidden: bool = False) -> Callable:
        def wrapper(f: Callable):
            self.commands.append(Command(
                # NOTE: this method assumes that functions without any
                # triggers will be named like '{self.trigger}_{trigger}'.
                triggers = [f.__name__.removeprefix(f'{self.trigger}_').strip()] \
                         + aliases,
                callback = f, priv = priv,
                hidden = hidden, doc = f.__doc__
            ))

            return f
        return wrapper

# TODO: refactor help commands into some base ver
#       since they're all the same anyways lol.

# not sure if this should be in glob or not,
# trying to think of some use cases lol..
regular_commands = []
command_sets = [
    mp_commands := CommandSet('mp', 'Multiplayer commands.'),
    pool_commands := CommandSet('pool', 'Mappool commands.'),
    clan_commands := CommandSet('clan', 'Clan commands.')
]

glob.commands = {
    'regular': regular_commands,
    'sets': command_sets
}

def command(priv: Privileges, aliases: list[str] = [],
            hidden: bool = False) -> Callable:
    def wrapper(f: Callable):
        regular_commands.append(Command(
            callback = f,
            priv = priv,
            hidden = hidden,
            triggers = [f.__name__.strip('_')] + aliases,
            doc = f.__doc__
        ))

        return f
    return wrapper

""" User commands
# The commands below are not considered dangerous,
# and are granted to any unbanned players.
"""

@command(Privileges.Normal, aliases=['h'], hidden=True)
async def _help(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Show information of all documented commands the player can access."""
    prefix = glob.config.command_prefix
    l = ['Individual commands',
         '-----------']

    for cmd in regular_commands:
        if not cmd.doc or p.priv & cmd.priv != cmd.priv:
            # no doc, or insufficient permissions.
            continue

        l.append(f'{prefix}{cmd.triggers[0]}: {cmd.doc}')

    l.append('') # newline
    l.extend(['Command sets',
              '-----------'])

    for cmd_set in command_sets:
        l.append(f'{prefix}{cmd_set.trigger}: {cmd_set.doc}')

    return '\n'.join(l)

@command(Privileges.Normal)
async def roll(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Roll an n-sided die where n is the number you write (100 default)."""
    if msg and msg[0].isdecimal():
        max_roll = min(int(msg[0]), 0x7fff)
    else:
        max_roll = 100

    points = random.randrange(0, max_roll)
    return f'{p.name} rolls {points} points!'

@command(Privileges.Normal, aliases=['bloodcat', 'beatconnect', 'chimu', 'q'])
async def maplink(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Return a download link to the user's current map (situation dependant)."""
    bmap = None

    # priority: multiplayer -> spectator -> last np

    if p.match and p.match.map_id:
        bmap = await Beatmap.from_md5(p.match.map_md5)
    elif p.spectating and p.spectating.status.map_id:
        bmap = await Beatmap.from_md5(p.spectating.status.map_md5)
    elif time.time() < p.last_np['timeout']:
        bmap = p.last_np['bmap']
    else:
        return 'No map found!'

    return f'[https://chimu.moe/d/{bmap.set_id} {bmap.full}]'

@command(Privileges.Normal, aliases=['last', 'r'])
async def recent(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Show information about your most recent score."""
    if not (s := p.recent_score):
        return 'No scores found :o (only saves per play session)'

    l = [f'[{s.mode!r}] {s.bmap.embed}', f'{s.acc:.2f}%']

    if s.mods:
        l.insert(1, f'+{s.mods!r}')

    l = [' '.join(l)]

    if s.passed:
        rank = s.rank if s.status == SubmissionStatus.BEST else 'NA'
        l.append(f'PASS {{{s.pp:.2f}pp #{rank}}}')
    else:
        # XXX: prior to v3.2.0, gulag didn't parse total_length from
        # the osu!api, and thus this can do some zerodivision moments.
        # this can probably be removed in the future, or better yet
        # replaced with a better system to fix the maps.
        if s.bmap.total_length != 0:
            completion = s.time_elapsed / (s.bmap.total_length * 1000)
            l.append(f'FAIL {{{completion * 100:.2f}% complete}})')
        else:
            l.append('FAIL')

    return ' | '.join(l)

# TODO: !top (get top #1 score)
# TODO: !compare (compare to previous !last/!top post's map)

@command(Privileges.Normal, aliases=['w'], hidden=True)
async def _with(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Specify custom accuracy & mod combinations with `/np`."""
    if not glob.oppai_built:
        return 'No oppai-ng binary was found at startup.'

    if c is not glob.bot:
        return 'This command can only be used in DM with Aika.'

    if time.time() >= p.last_np['timeout']:
        return 'Please /np a map first!'

    if (mode_vn := p.last_np['mode_vn']) not in (0, 1):
        return 'PP not yet supported for that mode.'

    # +?<mods> <acc>%?
    if 1 < len(msg) > 2:
        return 'Invalid syntax: !with <mods/acc> ...'

    mods = acc = None

    for param in (p.strip('+%') for p in msg):
        if cmyui._isdecimal(param, _float=True):
            if not 0 <= (acc := float(param)) <= 100:
                return 'Invalid accuracy.'

        elif len(param) % 2 == 0:
            mods = Mods.from_modstr(param)
            mods = mods.filter_invalid_combos(mode_vn)
        else:
            return 'Invalid syntax: !with <mods/acc> ...'

    bmap = p.last_np['bmap']
    _msg = [bmap.embed]

    if not mods:
        mods = Mods.NOMOD

    _msg.append(f'{mods!r}')

    if acc:
        # custom accuracy specified, calculate it on the fly.
        ppcalc = await PPCalculator.from_id(
            map_id=bmap.id, acc=acc,
            mods=mods, mode_vn=mode_vn
        )
        if not ppcalc:
            return 'Could not retrieve map file.'

        pp, _ = await ppcalc.perform() # don't need sr
        pp_values = [(acc, pp)]
    else:
        # general accuracy values requested.
        if mods not in bmap.pp_cache:
            # cache
            await bmap.cache_pp(mods)

        pp_values = zip(
            (90, 95, 98, 99, 100),
            bmap.pp_cache[mods]
        )

    pp_msg = ' | '.join([f'{acc:.2f}%: {pp:.2f}pp'
                         for acc, pp in pp_values])
    return f"{' '.join(_msg)}: {pp_msg}"

@command(Privileges.Normal, aliases=['req'])
async def request(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Request a beatmap for nomination."""
    if msg:
        return 'Invalid syntax: !request'

    if time.time() >= p.last_np['timeout']:
        return 'Please /np a map first!'

    bmap = p.last_np['bmap']

    if bmap.status != RankedStatus.Pending:
        return 'Only pending maps may be requested for status change.'

    await glob.db.execute(
        'INSERT INTO map_requests '
        '(map_id, player_id, datetime, active) '
        'VALUES (%s, %s, NOW(), 1)',
        [bmap.id, p.id]
    )

    return 'Request submitted.'

""" Nominator commands
# The commands below allow users to
# manage  the server's state of beatmaps.
"""

@command(Privileges.Nominator, aliases=['reqs'], hidden=True)
async def requests(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Check the nomination request queue."""
    if msg:
        return 'Invalid syntax: !requests'

    res = await glob.db.fetchall(
        'SELECT map_id, player_id, datetime '
        'FROM map_requests WHERE active = 1',
        _dict=False # return rows as tuples
    )

    if not res:
        return 'The queue is clean! (0 map request(s))'

    l = [f'Total requests: {len(res)}']

    for (map_id, player_id, dt) in res:
        # find player & map for each row, and add to output.
        if not (p := await glob.players.get_ensure(id=player_id)):
            l.append(f'Failed to find requesting player ({player_id})?')
            continue

        if not (bmap := await Beatmap.from_bid(map_id)):
            l.append(f'Failed to find requested map ({map_id})?')
            continue

        l.append(f'[{p.embed} @ {dt:%b %d %I:%M%p}] {bmap.embed}.')

    return '\n'.join(l)

status_to_id = lambda s: {
    'unrank': 0,
    'rank': 2,
    'love': 5
}[s]
@command(Privileges.Nominator)
async def _map(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Changes the ranked status of the most recently /np'ed map."""
    if (
        len(msg) != 2 or
        msg[0] not in ('rank', 'unrank', 'love') or
        msg[1] not in ('set', 'map')
    ):
        return 'Invalid syntax: !map <rank/unrank/love> <map/set>'

    if time.time() >= p.last_np['timeout']:
        return 'Please /np a map first!'

    bmap = p.last_np['bmap']
    new_status = RankedStatus(status_to_id(msg[0]))

    if bmap.status == new_status:
        return f'{bmap.embed} is already {new_status!s}!'

    # update sql & cache based on scope
    # XXX: not sure if getting md5s from sql
    # for updating cache would be faster?
    # surely this will not scale as well..

    if msg[1] == 'set':
        # update whole set
        await glob.db.execute(
            'UPDATE maps SET status = %s, '
            'frozen = 1 WHERE set_id = %s',
            [new_status, bmap.set_id]
        )

        # select all map ids for clearing map requests.
        map_ids = [x[0] for x in await glob.db.fetchall(
            'SELECT id FROM maps '
            'WHERE set_id = %s',
            [bmap.set_id], _dict=False
        )]

        for cached in glob.cache['beatmap'].values():
            # not going to bother checking timeout
            if cached['map'].set_id == bmap.set_id:
                cached['map'].status = new_status

    else:
        # update only map
        await glob.db.execute(
            'UPDATE maps SET status = %s, '
            'frozen = 1 WHERE id = %s',
            [new_status, bmap.id]
        )

        map_ids = [bmap.id]

        for cached in glob.cache['beatmap'].values():
            # not going to bother checking timeout
            if cached['map'] is bmap:
                cached['map'].status = new_status
                break

    # deactivate rank requests for all ids
    for map_id in map_ids:
        await glob.db.execute(
            'UPDATE map_requests SET active = 0 '
            'WHERE map_id = %s', [map_id]
        )

    return f'{bmap.embed} updated to {new_status!s}.'

""" Mod commands
# The commands below are somewhat dangerous,
# and are generally for managing players.
"""

@command(Privileges.Mod, hidden=True)
async def notes(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Retrieve the logs of a specified player by name."""
    if len(msg) != 2 or not msg[1].isdecimal():
        return 'Invalid syntax: !notes <name> <days_back>'

    if not (t := await glob.players.get_ensure(name=msg[0])):
        return f'"{msg[0]}" not found.'

    days = int(msg[1])

    if days > 365:
        return 'Please contact a developer to fetch >365 day old information.'
    elif days <= 0:
        return 'Invalid syntax: !notes <name> <days_back>'

    res = await glob.db.fetchall(
        'SELECT `msg`, `time` '
        'FROM `logs` WHERE `to` = %s '
        'AND UNIX_TIMESTAMP(`time`) >= UNIX_TIMESTAMP(NOW()) - %s '
        'ORDER BY `time` ASC',
        [t.id, days * 86400]
    )

    if not res:
        return f'No notes found on {t} in the past {days} days.'

    return '\n'.join(map(lambda row: '[{time}] {msg}'.format(**row), res))

@command(Privileges.Mod, hidden=True)
async def addnote(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Add a note to a specified player by name."""
    if len(msg) < 2:
        return 'Invalid syntax: !addnote <name> <note ...>'

    if not (t := await glob.players.get_ensure(name=msg[0])):
        return f'"{msg[0]}" not found.'

    log_msg = f'{p} added note: {" ".join(msg[1:])}'

    await glob.db.execute(
        'INSERT INTO logs '
        '(`from`, `to`, `msg`, `time`) '
        'VALUES (%s, %s, %s, NOW())',
        [p.id, t.id, log_msg]
    )

    return f'Added note to {p}.'

# some shorthands that can be used as
# reasons in many moderative commands.
SHORTHAND_REASONS = {
    'aa': 'having their appeal accepted',
    'cc': 'using a modified osu! client',
    '3p': 'using 3rd party programs',
    'rx': 'using 3rd party programs (relax)',
    'tw': 'using 3rd party programs (timewarp)',
    'au': 'using 3rd party programs (auto play)',
    'dn': 'deez nuts'
}

@command(Privileges.Mod, hidden=True)
async def silence(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Silence a specified player with a specified duration & reason."""
    if len(msg) < 3:
        return 'Invalid syntax: !silence <name> <duration> <reason>'

    if not (t := await glob.players.get_ensure(name=msg[0])):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    if not (rgx := regexes.silence_duration.match(msg[1])):
        return 'Invalid syntax: !silence <name> <duration> <reason>'

    multiplier = {
        's': 1, 'm': 60, 'h': 3600,
        'd': 86400, 'w': 604800
    }[rgx['scale']]

    duration = int(rgx['duration']) * multiplier
    reason = ' '.join(msg[2:])

    if reason in SHORTHAND_REASONS:
        reason = SHORTHAND_REASONS[reason]

    await t.silence(p, duration, reason)
    return f'{t} was silenced.'

@command(Privileges.Mod, hidden=True)
async def unsilence(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Unsilence a specified player."""
    if len(msg) != 1:
        return 'Invalid syntax: !unsilence <name>'

    if not (t := await glob.players.get_ensure(name=msg[0])):
        return f'"{msg[0]}" not found.'

    if not t.silenced:
        return f'{t} is not silenced.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    await t.unsilence(p)
    return f'{t} was unsilenced.'

""" Admin commands
# The commands below are relatively dangerous,
# and are generally for managing players.
"""

@command(Privileges.Admin, hidden=True)
async def restrict(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Restrict a specified player's account, with a reason."""
    if len(msg) < 2:
        return 'Invalid syntax: !restrict <name> <reason>'

    # find any user matching (including offline).
    if not (t := await glob.players.get_ensure(name=msg[0])):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    if t.restricted:
        return f'{t} is already restricted!'

    reason = ' '.join(msg[1:])

    if reason in SHORTHAND_REASONS:
        reason = SHORTHAND_REASONS[reason]

    await t.restrict(admin=p, reason=reason)

    return f'{t} was restricted.'

@command(Privileges.Admin, hidden=True)
async def unrestrict(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Unrestrict a specified player's account, with a reason."""
    if len(msg) < 2:
        return 'Invalid syntax: !restrict <name> <reason>'

    # find any user matching (including offline).
    if not (t := await glob.players.get_ensure(name=msg[0])):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    if not t.restricted:
        return f'{t} is not restricted!'

    reason = ' '.join(msg[1:])

    if reason in SHORTHAND_REASONS:
        reason = SHORTHAND_REASONS[reason]

    await t.unrestrict(p, reason)

    return f'{t} was unrestricted.'

@command(Privileges.Admin, hidden=True)
async def alert(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Send a notification to all players."""
    if len(msg) < 1:
        return 'Invalid syntax: !alert <msg>'

    notif_txt = ' '.join(msg)

    glob.players.enqueue(packets.notification(notif_txt))
    return 'Alert sent.'

@command(Privileges.Admin, aliases=['alertu'], hidden=True)
async def alertuser(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Send a notification to a specified player by name."""
    if len(msg) < 2:
        return 'Invalid syntax: !alertu <name> <msg>'

    if not (t := glob.players.get(name=msg[0])):
        return 'Could not find a user by that name.'

    notif_txt = ' '.join(msg[1:])

    t.enqueue(packets.notification(notif_txt))
    return 'Alert sent.'

# NOTE: this is pretty useless since it doesn't switch anything other
# than the c[e4-6].ppy.sh domains; it exists on bancho as a tournament
# server switch mechanism, perhaps we could leverage this in the future.
@command(Privileges.Admin, hidden=True)
async def switchserv(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Switch your client's internal endpoints to a specified IP address."""
    if len(msg) != 1:
        return 'Invalid syntax: !switch <endpoint>'

    new_bancho_ip = msg[0]

    p.enqueue(packets.switchTournamentServer(new_bancho_ip))
    return 'Have a nice journey..'

""" Developer commands
# The commands below are either dangerous or
# simply not useful for any other roles.
"""

_fake_users = []
@command(Privileges.Dangerous, aliases=['fu'])
async def fakeusers(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Add a specified number of fake presences to the online player list."""
    # NOTE: this is mostly just for speedtesting things regarding presences/stats.
    # it's implementation is indeed quite cursed (for speed).
    if (
        len(msg) != 2 or
        msg[0] not in ('add', 'rm') or
        not msg[1].isdecimal()
    ):
        return 'Invalid syntax: !fakeusers <add/rm> <amount>'

    action = msg[0]
    amount = int(msg[1])
    if not 0 < amount <= 5000:
        return 'Amount must be in range 0-5000.'

    # we start at half way through
    # the i32 space for fake user ids.
    FAKE_ID_START = 0x7fffffff >> 1

    # data to send to clients (all new user info)
    # we'll send all the packets together at end (more efficient)
    data = bytearray()

    if action == 'add':
        const_uinfo = { # non important stuff
            'utc_offset': 0,
            'osu_ver': 'dn',
            'pm_private': False,
            'login_time': 0,
            'clan': None,
            'clan_priv': None,
            'priv': Privileges.Normal | Privileges.Verified,
            'silence_end': 0,
            'login_time': 0x7fffffff # never auto-dc
        }

        data = bytearray()
        _stats = packets.userStats(p)

        if _fake_users:
            current_fakes = max([x.id for x in _fake_users]) - (FAKE_ID_START - 1)
        else:
            current_fakes = 0

        start_id = FAKE_ID_START + current_fakes
        end_id = start_id + amount
        vn_std = GameMode.vn_std

        for i in range(start_id, end_id):
            name = f'fake #{i - (FAKE_ID_START - 1)}'
            fake = Player(id=i, name=name, **const_uinfo)

            # copy vn_std stats (just for rank lol, could optim)
            fake.stats[vn_std] = copy.copy(p.stats[vn_std])

            data += packets.userPresence(fake) # <- uses rank
            data += _stats

            glob.players.append(fake)
            _fake_users.append(fake)

        msg = 'Added.'
    else: # remove
        len_fake_users = len(_fake_users)
        if amount > len_fake_users:
            return f'Too many! only {len_fake_users} remaining.'

        to_remove = _fake_users[len_fake_users - amount:]
        data = bytearray()
        logout_packet_header = b'\x0c\x00\x00\x05\x00\x00\x00'

        for fake in to_remove:
            if not fake.online:
                # already auto-dced
                _fake_users.remove(fake)
                continue

            data += logout_packet_header
            data += fake.id.to_bytes(4, 'little') # 4 bytes pid
            data += b'\x00' # 1 byte 0

            glob.players.remove(fake)
            _fake_users.remove(fake)

        msg = 'Removed.'

    data = bytes(data) # bytearray -> bytes

    # only enqueue data to real users.
    for o in [x for x in glob.players if x.id < FAKE_ID_START]:
        o.enqueue(data)

    return msg

@command(Privileges.Dangerous)
async def stealth(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Toggle the developer's stealth, allowing them to be hidden."""
    # NOTE: this command is a large work in progress and currently
    # half works; eventually it will be moved to the Admin level.
    p.stealth = not p.stealth

    return f'Stealth {"enabled" if p.stealth else "disabled"}.'

@command(Privileges.Dangerous)
async def recalc(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Performs a full PP recalc on a specified map, or all maps."""
    if not glob.oppai_built:
        return 'No oppai-ng binary was found at startup.'

    if len(msg) != 1 or msg[0] not in ('map', 'all'):
        return 'Invalid syntax: !recalc <map/all>'

    score_counts = [] # keep track of # of scores recalced

    if msg[0] == 'map':
        # recalculate all scores on their last /np'ed map.
        if time.time() >= p.last_np['timeout']:
            return 'Please /np a map first!'

        if (mode_vn := p.last_np['mode_vn']) not in (0, 1):
            return 'PP not yet supported for that mode.'

        bmap = p.last_np['bmap']

        ppcalc = await PPCalculator.from_id(
            map_id=bmap.id, mode_vn=mode_vn
        )

        if not ppcalc:
            return 'Could not retrieve map file.'

        c.send_bot(f'Performing full recalc on {bmap.embed}.')

        for table in ('scores_vn', 'scores_rx', 'scores_ap'):
            # fetch all scores from the table on this map
            scores = await glob.db.fetchall(
                'SELECT id, acc, mods, max_combo, '
                'n300, n100, n50, nmiss, ngeki, nkatu '
                f'FROM {table} WHERE map_md5 = %s '
                'AND status = 2 AND mode = %s',
                [bmap.md5, mode_vn]
            )

            score_counts.append(len(scores))

            if not scores:
                continue

            for score in scores:
                ppcalc.mods = Mods(score['mods'])
                ppcalc.combo = score['max_combo']
                ppcalc.nmiss = score['nmiss']
                ppcalc.acc = score['acc']

                pp, _ = await ppcalc.perform() # sr not needed

                await glob.db.execute(
                    f'UPDATE {table} '
                    'SET pp = %s '
                    'WHERE id = %s',
                    [pp, score['id']]
                )

    else:
        # recalculate all scores on every map
        if not p.priv & Privileges.Dangerous:
            return 'This command is limited to developers.'

        return 'TODO'

    recap = '{0} vn | {1} rx | {2} ap'.format(*score_counts)
    return f'Recalculated {sum(score_counts)} ({recap}) scores.'

@command(Privileges.Dangerous, hidden=True)
async def debug(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Toggle the console's debug setting."""
    glob.config.debug = not glob.config.debug
    return f"Toggled {'on' if glob.config.debug else 'off'}."

# TODO: this command is rly bad, it probably
# shouldn't really be a command to begin with..
str_priv_dict = {
    'normal': Privileges.Normal,
    'verified': Privileges.Verified,
    'whitelisted': Privileges.Whitelisted,
    'supporter': Privileges.Supporter,
    'premium': Privileges.Premium,
    'alumni': Privileges.Alumni,
    'tournament': Privileges.Tournament,
    'nominator': Privileges.Nominator,
    'mod': Privileges.Mod,
    'admin': Privileges.Admin,
    'dangerous': Privileges.Dangerous
}
@command(Privileges.Dangerous, hidden=True)
async def setpriv(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Set privileges for a specified player (by name)."""
    if len(msg) < 2:
        return 'Invalid syntax: !setpriv <name> <role1 role2 role3 ...>'

    priv = Privileges(0)

    for m in [m.lower() for m in msg[1:]]:
        if m not in str_priv_dict:
            return f'Not found: {m}.'

        priv |= str_priv_dict[m]

    if not (t := await glob.players.get_ensure(name=msg[0])):
        return 'Could not find user.'

    await t.update_privs(priv)
    return f"Updated {t}'s privileges."

@command(Privileges.Dangerous)
async def wipemap(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    if msg:
        return 'Invalid syntax: !wipemap'

    if time.time() >= p.last_np['timeout']:
        return 'Please /np a map first!'

    map_md5 = p.last_np['bmap'].md5

    # delete scores from all tables
    for t in ('vn', 'rx', 'ap'):
        await glob.db.execute(
            f'DELETE FROM scores_{t} '
            'WHERE map_md5 = %s',
            [map_md5]
        )

    return 'Scores wiped.'

#@command(Privileges.Dangerous, aliases=['men'], hidden=True)
#async def menu_preview(p: Player, c: Messageable, msg: Sequence[str]) -> str:
#    """Temporary command to illustrate the menu option idea."""
#    async def callback():
#        # this is called when the menu item is clicked
#        p.enqueue(packets.notification('clicked!'))
#
#    # add the option to their menu opts & send them a button
#    opt_id = await p.add_to_menu(callback)
#    return f'[osump://{opt_id}/dn option]'

@command(Privileges.Dangerous, aliases=['re'])
async def reload(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Reload a python module."""
    if len(msg) != 1:
        return 'Invalid syntax: !reload <module>'

    parent, *children = msg[0].split('.')

    try:
        mod = __import__(parent)
    except ModuleNotFoundError:
        return 'Module not found.'

    try:
        for child in children:
            mod = getattr(mod, child)
    except AttributeError:
        return f'Failed at {child}.'

    mod = importlib.reload(mod)
    return f'Reloaded {mod.__name__}'

""" Advanced commands (only allowed with `advanced = True` in config) """

# NOTE: some of these commands are potentially dangerous, and only
# really intended for advanced users looking for access to lower level
# utilities. Some may give direct access to utilties that could perform
# harmful tasks to the underlying machine, so use at your own risk.

if glob.config.advanced:
    __py_namespace = globals() | {
        mod: __import__(mod) for mod in (
        'asyncio', 'dis', 'os', 'sys', 'struct', 'discord',
        'cmyui',  'datetime', 'time', 'inspect', 'math',
        'importlib'
    )}

    @command(Privileges.Dangerous)
    async def py(p: Player, c: Messageable, msg: Sequence[str]) -> str:
        """Allow for (async) access to the python interpreter."""
        # This can be very good for getting used to gulag's API; just look
        # around the codebase and find things to play with in your server.
        # Ex: !py return (await glob.players.get(name='cmyui')).status.action
        if not msg:
            return 'owo'

        # create the new coroutine definition as a string
        # with the lines from our message (split by '\n').
        lines = ' '.join(msg).split(r'\n')
        definition = '\n '.join(['async def __py(p, c, msg):'] + lines)

        try: # def __py(p, c, msg)
            exec(definition, __py_namespace)

            loop = asyncio.get_running_loop()

            try: # __py(p, c, msg)
                task = loop.create_task(__py_namespace['__py'](p, c, msg))
                ret = await asyncio.wait_for(asyncio.shield(task), 5.0)
            except asyncio.TimeoutError:
                ret = 'Left running (took >=5 sec).'

        except Exception as e:
            # code was invalid, return
            # the error in the osu! chat.
            ret = f'{e.__class__}: {e}'

        if '__py' in __py_namespace:
            del __py_namespace['__py']

        if ret is not None:
            return str(ret)
        else:
            return 'Success'

""" Multiplayer commands
# The commands below for multiplayer match management.
# Most commands are open to player usage.
"""

@mp_commands.add(Privileges.Normal, aliases=['h'])
async def mp_help(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Show information of all documented mp commands the player can access."""
    prefix = glob.config.command_prefix
    cmds = []

    for cmd in mp_commands.commands:
        if not cmd.doc or p.priv & cmd.priv != cmd.priv:
            # no doc, or insufficient permissions.
            continue

        cmds.append(f'{prefix}mp {cmd.triggers[0]}: {cmd.doc}')

    return '\n'.join(cmds)

@mp_commands.add(Privileges.Normal, aliases=['st'])
async def mp_start(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Start the current multiplayer match, with any players ready."""
    if (msg_len := len(msg)) > 1:
        return 'Invalid syntax: !mp start <force/seconds>'

    if msg_len == 1:
        if msg[0].isdecimal():
            # !mp start <seconds>
            duration = int(msg[0])
            if not 0 < duration <= 300:
                return 'Timer range is 1-300 seconds.'

            def _start():
                # make sure player didn't leave the
                # match since queueing this start lol..
                if p in m:
                    m.start()

            loop = asyncio.get_event_loop()
            loop.call_later(duration, _start)
            return f'Match will start in {duration} seconds.'
        elif msg[0] not in ('force', 'f'):
            return 'Invalid syntax: !mp start <force/seconds>'
        # !mp start force simply passes through
    else:
        # !mp start (no force or timer)
        if any(s.status == SlotStatus.not_ready for s in m.slots):
            return ('Not all players are ready '
                    '(use `!mp start force` to override).')

    m.start()
    return 'Good luck!'

@mp_commands.add(Privileges.Normal, aliases=['a'])
async def mp_abort(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Abort the current in-progress multiplayer match."""
    if not m.in_progress:
        return 'Abort what?'

    m.unready_players(expected=SlotStatus.playing)

    m.in_progress = False
    m.enqueue(packets.matchAbort())
    m.enqueue_state()
    return 'Match aborted.'

@mp_commands.add(Privileges.Normal)
async def mp_map(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Set the current match's current map by id."""
    if len(msg) != 1 or not msg[0].isdecimal():
        return 'Invalid syntax: !mp map <beatmapid>'

    if not (bmap := await Beatmap.from_bid(int(msg[0]))):
        return 'Beatmap not found.'

    m.map_id = bmap.id
    m.map_md5 = bmap.md5
    m.map_name = bmap.full

    m.mode = bmap.mode

    m.enqueue_state()
    return f'Selected: {bmap.embed}.'

@mp_commands.add(Privileges.Normal)
async def mp_mods(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Set the current match's mods, from string form."""
    if len(msg) != 1 or len(msg[0]) % 2 != 0:
        return 'Invalid syntax: !mp mods <mods>'

    mods = Mods.from_modstr(msg[0])
    mods = mods.filter_invalid_combos(m.mode.as_vanilla)

    if m.freemods:
        if p is m.host:
            # allow host to set speed-changing mods.
            m.mods = mods & SPEED_CHANGING_MODS

        # set slot mods
        m.get_slot(p).mods = mods & ~SPEED_CHANGING_MODS
    else:
        # not freemods, set match mods.
        m.mods = mods

    m.enqueue_state()
    return 'Match mods updated.'

@mp_commands.add(Privileges.Normal, aliases=['fm', 'fmods'])
async def mp_freemods(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Toggle freemods status for the match."""
    if len(msg) != 1 or msg[0] not in ('on', 'off'):
        return 'Invalid syntax: !mp freemods <on/off>'

    if msg[0] == 'on':
        # central mods -> all players mods.
        m.freemods = True

        for s in m.slots:
            if s.status & SlotStatus.has_player:
                # the slot takes any non-speed
                # changing mods from the match.
                s.mods = m.mods & ~SPEED_CHANGING_MODS

        m.mods &= SPEED_CHANGING_MODS
    else:
        # host mods -> central mods.
        m.freemods = False

        host = m.get_host_slot() # should always exist
        # the match keeps any speed-changing mods,
        # and also takes any mods the host has enabled.
        m.mods &= SPEED_CHANGING_MODS
        m.mods |= host.mods

        for s in m.slots:
            if s.status & SlotStatus.has_player:
                s.mods = Mods.NOMOD

    m.enqueue_state()
    return 'Match freemod status updated.'

@mp_commands.add(Privileges.Normal)
async def mp_host(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Set the current match's current host by id."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp host <name>'

    if not (t := glob.players.get(name=msg[0])):
        return 'Could not find a user by that name.'

    if t is m.host:
        return "They're already host, silly!"

    if t not in m:
        return 'Found no such player in the match.'

    m.host = t
    m.host.enqueue(packets.matchTransferHost())
    m.enqueue_state(lobby=False)
    return 'Match host updated.'

@mp_commands.add(Privileges.Normal)
async def mp_randpw(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Randomize the current match's password."""
    m.passwd = cmyui.rstring(16)
    return 'Match password randomized.'

@mp_commands.add(Privileges.Normal, aliases=['inv'])
async def mp_invite(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Invite a player to the current match by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp invite <name>'

    if not (t := glob.players.get(name=msg[0])):
        return 'Could not find a user by that name.'
    elif t is glob.bot:
        p.send("I'm too busy!", sender=glob.bot)
        return

    if p is t:
        return "You can't invite yourself!"

    t.enqueue(packets.matchInvite(p, t.name))
    return f'Invited {t} to the match.'

@mp_commands.add(Privileges.Normal)
async def mp_addref(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Add a referee to the current match by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp addref <name>'

    if not (t := glob.players.get(name=msg[0])):
        return 'Could not find a user by that name.'

    if t not in m:
        return 'User must be in the current match!'

    if t in m.refs:
        return f'{t} is already a match referee!'

    m._refs.add(t)
    return 'Match referees updated.'

@mp_commands.add(Privileges.Normal)
async def mp_rmref(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Remove a referee from the current match by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp addref <name>'

    if not (t := glob.players.get(name=msg[0])):
        return 'Could not find a user by that name.'

    if t not in m.refs:
        return f'{t} is not a match referee!'

    if t is m.host:
        return 'The host is always a referee!'

    m._refs.remove(t)
    return 'Match referees updated.'

@mp_commands.add(Privileges.Normal)
async def mp_listref(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """List all referees from the current match."""
    return ', '.join(map(str, m.refs)) + '.'

@mp_commands.add(Privileges.Normal)
async def mp_lock(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Lock all unused slots in the current match."""
    for slot in m.slots:
        if slot.status == SlotStatus.open:
            slot.status = SlotStatus.locked

    m.enqueue_state()
    return 'All unused slots locked.'

@mp_commands.add(Privileges.Normal)
async def mp_unlock(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Unlock locked slots in the current match."""
    for slot in m.slots:
        if slot.status == SlotStatus.locked:
            slot.status = SlotStatus.open

    m.enqueue_state()
    return 'All locked slots unlocked.'

@mp_commands.add(Privileges.Normal)
async def mp_teams(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Change the team type for the current match."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp teams <type>'

    team_type = msg[0]

    if team_type in ('ffa', 'freeforall', 'head-to-head'):
        m.team_type = MatchTeamTypes.head_to_head
    elif team_type in ('tag', 'coop', 'co-op', 'tag-coop'):
        m.team_type = MatchTeamTypes.tag_coop
    elif team_type in ('teams', 'team-vs', 'teams-vs'):
        m.team_type = MatchTeamTypes.team_vs
    elif team_type in ('tag-teams', 'tag-team-vs', 'tag-teams-vs'):
        m.team_type = MatchTeamTypes.tag_team_vs
    else:
        return 'Unknown team type. (ffa, tag, teams, tag-teams)'

    # find the new appropriate default team.
    # defaults are (ffa: neutral, teams: red).
    if m.team_type in (MatchTeamTypes.head_to_head,
                       MatchTeamTypes.tag_coop):
        new_t = MatchTeams.neutral
    else:
        new_t = MatchTeams.red

    # change each active slots team to
    # fit the correspoding team type.
    for s in m.slots:
        if s.status & SlotStatus.has_player:
            s.team = new_t

    if m.is_scrimming:
        # reset score if scrimming.
        m.reset_scrim()

    m.enqueue_state()
    return 'Match team type updated.'

@mp_commands.add(Privileges.Normal, aliases=['cond'])
async def mp_condition(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Change the win condition for the match."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp condition <type>'

    cond = msg[0]

    if cond == 'pp':
        # special case - pp can't actually be used as an ingame
        # win condition, but gulag allows it to be passed into
        # this command during a scrims to use pp as a win cond.
        if not m.is_scrimming:
            return 'PP is only useful as a win condition during scrims.'
        if m.use_pp_scoring:
            return 'PP scoring already enabled.'

        m.use_pp_scoring = True
    else:
        if m.use_pp_scoring:
            m.use_pp_scoring = False

        if cond == 'score':
            m.win_condition = MatchWinConditions.score
        elif cond in ('accuracy', 'acc'):
            m.win_condition = MatchWinConditions.accuracy
        elif cond == 'combo':
            m.win_condition = MatchWinConditions.combo
        elif cond in ('scorev2', 'v2'):
            m.win_condition = MatchWinConditions.scorev2
        else:
            return 'Invalid win condition. (score, acc, combo, scorev2, *pp)'

    m.enqueue_state(lobby=False)
    return 'Match win condition updated.'

@mp_commands.add(Privileges.Normal)
async def mp_scrim(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Start a scrim in the current match."""
    if (
        len(msg) != 1 or
        not (rgx := re.fullmatch(r'^(?:bo)?(\d{1,2})$', msg[0]))
    ):
        return 'Invalid syntax: !mp scrim <bo#>'

    if not 0 <= (best_of := int(rgx[1])) < 16:
        return 'Best of must be in range 0-15.'

    winning_pts = (best_of // 2) + 1

    if winning_pts != 0:
        # setting to real num
        if m.is_scrimming:
            return 'Already scrimming!'

        if best_of % 2 == 0:
            return 'Best of must be an odd number!'

        m.is_scrimming = True
        msg = (f'A scrimmage has been started by {p.name}; '
               f'first to {winning_pts} points wins. Best of luck!')
    else:
        # setting to 0
        if not m.is_scrimming:
            return 'Not currently scrimming!'

        m.is_scrimming = False
        m.reset_scrim()
        msg = 'Scrimming cancelled.'

    m.winning_pts = winning_pts
    return msg

@mp_commands.add(Privileges.Normal, aliases=['end'])
async def mp_endscrim(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """End the current matches ongoing scrim."""
    if not m.is_scrimming:
        return 'Not currently scrimming!'

    m.is_scrimming = False
    m.reset_scrim()
    return 'Scrimmage ended.' # TODO: final score (get_score method?)

@mp_commands.add(Privileges.Normal, aliases=['rm'])
async def mp_rematch(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Restart a scrim with the previous match points, """ \
    """or roll back the most recent match point."""
    if msg:
        return 'Invalid syntax: !mp rematch'

    if p is not m.host:
        return 'Only available to the host.'

    if not m.is_scrimming:
        if m.winning_pts == 0:
            msg = 'No scrim to rematch; to start one, use !mp scrim.'
        else:
            # re-start scrimming with old points
            m.is_scrimming = True
            msg = (f'A rematch has been started by {p.name}; '
                f'first to {m.winning_pts} points wins. Best of luck!')
    else:
        # reset the last match point awarded
        if not m.winners:
            return "No match points have yet been awarded!"

        if (recent_winner := m.winners[-1]) is None:
            return 'The last point was a tie!'

        m.match_points[recent_winner] -= 1 # TODO: team name
        m.winners.pop()

        msg = f'A point has been deducted from {recent_winner}.'

    return msg

@mp_commands.add(Privileges.Admin, aliases=['f'], hidden=True)
async def mp_force(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Force a player into the current match by name."""
    # NOTE: this overrides any limits such as silences or passwd.
    if len(msg) != 1:
        return 'Invalid syntax: !mp force <name>'

    if not (t := glob.players.get(name=msg[0])):
        return 'Could not find a user by that name.'

    t.join_match(m, m.passwd)
    return 'Welcome.'

# mappool-related mp commands

@mp_commands.add(Privileges.Normal, aliases=['lp'])
async def mp_loadpool(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Load a mappool into the current match."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp loadpool <name>'

    if p is not m.host:
        return 'Only available to the host.'

    name = msg[0]

    if not (pool := glob.pools.get(name)):
        return 'Could not find a pool by that name!'

    if m.pool is pool:
        return f'{pool!r} already selected!'

    m.pool = pool
    return f'{pool!r} selected.'

@mp_commands.add(Privileges.Normal, aliases=['ulp'])
async def mp_unloadpool(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Unload the current matches mappool."""
    if msg:
        return 'Invalid syntax: !mp unloadpool'

    if p is not m.host:
        return 'Only available to the host.'

    if not m.pool:
        return 'No mappool currently selected!'

    m.pool = None
    return 'Mappool unloaded.'

@mp_commands.add(Privileges.Normal)
async def mp_ban(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Ban a pick in the currently loaded mappool."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp ban <pick>'

    if not m.pool:
        return 'No pool currently selected!'

    mods_slot = msg[0]

    # separate mods & slot
    if not (rgx := regexes.mappool_pick.fullmatch(mods_slot)):
        return 'Invalid pick syntax; correct example: HD2'

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(rgx[1])
    slot = int(rgx[2])

    if (mods, slot) not in m.pool.maps:
        return f'Found no {mods_slot} pick in the pool.'

    if (mods, slot) in m.bans:
        return 'That pick is already banned!'

    m.bans.add((mods, slot))
    return f'{mods_slot} banned.'

@mp_commands.add(Privileges.Normal)
async def mp_unban(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Unban a pick in the currently loaded mappool."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp unban <pick>'

    if not m.pool:
        return 'No pool currently selected!'

    mods_slot = msg[0]

    # separate mods & slot
    if not (rgx := regexes.mappool_pick.fullmatch(mods_slot)):
        return 'Invalid pick syntax; correct example: HD2'

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(rgx[1])
    slot = int(rgx[2])

    if (mods, slot) not in m.pool.maps:
        return f'Found no {mods_slot} pick in the pool.'

    if (mods, slot) not in m.bans:
        return 'That pick is not currently banned!'

    m.bans.remove((mods, slot))
    return f'{mods_slot} unbanned.'

@mp_commands.add(Privileges.Normal)
async def mp_pick(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Pick a map from the currently loaded mappool."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp pick <pick>'

    if not m.pool:
        return 'No pool currently loaded!'

    mods_slot = msg[0]

    # separate mods & slot
    if not (rgx := regexes.mappool_pick.fullmatch(mods_slot)):
        return 'Invalid pick syntax; correct example: HD2'

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(rgx[1])
    slot = int(rgx[2])

    if (mods, slot) not in m.pool.maps:
        return f'Found no {mods_slot} pick in the pool.'

    if (mods, slot) in m.bans:
        return f'{mods_slot} has been banned from being picked.'

    # update match beatmap to the picked map.
    bmap = m.pool.maps[(mods, slot)]
    m.map_md5 = bmap.md5
    m.map_id = bmap.id
    m.map_name = bmap.full

    # TODO: some kind of abstraction allowing
    # for something like !mp pick fm.
    if m.freemods:
        # if freemods are enabled, disable them.
        m.freemods = False

        for s in m.slots:
            if s.status & SlotStatus.has_player:
                s.mods = Mods.NOMOD

    # update match mods to the picked map.
    m.mods = mods

    m.enqueue_state()

    return f'Picked {bmap.embed}. ({mods_slot})'

""" Mappool management commands
# The commands below are for event managers
# and tournament hosts/referees to help automate
# tedious processes of running tournaments.
"""

@pool_commands.add(Privileges.Tournament, aliases=['h'], hidden=True)
async def pool_help(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Show information of all documented pool commands the player can access."""
    prefix = glob.config.command_prefix
    cmds = []

    for cmd in pool_commands.commands:
        if not cmd.doc or p.priv & cmd.priv != cmd.priv:
            # no doc, or insufficient permissions.
            continue

        cmds.append(f'{prefix}pool {cmd.triggers[0]}: {cmd.doc}')

    return '\n'.join(cmds)

@pool_commands.add(Privileges.Tournament, aliases=['c'], hidden=True)
async def pool_create(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Add a new mappool to the database."""
    if len(msg) != 1:
        return 'Invalid syntax: !pool create <name>'

    name = msg[0]

    if glob.pools.get(name):
        return 'Pool already exists by that name!'

    # insert pool into db
    await glob.db.execute(
        'INSERT INTO tourney_pools '
        '(name, created_at, created_by) '
        'VALUES (%s, NOW(), %s)',
        [name, p.id]
    )

    # add to cache (get from sql for id & time)
    res = await glob.db.fetch('SELECT * FROM tourney_pools '
                              'WHERE name = %s', [name])

    glob.pools.append(MapPool(**res))

    return f'{name} created.'

@pool_commands.add(Privileges.Tournament, aliases=['del', 'd'], hidden=True)
async def pool_delete(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Remove a mappool from the database."""
    if len(msg) != 1:
        return 'Invalid syntax: !pool delete <name>'

    name = msg[0]

    if not (pool := glob.pools.get(name)):
        return 'Could not find a pool by that name!'

    # delete from db
    await glob.db.execute(
        'DELETE FROM tourney_pools '
        'WHERE name = %s',
        [name]
    )

    # remove from cache
    glob.pools.remove(pool)

    return f'{name} deleted.'

@pool_commands.add(Privileges.Tournament, aliases=['a'], hidden=True)
async def pool_add(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Add a new map to a mappool in the database."""
    if len(msg) != 2:
        return 'Invalid syntax: !pool add <name> <pick>'

    if time.time() >= p.last_np['timeout']:
        return 'Please /np a map first!'

    name, mods_slot = msg
    mods_slot = mods_slot.upper() # ocd
    bmap = p.last_np['bmap']

    # separate mods & slot
    if not (rgx := regexes.mappool_pick.fullmatch(mods_slot)):
        return 'Invalid pick syntax; correct example: HD2'

    if len(rgx[1]) % 2 != 0:
        return 'Invalid mods.'

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(rgx[1])
    slot = int(rgx[2])

    if not (pool := glob.pools.get(name)):
        return 'Could not find a pool by that name!'

    if (mods, slot) in pool.maps:
        return f'{mods_slot} is already {pool.maps[(mods, slot)].embed}!'

    if bmap in pool.maps.values():
        return f'Map is already in the pool!'

    # insert into db
    await glob.db.execute(
        'INSERT INTO tourney_pool_maps '
        '(map_id, pool_id, mods, slot) '
        'VALUES (%s, %s, %s, %s)',
        [bmap.id, pool.id, mods, slot]
    )

    # add to cache
    pool.maps[(mods, slot)] = bmap

    return f'{bmap.embed} added to {name}.'

@pool_commands.add(Privileges.Tournament, aliases=['rm', 'r'], hidden=True)
async def pool_remove(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Remove a map from a mappool in the database."""
    if len(msg) != 2:
        return 'Invalid syntax: !pool remove <name> <pick>'

    name, mods_slot = msg
    mods_slot = mods_slot.upper() # ocd

    # separate mods & slot
    if not (rgx := regexes.mappool_pick.fullmatch(mods_slot)):
        return 'Invalid pick syntax; correct example: HD2'

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(rgx[1])
    slot = int(rgx[2])

    if not (pool := glob.pools.get(name)):
        return 'Could not find a pool by that name!'

    if (mods, slot) not in pool.maps:
        return f'Found no {mods_slot} pick in the pool.'

    # delete from db
    await glob.db.execute(
        'DELETE FROM tourney_pool_maps '
        'WHERE mods = %s AND slot = %s',
        [mods, slot]
    )

    # remove from cache
    del pool.maps[(mods, slot)]

    return f'{mods_slot} removed from {name}.'

@pool_commands.add(Privileges.Tournament, aliases=['l'], hidden=True)
async def pool_list(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """List all existing mappools information."""
    if not (pools := glob.pools):
        return 'There are currently no pools!'

    l = [f'Mappools ({len(pools)})']

    for pool in pools:
        l.append(f'[{pool.created_at:%Y-%m-%d}] {pool.id}. {pool.name}, by {pool.created_by}.')

    return '\n'.join(l)

@pool_commands.add(Privileges.Tournament, aliases=['i'], hidden=True)
async def pool_info(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Get all information for a specific mappool."""
    if len(msg) != 1:
        return 'Invalid syntax: !pool info <name>'

    name = msg[0]

    if not (pool := glob.pools.get(name)):
        return 'Could not find a pool by that name!'

    _time = pool.created_at.strftime('%H:%M:%S%p')
    _date = pool.created_at.strftime('%Y-%m-%d')
    datetime_fmt = f'Created at {_time} on {_date}'
    l = [f'{pool.id}. {pool.name}, by {pool.created_by} | {datetime_fmt}.']

    for (mods, slot), bmap in pool.maps.items():
        l.append(f'{mods!r}{slot}: {bmap.embed}')

    return '\n'.join(l)

""" Clan managment commands
# The commands below are for managing gulag
# clans, for users, clan staff, and server staff.
"""

@clan_commands.add(Privileges.Normal, aliases=['h'])
async def clan_help(p: Player, m: 'Match', msg: Sequence[str]) -> str:
    """Show information of all documented clan commands the player can access."""
    prefix = glob.config.command_prefix
    cmds = []

    for cmd in clan_commands.commands:
        if not cmd.doc or p.priv & cmd.priv != cmd.priv:
            # no doc, or insufficient permissions.
            continue

        cmds.append(f'{prefix}clan {cmd.triggers[0]}: {cmd.doc}')

    return '\n'.join(cmds)

@clan_commands.add(Privileges.Normal, aliases=['c'])
async def clan_create(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Create a clan with a given tag & name."""
    if len(msg) < 2:
        return 'Invalid syntax: !clan create <tag> <name>'

    if not 1 <= len(tag := msg[0].upper()) <= 6:
        return 'Clan tag may be 1-6 characters long.'

    if not 2 <= len(name := ' '.join(msg[1:])) <= 16:
        return 'Clan name may be 2-16 characters long.'

    if p.clan:
        return f"You're already a member of {p.clan}!"

    if glob.clans.get(name=name):
        return 'That name has already been claimed by another clan.'

    if glob.clans.get(tag=tag):
        return 'That tag has already been claimed by another clan.'

    created_at = datetime.now()

    # add clan to sql (generates id)
    id = await glob.db.execute(
        'INSERT INTO clans '
        '(name, tag, created_at, owner) '
        'VALUES (%s, %s, %s, %s)',
        [name, tag, created_at, p.id]
    )

    # add clan to cache
    clan = Clan(id=id, name=name, tag=tag,
                created_at=created_at, owner=p.id)
    glob.clans.append(clan)

    # set owner's clan & clan rank (cache & sql)
    p.clan = clan
    p.clan_priv = ClanPrivileges.Owner

    clan.owner = p.id
    clan.members.add(p.id)

    if 'full_name' in p.__dict__:
        del p.full_name # wipe cached_property

    await glob.db.execute(
        'UPDATE users '
        'SET clan_id = %s, '
        'clan_priv = 3 ' # ClanPrivileges.Owner
        'WHERE id = %s',
        [id, p.id]
    )

    # TODO: take currency from player

    # announce clan creation
    if announce_chan := glob.channels['#announce']:
        msg = f'\x01ACTION founded {clan!r}.'
        announce_chan.send(msg, sender=p, to_self=True)

    return f'{clan!r} created.'

@clan_commands.add(Privileges.Normal, aliases=['delete', 'd'])
async def clan_disband(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Disband a clan (admins may disband others clans)."""
    if msg:
        # disband a specified clan by tag
        if p not in glob.players.staff:
            return 'Only staff members may disband the clans of others.'

        if not (clan := glob.clans.get(tag=' '.join(msg).upper())):
            return 'Could not find a clan by that tag.'
    else:
        # disband the player's clan
        if not (clan := p.clan):
            return "You're not a member of a clan!"

    # delete clan from sql
    await glob.db.execute(
        'DELETE FROM clans '
        'WHERE id = %s',
        [clan.id]
    )

    # remove all members from the clan,
    # reset their clan rank (cache & sql).
    # NOTE: only online players need be to be uncached.
    for m in [glob.players.get(id=p_id) for p_id in clan.members]:
        if 'full_name' in m.__dict__:
            del m.full_name # wipe cached_property

        m.clan = m.clan_priv = None

    await glob.db.execute(
        'UPDATE users '
        'SET clan_id = 0, '
        'clan_priv = 0 '
        'WHERE clan_id = %s',
        [clan.id]
    )

    # remove clan from cache
    glob.clans.remove(clan)

    # announce clan disbanding
    if announce_chan := glob.channels['#announce']:
        msg = f'\x01ACTION disbanded {clan!r}.'
        announce_chan.send(msg, sender=p, to_self=True)

    return f'{clan!r} disbanded.'

@clan_commands.add(Privileges.Normal, aliases=['i'])
async def clan_info(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Lookup information of a clan by tag."""
    if not msg:
        return 'Invalid syntax: !clan info <tag>'

    if not (clan := glob.clans.get(tag=' '.join(msg).upper())):
        return 'Could not find a clan by that tag.'

    owner = await glob.players.get_ensure(id=clan.owner)

    _time = clan.created_at.strftime('%H:%M:%S%p')
    _date = clan.created_at.strftime('%Y-%m-%d')
    datetime_fmt = f'Founded at {_time} on {_date}'
    msg = [f"{owner.embed}'s {clan!r} | {datetime_fmt}."]

    # get members ranking from sql
    res = await glob.db.fetchall(
        'SELECT name, clan_priv '
        'FROM users '
        'WHERE clan_id = %s',
        [clan.id], _dict=False
    )

    for name, clan_priv in sorted(res, key=lambda row: row[1]):
        rank_str = ('Member', 'Officer', 'Owner')[clan_priv - 1]
        msg.append(f'[{rank_str}] {name}')

    return '\n'.join(msg)

# TODO: !clan inv, !clan join, !clan leave

@clan_commands.add(Privileges.Normal, aliases=['l'])
async def clan_list(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """List all existing clans information."""
    if msg:
        if len(msg) != 1 or not msg[0].isdecimal():
            return 'Invalid syntax: !clan list (page)'
        else:
            offset = 25 * int(msg[0])
    else:
        offset = 0

    if offset >= (total_clans := len(glob.clans)):
        return 'No clans found.'

    msg = [f'gulag clans listing ({total_clans} total).']

    for idx, clan in enumerate(glob.clans, offset):
        msg.append(f'{idx + 1}. {clan!r}')

    return '\n'.join(msg)

async def process_commands(p: Player, t: Messageable,
                           msg: str) -> Optional[CommandResponse]:
    # response is either a CommandResponse if we hit a command,
    # or simply False if we don't have any command hits.
    start_time = clock_ns()
    trigger, *args = msg[len(glob.config.command_prefix):].strip().split(' ')

    # case-insensitive triggers
    trigger = trigger.lower()

    for cmd_set in command_sets:
        # check if any command sets match.
        if trigger == cmd_set.trigger:
            # matching set found;
            if not args:
                args = ['help']

            if trigger == 'mp':
                # multi set is a bit of a special case,
                # as we do some additional checks.
                if not (m := p.match):
                    # player not in a match
                    return

                if t is not m.chat:
                    # message not in match channel
                    return

                if args[0] != 'help' and (p not in m.refs and
                                          not p.priv & Privileges.Tournament):
                    # doesn't have privs to use !mp commands (allow help).
                    return

                t = m # send match for mp commands instead of chan

            trigger, *args = args # get subcommand

            # case-insensitive triggers
            trigger = trigger.lower()

            commands = cmd_set.commands
            break
    else:
        # no set commands matched, check normal commands.
        commands = regular_commands

    for cmd in commands:
        if trigger in cmd.triggers and p.priv & cmd.priv == cmd.priv:
            # command found & we have privileges, run it.
            if res := await cmd.callback(p, t, args):
                ms_taken = (clock_ns() - start_time) / 1e6

                return {
                    'resp': f'{res} | Elapsed: {ms_taken:.2f}ms',
                    'hidden': cmd.hidden
                }

            return {'hidden': False}
