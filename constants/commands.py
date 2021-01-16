# -*- coding: utf-8 -*-

import asyncio
from typing import (NamedTuple, Sequence, Optional,
                    Union, Callable, TYPE_CHECKING)
import time
import re
import cmyui
import random
from datetime import datetime
from collections import defaultdict

import packets

from constants.privileges import Privileges
from constants.mods import Mods
from constants import regexes

from objects import glob
from objects.clan import Clan, ClanRank
from objects.score import SubmissionStatus
from objects.beatmap import Beatmap, RankedStatus
from objects.match import (MapPool, MatchWinConditions,
                           MatchTeamTypes, SlotStatus, MatchTeams)

from utils.recalculator import PPCalculator

if TYPE_CHECKING:
    from objects.channel import Channel
    from objects.player import Player
    from objects.match import Match

Messageable = Union['Channel', 'Player']
CommandResponse = dict[str, str]

class Command(NamedTuple):
    triggers: list[str]
    callback: Callable
    priv: Privileges
    hidden: bool
    doc: str

class CommandSet:
    __slots__ = ('commands', 'trigger')

    def __init__(self, trigger: str) -> None:
        self.trigger = trigger
        self.commands: list[Command] = []

    def add(self, priv: Privileges, other_triggers: list[str] = [],
            hidden: bool = False) -> Callable:
        def wrapper(f: Callable):
            self.commands.append(Command(
                # NOTE: this method assumes that functions without any
                # triggers will be named like '{self.trigger}_{trigger}'.
                triggers = [f.__name__.removeprefix(f'{self.trigger}_').strip()] \
                         + other_triggers,
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
mp_commands = CommandSet('mp')
pool_commands = CommandSet('pool')
clan_commands = CommandSet('clan')

glob.commands = {
    'regular': regular_commands,
    'sets': [mp_commands, pool_commands,
             clan_commands]
}

regular_commands = glob.commands['regular']
def command(priv: Privileges, other_triggers: list[str] = [],
            hidden: bool = False) -> Callable:
    def wrapper(f: Callable):
        regular_commands.append(Command(
            callback = f,
            priv = priv,
            hidden = hidden,
            triggers = [f.__name__.strip('_')] + other_triggers,
            doc = f.__doc__
        ))

        return f
    return wrapper

""" User commands
# The commands below are not considered dangerous,
# and are granted to any unbanned players.
"""

@command(Privileges.Normal, other_triggers=['h'], hidden=True)
async def _help(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Show information of all documented commands the player can access."""
    prefix = glob.config.command_prefix
    cmds = []

    for cmd in glob.commands['regular']:
        if not cmd.doc or not p.priv & cmd.priv:
            # no doc, or insufficient permissions.
            continue

        cmds.append(f'{prefix}{cmd.triggers[0]}: {cmd.doc}')

    return '\n'.join(cmds)

@command(Privileges.Normal)
async def roll(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Roll an n-sided die where n is the number you write (100 default)."""
    if msg and msg[0].isdecimal():
        max_roll = min(int(msg[0]), 0x7fff)
    else:
        max_roll = 100

    points = random.randrange(0, max_roll)
    return f'{p.name} rolls {points} points!'

# TODO: prolly beatconnect
@command(Privileges.Normal, other_triggers=['bc'])
async def bloodcat(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Return a bloodcat link of the user's current map (situation dependant)."""
    bmap = None

    # priority: multiplayer -> spectator -> last np

    if p.match and p.match.map_id:
        bmap = await Beatmap.from_md5(p.match.map_md5)
    elif p.spectating and p.spectating.status.map_id:
        bmap = await Beatmap.from_md5(p.spectating.status.map_md5)
    elif p.last_np:
        bmap = p.last_np
    else:
        return 'No map found!'

    return f'[https://bloodcat.com/d/{bmap.set_id} {bmap.full}]'

@command(Privileges.Normal, other_triggers=['recent'])
async def last(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
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
        completion = s.time_elapsed / (s.bmap.total_length * 1000)
        l.append(f'FAIL {{{completion * 100:.2f}% complete}})')

    return ' | '.join(l)

# TODO: !top (get top #1 score)
# TODO: !compare (compare to previous !last/!top post's map)

_mapsearch_fmt = (
    '[https://osu.ppy.sh/b/{id} {artist} - {title} [{version}]] '
    '([{mirror}/d/{set_id} download])'
)
_mapsearch_func = lambda row: _mapsearch_fmt.format(**row, mirror=glob.config.mirror)
@command(Privileges.Normal, hidden=True)
async def mapsearch(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Search map titles with user input as a wildcard."""
    if not msg:
        return 'Invalid syntax: !mapsearch <title>'

    if not (res := await glob.db.fetchall(
        'SELECT id, set_id, artist, title, version '
        'FROM maps WHERE title LIKE %s LIMIT 25',
        [f'%{" ".join(msg)}%']
    )): return 'No matches found :('

    return '\n'.join(map(_mapsearch_func, res)) + f'\nMaps: {len(res)}'

@command(Privileges.Normal, hidden=True)
async def _with(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Specify custom accuracy & mod combinations with `/np`."""
    if c is not glob.bot:
        return 'This command can only be used in DM with Aika.'

    if not p.last_np:
        return 'Please /np a map first!'

    # +?<mods> <acc>%?
    if 1 < len(msg) > 2:
        return 'Invalid syntax: !with <mods/acc> ...'

    mods = acc = None

    for param in (p.strip('+%') for p in msg):
        if cmyui._isdecimal(param, _float=True):
            if not 0 <= (acc := float(param)) <= 100:
                return 'Invalid accuracy.'

        elif ~len(param) & 1: # len(param) % 2 == 0
            mods = Mods.from_str(param)
        else:
            return 'Invalid syntax: !with <mods/acc> ...'

    _msg = [p.last_np.embed]
    if not mods:
        mods = Mods.NOMOD

    _msg.append(f'{mods!r}')

    if acc:
        # custom accuracy specified, calculate it on the fly.
        ppcalc = await PPCalculator.from_id(p.last_np.id, acc=acc, mods=mods)
        if not ppcalc:
            return 'Could not retrieve map file.'

        pp, _ = await ppcalc.perform() # don't need sr
        pp_values = [(acc, pp)]
    else:
        # general accuracy values requested.
        if mods not in p.last_np.pp_cache:
            # cache
            await p.last_np.cache_pp(mods)

        pp_values = zip(
            (90, 95, 98, 99, 100),
            p.last_np.pp_cache[mods]
        )

    pp_msg = ' | '.join(f'{acc:.2f}%: {pp:.2f}pp'
                        for acc, pp in pp_values)
    return f"{' '.join(_msg)}: {pp_msg}"

""" Nominators commands
# The commands below allow users to
# manage  the server's state of beatmaps.
"""

status_to_id = lambda s: {
    'unrank': 0,
    'rank': 2,
    'love': 5
}[s]
@command(Privileges.Nominator)
async def _map(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Changes the ranked status of the most recently /np'ed map."""
    if len(msg) != 2 or msg[0] not in ('rank', 'unrank', 'love') \
                     or msg[1] not in ('set', 'map'):
        return 'Invalid syntax: !map <rank/unrank/love> <map/set>'

    if not p.last_np:
        return 'You must /np a map first!'

    new_status = status_to_id(msg[0])

    # update sql & cache based on scope
    # XXX: not sure if getting md5s from sql
    # for updating cache would be faster?
    # surely this will not scale as well..

    if msg[1] == 'set':
        # update whole set
        await glob.db.execute(
            'UPDATE maps SET status = %s, '
            'frozen = 1 WHERE set_id = %s',
            [new_status, p.last_np.set_id]
        )

        for cached in glob.cache['beatmap'].values():
            # not going to bother checking timeout
            if cached['map'].set_id == p.last_np.set_id:
                cached['map'].status = RankedStatus(new_status)

    else:
        # update only map
        await glob.db.execute(
            'UPDATE maps SET status = %s, '
            'frozen = 1 WHERE id = %s',
            [new_status, p.last_np.id]
        )

        for cached in glob.cache['beatmap'].values():
            # not going to bother checking timeout
            if cached['map'] is p.last_np:
                cached['map'].status = RankedStatus(new_status)
                break

    return 'Map updated!'

""" Mod commands
# The commands below are somewhat dangerous,
# and are generally for managing players.
"""

@command(Privileges.Mod, hidden=True)
async def notes(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Retrieve the logs of a specified player by name."""
    if len(msg) != 2 or not msg[1].isdecimal():
        return 'Invalid syntax: !notes <name> <days_back>'

    if not (t := await glob.players.get(name=msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if (days := int(msg[1])) > 365:
        return 'Please contact a developer to fetch >365 day old information.'

    res = await glob.db.fetchall(
        'SELECT `msg`, `time` '
        'FROM `logs` WHERE `to` = %s '
        'AND UNIX_TIMESTAMP(`time`) >= UNIX_TIMESTAMP(NOW()) - %s '
        'ORDER BY `time` ASC',
        [t.id, days * 86400]
    )

    return '\n'.join(map(lambda row: '[{time}] {msg}'.format(**row), res))

@command(Privileges.Mod, hidden=True)
async def addnote(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Add a note to a specified player by name."""
    if len(msg) < 2:
        return 'Invalid syntax: !addnote <name> <note ...>'

    if not (t := await glob.players.get(name=msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    log_msg = f'{p} added note: {" ".join(msg[1:])}'

    await glob.db.execute(
        'INSERT INTO logs (`from`, `to`, `msg`, `time`) '
        'VALUES (%s, %s, %s, NOW())',
        [p.id, t.id, log_msg]
    )

    return f'Added note to {p}.'

@command(Privileges.Mod, hidden=True)
async def silence(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Silence a specified player with a specified duration & reason."""
    if len(msg) < 3:
        return 'Invalid syntax: !silence <name> <duration> <reason>'

    if not (t := await glob.players.get(name=msg[0], sql=True)):
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

    await t.silence(p, duration, reason)
    return f'{t} was silenced.'

@command(Privileges.Mod, hidden=True)
async def unsilence(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Unsilence a specified player."""
    if len(msg) != 1:
        return 'Invalid syntax: !unsilence <name>'

    if not (t := await glob.players.get(name=msg[0], sql=True)):
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
async def ban(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Ban a specified player's account, with a reason."""
    if len(msg) < 2:
        return 'Invalid syntax: !ban <name> <reason>'

    # find any user matching (including offline).
    if not (t := await glob.players.get(name=msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    reason = ' '.join(msg[1:])

    await t.ban(p, reason)
    return f'{t} was banned.'

@command(Privileges.Admin, hidden=True)
async def unban(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Unban a specified player's account, with a reason."""
    if (len_msg := len(msg)) < 2:
        return 'Invalid syntax: !ban <name> <reason>'

    # find any user matching (including offline).
    if not (t := await glob.players.get(name=msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    reason = ' '.join(msg[2:]) if len_msg > 2 else None

    await t.unban(p, reason)
    return f'{t} was unbanned.'

@command(Privileges.Admin, hidden=True)
async def alert(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Send a notification to all players."""
    if len(msg) < 1:
        return 'Invalid syntax: !alert <msg>'

    glob.players.enqueue(packets.notification(' '.join(msg)))
    return 'Alert sent.'

@command(Privileges.Admin, hidden=True)
async def alertu(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Send a notification to a specified player by name."""
    if len(msg) < 2:
        return 'Invalid syntax: !alertu <name> <msg>'

    if not (t := await glob.players.get(name=msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(packets.notification(' '.join(msg[1:])))
    return 'Alert sent.'

""" Developer commands
# The commands below are either dangerous or
# simply not useful for any other roles.
"""

@command(Privileges.Dangerous)
async def recalc(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Performs a full PP recalc on a specified map, or all maps."""
    if len(msg) != 1 or msg[0] not in ('map', 'all'):
        return 'Invalid syntax: !recalc <map/all>'

    score_counts = [] # keep track of # of scores recalced

    if msg[0] == 'map':
        # recalculate all scores on their last /np'ed map.
        if not p.last_np:
            return 'You must /np a map first!'

        ppcalc = await PPCalculator.from_id(p.last_np.id)
        if not ppcalc:
            return 'Could not retrieve map file.'

        await c.send(glob.bot, f'Performing full recalc on {p.last_np.embed}.')

        for table in ('scores_vn', 'scores_rx', 'scores_ap'):
            # fetch all scores from the table on this map
            scores = await glob.db.fetchall(
                'SELECT id, acc, mods, max_combo, '
                'n300, n100, n50, nmiss, ngeki, nkatu '
                f'FROM {table} WHERE map_md5 = %s '
                'AND status = 2 AND mode = 0',
                [p.last_np.md5]
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

# NOTE: this is pretty useless since it doesn't switch anything other
# than the c[e4-6].ppy.sh domains; it exists on bancho as a tournament
# server switch mechanism, perhaps we could leverage this in the future.
@command(Privileges.Dangerous, hidden=True)
async def switchserv(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Switch your client's internal endpoints to a specified IP address."""
    if len(msg) != 1:
        return 'Invalid syntax: !switch <endpoint>'

    p.enqueue(packets.switchTournamentServer(msg[0]))
    return 'Have a nice journey..'

# rest in peace rtx - oct 2020 :candle:
#@command(Privileges.Dangerous, hidden=True)
#async def rtx(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
#    """Send an RTX packet with a message to a user."""
#    if len(msg) != 2:
#        return 'Invalid syntax: !rtx <name> <msg>'
#
#    if not (t := await glob.players.get(name=msg[0])):
#        return 'Could not find a user by that name.'
#
#    t.enqueue(packets.RTX(msg[1]))
#    return 'pong'

@command(Privileges.Dangerous, hidden=True)
async def debug(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Toggle the console's debug setting."""
    glob.config.debug = not glob.config.debug
    return f"Toggled {'on' if glob.config.debug else 'off'}."

# TODO: this command is rly bad, it probably
# shouldn't really be a command to begin with..
str_priv_dict = defaultdict(lambda: None, {
    'normal': Privileges.Normal,
    'verified': Privileges.Verified,
    'whitelisted': Privileges.Whitelisted,
    'supporter': Privileges.Supporter,
    'premium': Privileges.Premium,
    'tournament': Privileges.Tournament,
    'nominator': Privileges.Nominator,
    'mod': Privileges.Mod,
    'admin': Privileges.Admin,
    'dangerous': Privileges.Dangerous
})
@command(Privileges.Dangerous, hidden=True)
async def setpriv(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Set privileges for a specified player (by name)."""
    if len(msg) < 2:
        return 'Invalid syntax: !setpriv <name> <role1 role2 role3 ...>'

    priv = Privileges(0)

    for m in msg[1:]:
        if not (_priv := str_priv_dict[m]):
            return f'Not found: {m}.'

        priv |= _priv

    if not (t := await glob.players.get(name=msg[0], sql=True)):
        return 'Could not find user.'

    await t.update_privs(priv)
    return f"Updated {t}'s privileges."

# TODO: figure out better way :(
@command(Privileges.Dangerous, other_triggers=['men'], hidden=True)
async def menu_preview(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Temporary command to illustrate cmyui's menu option idea."""
    async def callback():
        # this is called when the menu item is clicked
        p.enqueue(packets.notification('clicked!'))

    # add the option to their menu opts & send them a button
    opt_id = await p.add_to_menu(callback)
    return f'[osu://dl/{opt_id} option]'

# XXX: this actually comes in handy sometimes, i initially
# wrote it completely as a joke, but i might keep it in for
# devs.. Comes in handy when debugging to be able to run something
# like `!py return (await glob.players.get(name='cmyui')).status.action`
# or for anything while debugging on-the-fly..
@command(Privileges.Dangerous)
async def py(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    # create the new coroutine definition as a string
    # with the lines from our message (split by '\n').
    lines = ' '.join(msg).split(r'\n')
    definition = '\n '.join(['async def __py(p, c, msg):'] + lines)

    try:
        # define, and run the coroutine
        exec(definition)

        loop = asyncio.get_event_loop()

        try:
            task = loop.create_task(locals()['__py'](p, c, msg))
            ret = await asyncio.wait_for(asyncio.shield(task), 5.0)
        except asyncio.TimeoutError:
            ret = 'Left running (took >=5 sec).'

    except Exception as e:
        # code was invalid, return
        # the error in the osu! chat.
        ret = f'{e.__class__}: {e}'

    if ret is not None:
        return str(ret)
    else:
        return 'Success'

""" Multiplayer commands
# The commands below are specifically for
# multiplayer match management.
"""

@mp_commands.add(Privileges.Normal, other_triggers=['h'])
async def mp_help(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Show information of all documented mp commands the player can access."""
    prefix = glob.config.command_prefix
    cmds = []

    for cmd in mp_commands.commands:
        if not cmd.doc or not p.priv & cmd.priv:
            # no doc, or insufficient permissions.
            continue

        cmds.append(f'{prefix}mp {cmd.triggers[0]}: {cmd.doc}')

    return '\n'.join(cmds)

@mp_commands.add(Privileges.Normal, other_triggers=['st'])
async def mp_start(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Start the current multiplayer match, with any players ready."""
    if (msg_len := len(msg)) > 1:
        return 'Invalid syntax: !mp start <force/seconds>'

    if msg_len == 1:
        if msg[0].isdecimal():
            # !mp start <seconds>
            duration = int(msg[0])
            if not 0 < duration <= 300:
                return 'Timer range is 1-300 seconds.'

            async def delayed_start(wait: int):
                await asyncio.sleep(wait)

                if p not in m:
                    # player left match since :monkaS:
                    return

                await m.chat.send(glob.bot, 'Good luck!')
                m.start()

            asyncio.create_task(delayed_start(duration))
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

@mp_commands.add(Privileges.Normal, other_triggers=['a'])
async def mp_abort(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Abort the current in-progress multiplayer match."""
    if not m.in_progress:
        return 'Abort what?'

    m.unready_players(expected=SlotStatus.playing)

    m.in_progress = False
    m.enqueue(packets.matchAbort())
    m.enqueue_state()
    return 'Match aborted.'

@mp_commands.add(Privileges.Admin, hidden=True)
async def mp_force(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Force a player into the current match by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp force <name>'

    if not (t := await glob.players.get(name=' '.join(msg))):
        return 'Could not find a user by that name.'

    await t.join_match(m, m.passwd)
    return 'Welcome.'

@mp_commands.add(Privileges.Normal)
async def mp_map(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Set the current match's current map by id."""
    if len(msg) != 1 or not msg[0].isdecimal():
        return 'Invalid syntax: !mp map <beatmapid>'

    if not (bmap := await Beatmap.from_bid(int(msg[0]))):
        return 'Beatmap not found.'

    m.map_id = bmap.id
    m.map_md5 = bmap.md5
    m.map_name = bmap.full

    m.enqueue_state()
    return f'Map selected: {bmap.embed}.'

@mp_commands.add(Privileges.Normal)
async def mp_mods(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Set the current match's mods, from string form."""
    if len(msg) != 1 or not ~len(msg[0]) & 1:
        return 'Invalid syntax: !mp mods <mods>'

    mods = Mods.from_str(msg[0])

    if m.freemods:
        if p is m.host:
            # allow host to set speed-changing mods.
            m.mods = mods & Mods.SPEED_CHANGING

        # set slot mods
        m.get_slot(p).mods = mods & ~Mods.SPEED_CHANGING
    else:
        # not freemods, set match mods.
        m.mods = mods

    m.enqueue_state()
    return 'Match mods updated.'

@mp_commands.add(Privileges.Normal, other_triggers=['fm'])
async def mp_freemods(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    if len(msg) != 1 or msg[0] not in ('on', 'off'):
        return 'Invalid syntax: !mp freemods <on/off>'

    if msg[0] == 'on':
        # central mods -> all players mods.
        m.freemods = True

        for s in m.slots:
            if s.status & SlotStatus.has_player:
                # the slot takes any non-speed
                # changing mods from the match.
                s.mods = m.mods & ~Mods.SPEED_CHANGING

        m.mods &= Mods.SPEED_CHANGING
    else:
        # host mods -> central mods.
        m.freemods = False
        host = m.get_host_slot() # should always exist
        # the match keeps any speed-changing mods,
        # and also takes any mods the host has enabled.
        m.mods &= Mods.SPEED_CHANGING
        m.mods |= host.mods

    m.enqueue_state()
    return 'Match freemod status updated.'

@mp_commands.add(Privileges.Normal)
async def mp_host(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Set the current match's current host by id."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp host <name>'

    if not (t := await glob.players.get(name=' '.join(msg))):
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
async def mp_randpw(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Randomize the current match's password."""
    m.passwd = cmyui.rstring(16)
    return 'Match password randomized.'

@mp_commands.add(Privileges.Normal, other_triggers=['inv'])
async def mp_invite(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Invite a player to the current match by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp invite <name>'

    if not (t := await glob.players.get(name=msg[0])):
        return 'Could not find a user by that name.'

    if p is t:
        return "You can't invite yourself!"

    t.enqueue(packets.matchInvite(p, t.name))
    return f'Invited {t} to the match.'

@mp_commands.add(Privileges.Normal)
async def mp_addref(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Add a referee to the current match by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp addref <name>'

    if not (t := await glob.players.get(name=msg[0])):
        return 'Could not find a user by that name.'

    if t not in m:
        return 'User must be in the current match!'

    if t in m.refs:
        return f'{t} is already a match referee!'

    m._refs.add(t)
    return 'Match referees updated.'

@mp_commands.add(Privileges.Normal)
async def mp_rmref(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Remove a referee from the current match by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp addref <name>'

    if not (t := await glob.players.get(name=msg[0])):
        return 'Could not find a user by that name.'

    if t not in m.refs:
        return f'{t} is not a match referee!'

    if t is m.host:
        return 'The host is always a referee!'

    m._refs.remove(t)
    return 'Match referees updated.'

@mp_commands.add(Privileges.Normal)
async def mp_listref(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """List all referees from the current match."""
    return ', '.join(map(str, m.refs)) + '.'

@mp_commands.add(Privileges.Normal)
async def mp_lock(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Lock all unused slots in the current match."""
    for slot in m.slots:
        if slot.status == SlotStatus.open:
            slot.status = SlotStatus.locked

    m.enqueue_state()
    return 'All unused slots locked.'

@mp_commands.add(Privileges.Normal)
async def mp_unlock(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Unlock locked slots in the current match."""
    for slot in m.slots:
        if slot.status == SlotStatus.locked:
            slot.status = SlotStatus.open

    m.enqueue_state()
    return 'All locked slots unlocked.'

@mp_commands.add(Privileges.Normal)
async def mp_teams(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
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

@mp_commands.add(Privileges.Normal, other_triggers=['cond'])
async def mp_condition(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
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
async def mp_scrim(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Start a scrim in the current match."""
    if len(msg) != 1 \
    or not (rgx := re.fullmatch(r'^(?:bo)?(\d{1,2})$', msg[0])):
        return 'Invalid syntax: !mp scrim <bo#>'

    if not 0 <= (best_of := int(rgx[1])) < 16:
        return 'Best of must be in range 0-15.'

    winning_pts = (best_of // 2) + 1

    if winning_pts != 0:
        # setting to real num
        if m.is_scrimming:
            return 'Already scrimming!'

        if ~best_of & 1:
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

@mp_commands.add(Privileges.Normal)
async def mp_endscrim(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """End the current matches ongoing scrim."""
    if not m.is_scrimming:
        return 'Not currently scrimming!'

    m.is_scrimming = False
    m.reset_scrim()
    return 'Scrimmage ended.' # TODO: final score (get_score method?)

@mp_commands.add(Privileges.Normal, other_triggers=['rm'])
async def mp_rematch(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Restart a scrim with the previous match points, """ \
    """or roll back the most recent match point."""
    if msg:
        return 'Invalid syntax: !mp rematch'

    if p is not m.host:
        return 'Only available to the host.'

    if not m.is_scrimming:
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

# Mappool commands

@mp_commands.add(Privileges.Normal, other_triggers=['lp'])
async def mp_loadpool(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
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

@mp_commands.add(Privileges.Normal, other_triggers=['ulp'])
async def mp_unloadpool(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
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
async def mp_ban(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Ban a pick in the currently loaded mappool."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp ban <mods#>'

    if not m.pool:
        return 'No pool currently selected!'

    mods_slot = msg[0]

    # separate mods & slot
    if not (rgx := re.fullmatch(r'^([a-zA-Z]+)([0-9]+)$', mods_slot)):
        return 'Invalid <mods#> syntax; correct example: "HD2".'

    mods = Mods.from_str(rgx[1])
    slot = int(rgx[2])

    if (mods, slot) not in m.pool.maps:
        return f'Found no {mods_slot} pick in the pool.'

    if (mods, slot) in m.bans:
        return 'That pick is already banned!'

    m.bans.add((mods, slot))
    return f'{mods_slot} banned.'

@mp_commands.add(Privileges.Normal)
async def mp_unban(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Unban a pick in the currently loaded mappool."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp unban <mods#>'

    if not m.pool:
        return 'No pool currently selected!'

    mods_slot = msg[0]

    # separate mods & slot
    if not (rgx := re.fullmatch(r'^([a-zA-Z]+)([0-9]+)$', mods_slot)):
        return 'Invalid <mods#> syntax; correct example: "HD2".'

    mods = Mods.from_str(rgx[1])
    slot = int(rgx[2])

    if (mods, slot) not in m.pool.maps:
        return f'Found no {mods_slot} pick in the pool.'

    if (mods, slot) not in m.bans:
        return 'That pick is not currently banned!'

    m.bans.remove((mods, slot))
    return f'{mods_slot} unbanned.'

@mp_commands.add(Privileges.Normal)
async def mp_pick(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Pick a map from the currently loaded mappool."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp pick <mods#>'

    if not m.pool:
        return 'No pool currently loaded!'

    mods_slot = msg[0]

    # separate mods & slot
    if not (rgx := re.fullmatch(r'^([a-zA-Z]+)([0-9]+)$', mods_slot)):
        return 'Invalid <mods#> syntax; correct example: "HD2".'

    mods = Mods.from_str(rgx[1])
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
    m.enqueue_state()

    return f'Picked {bmap.embed}. ({mods_slot})'

""" Mappool management commands
# The commands below are for event managers
# and tournament hosts/referees to help automate
# tedious processes of running tournaments.
"""

@pool_commands.add(Privileges.Tournament, other_triggers=['h'], hidden=True)
async def pool_help(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Show information of all documented pool commands the player can access."""
    prefix = glob.config.command_prefix
    cmds = []

    for cmd in pool_commands.commands:
        if not cmd.doc or not p.priv & cmd.priv:
            # no doc, or insufficient permissions.
            continue

        cmds.append(f'{prefix}pool {cmd.triggers[0]}: {cmd.doc}')

    return '\n'.join(cmds)

@pool_commands.add(Privileges.Tournament, other_triggers=['c'], hidden=True)
async def pool_create(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
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

@pool_commands.add(Privileges.Tournament, other_triggers=['d'], hidden=True)
async def pool_delete(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
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

@pool_commands.add(Privileges.Tournament, other_triggers=['a'], hidden=True)
async def pool_add(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Add a new map to a mappool in the database."""
    if len(msg) != 2:
        return 'Invalid syntax: !pool add <name> <mods#>'

    if not p.last_np:
        return 'Please /np a map first!'

    name, mods_slot = msg

    # separate mods & slot
    if not (rgx := re.fullmatch(r'^([a-zA-Z]+)([0-9]+)$', mods_slot)):
        return 'Invalid <mods#> syntax; correct example: "HD2".'

    if not ~len(rgx[1]) & 1:
        return 'Invalid mods.'

    mods = int(Mods.from_str(rgx[1]))
    slot = int(rgx[2])

    if not (pool := glob.pools.get(name)):
        return 'Could not find a pool by that name!'

    if p.last_np in pool.maps:
        return f'Map is already in the pool!'

    # insert into db
    await glob.db.execute(
        'INSERT INTO tourney_pool_maps '
        '(map_id, pool_id, mods, slot) '
        'VALUES (%s, %s, %s, %s)',
        [p.last_np.id, pool.id, mods, slot]
    )

    # add to cache
    pool.maps[(Mods(mods), slot)] = p.last_np

    return f'{p.last_np.embed} added to {name}.'

@pool_commands.add(Privileges.Tournament, other_triggers=['r'], hidden=True)
async def pool_remove(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Remove a map from a mappool in the database."""
    if len(msg) != 2:
        return 'Invalid syntax: !pool remove <name> <mods#>'

    name, mods_slot = msg

    # separate mods & slot
    if not (rgx := re.fullmatch(r'^([a-zA-Z]+)([0-9]+)$', mods_slot)):
        return 'Invalid <mods#> syntax; correct example: "HD2".'

    mods = Mods.from_str(rgx[1])
    slot = int(rgx[2])

    if not (pool := glob.pools.get(name)):
        return 'Could not find a pool by that name!'

    if (mods, slot) not in pool.maps:
        return f'Found no {mods_slot} pick in the pool.'

    # delete from db
    await glob.db.execute(
        'DELETE FROM tourney_pool_maps '
        'WHERE mods = %s AND slot = %s',
        [int(mods), slot]
    )

    # remove from cache
    del pool.maps[(mods, slot)]

    return f'{mods_slot} removed from {name}.'

@pool_commands.add(Privileges.Tournament, other_triggers=['l'], hidden=True)
async def pool_list(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """List all existing mappools information."""

    if not (pools := glob.pools):
        return 'There are currently no pools!'

    l = [f'Mappools ({len(pools)})']

    for pool in pools:
        l.append(f'[{pool.created_at:%Y-%m-%d}] {pool.id}. {pool.name}, by {pool.created_by}.')

    return '\n'.join(l)

@pool_commands.add(Privileges.Tournament, other_triggers=['i'], hidden=True)
async def pool_info(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
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

@clan_commands.add(Privileges.Normal, other_triggers=['h'])
async def clan_help(p: 'Player', m: 'Match', msg: Sequence[str]) -> str:
    """Show information of all documented clan commands the player can access."""
    prefix = glob.config.command_prefix
    cmds = []

    for cmd in clan_commands.commands:
        if not cmd.doc or not p.priv & cmd.priv:
            # no doc, or insufficient permissions.
            continue

        cmds.append(f'{prefix}clan {cmd.triggers[0]}: {cmd.doc}')

    return '\n'.join(cmds)

@clan_commands.add(Privileges.Normal, other_triggers=['c'])
async def clan_create(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Create a clan with a given tag & name."""
    if p.clan:
        return f"You're already a member of {p.clan}!"

    if len(msg) < 2:
        return 'Invalid syntax: !clan create <tag> <name>'

    if not 1 <= len(tag := msg[0].upper()) <= 6:
        return 'Clan tag may be 1-6 characters long.'

    if not 2 <= len(name := ' '.join(msg[1:])) <= 16:
        return 'Clan name may be 2-16 characters long.'

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
    p.clan_rank = ClanRank.Owner

    clan.owner = p.id
    clan.members.add(p.id)

    await glob.db.execute(
        'UPDATE users '
        'SET clan_id = %s, '
        'clan_rank = 3 ' # ClanRank.Owner
        'WHERE id = %s',
        [id, p.id]
    )

    # TODO: take currency from player

    # announce clan creation
    if announce_chan := glob.channels['#announce']:
        msg = f'\x01ACTION founded {clan!r}.'
        await announce_chan.send(p, msg, to_self=True)

    return f'{clan!r} created.'

@clan_commands.add(Privileges.Normal, other_triggers=['delete', 'd'])
async def clan_disband(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
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
    for m in [await glob.players.get(id=p_id) for p_id in clan.members]:
        m.clan = m.clan_rank = None

    await glob.db.execute(
        'UPDATE users '
        'SET clan_id = 0, '
        'clan_rank = 0 '
        'WHERE clan_id = %s',
        [clan.id]
    )

    # remove clan from cache
    glob.clans.remove(clan)

    # announce clan disbanding
    if announce_chan := glob.channels['#announce']:
        msg = f'\x01ACTION disbanded {clan!r}.'
        await announce_chan.send(p, msg, to_self=True)

    return f'{clan!r} disbanded.'

@clan_commands.add(Privileges.Normal, other_triggers=['i'])
async def clan_info(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
    """Lookup information of a clan by tag."""
    if not msg:
        return 'Invalid syntax: !clan info <tag>'

    if not (clan := glob.clans.get(tag=' '.join(msg).upper())):
        return 'Could not find a clan by that tag.'

    owner = await glob.players.get(id=clan.owner, sql=True)

    _time = clan.created_at.strftime('%H:%M:%S%p')
    _date = clan.created_at.strftime('%Y-%m-%d')
    datetime_fmt = f'Founded at {_time} on {_date}'
    msg = [f"{owner.embed}'s {clan!r} | {datetime_fmt}."]

    # get members ranking from sql
    res = await glob.db.fetchall(
        'SELECT name, clan_rank '
        'FROM users '
        'WHERE clan_id = %s',
        [clan.id], _dict=False
    )

    for name, clan_rank in sorted(res, key=lambda row: row[1]):
        rank_str = ('Member', 'Officer', 'Owner')[clan_rank - 1]
        msg.append(f'[{rank_str}] {name}')

    return '\n'.join(msg)

@clan_commands.add(Privileges.Normal, other_triggers=['l'])
async def clan_list(p: 'Player', c: Messageable, msg: Sequence[str]) -> str:
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

async def process_commands(p: 'Player', t: Messageable,
                           msg: str) -> Optional[CommandResponse]:
    # response is either a CommandResponse if we hit a command,
    # or simply False if we don't have any command hits.
    st = time.time_ns()
    trigger, *args = msg[len(glob.config.command_prefix):].strip().split(' ')

    for cmd_set in glob.commands['sets']:
        # check if any command sets match.
        if trigger == cmd_set.trigger:
            # matching set found;
            if trigger == 'mp':
                # multi set is a bit of a special case,
                # as we do some additional checks.
                if not (m := p.match):
                    # player not in a match
                    return

                if t is not m.chat:
                    # message not in match channel
                    return

                if p not in m.refs and not p.priv & Privileges.Tournament:
                    # doesn't have privs to use !mp commands.
                    return

                t = m # send match for mp commands instead of chan

            if not args:
                # no subcommand specified,
                # send back the set's !help cmd.
                args = ['help']

            trigger, *args = args # get subcommand
            commands = cmd_set.commands
            break
    else:
        # no set commands matched, check normal commands.
        commands = glob.commands['regular']

    for cmd in commands:
        if trigger in cmd.triggers and p.priv & cmd.priv:
            # command found & we have privileges, run it.
            if res := await cmd.callback(p, t, args):
                time_taken = (time.time_ns() - st) / 1e6

                return {
                    'resp': f'{res} | Elapsed: {time_taken:.2f}ms',
                    'hidden': cmd.hidden
                }

            return {'hidden': False}
