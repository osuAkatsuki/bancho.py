# -*- coding: utf-8 -*-

import asyncio
from utils.recalculator import PPCalculator
from typing import NamedTuple, Sequence, Optional, Union, Callable
import time
import re
import cmyui
import random
from collections import defaultdict

import packets

from constants.privileges import Privileges
from constants.mods import Mods
from constants import regexes

from objects import glob
from objects.player import Player
from objects.channel import Channel
from objects.beatmap import Beatmap, RankedStatus
from objects.match import (MapPool, Match, MatchScoringTypes,
                           MatchTeamTypes, SlotStatus, Teams)

Messageable = Union[Channel, Player]
CommandResponse = dict[str, str]

class Command(NamedTuple):
    triggers: list[str]
    callback: Callable
    priv: Privileges
    public: bool
    doc: str

class CommandSet:
    __slots__ = ('commands', 'trigger')
    def __init__(self, trigger: str) -> None:
        self.trigger = trigger
        self.commands: list[Command] = []

    def add(self, priv: Privileges, public: bool,
            triggers: list[str] = []) -> Callable:
        def wrapper(f: Callable):
            self.commands.append(Command(
                # NOTE: this method assumes that functions without any
                # triggers will be named like '{self.trigger}_{trigger}'.
                triggers = triggers or [f.__name__.removeprefix(f'{self.trigger}_')],
                callback = f, priv = priv,
                public = public, doc = f.__doc__
            ))

            return f
        return wrapper

# TODO: refactor help commands into some base ver
#       since they're all the same anyways lol.

# not sure if this should be in glob or not,
# trying to think of some use cases lol..
glob.commands = {
    'regular': [],
    'sets': [mp_commands := CommandSet('mp'),
             pool_commands := CommandSet('pool')]
}

def command(priv: Privileges, public: bool,
            triggers: list[str] = []) -> Callable:
    def wrapper(callback: Callable):
        glob.commands['regular'].append(Command(
            triggers=triggers or [callback.__name__],
            callback=callback,
            priv=priv,
            public=public,
            doc=callback.__doc__
        ))

        return callback
    return wrapper

""" User commands
# The commands below are not considered dangerous,
# and are granted to any unbanned players.
"""

@command(triggers=['help', 'h'], priv=Privileges.Normal, public=False)
async def _help(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Show information of all documented commands `p` can use."""
    cmds = []

    for cmd in glob.commands['regular']:
        if not cmd.doc or not p.priv & cmd.priv:
            # no doc, or insufficient permissions.
            continue

        cmds.append(f'{cmd.triggers[0]}: {cmd.doc}')

    return '\n'.join(cmds)

@command(priv=Privileges.Normal, public=True)
async def roll(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Roll an n-sided die where n is the number you write (100 if empty)."""
    if msg and msg[0].isdecimal():
        max_roll = min(int(msg[0]), 0x7fff)
    else:
        max_roll = 100

    points = random.randrange(0, max_roll)
    return f'{p.name} rolls {points} points!'

@command(priv=Privileges.Normal, public=True)
async def bloodcat(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Return a bloodcat link of the user's current map (situation dependant)."""
    bmap = None

    if p.match and p.match.bmap:
        # return the match beatmap
        bmap = p.match.bmap
    # TODO: spectator?
    elif p.last_np:
        bmap = p.last_np
    else:
        return 'No map found!'

    return '[https://bloodcat.com/d/{} {}]'.format(bmap.set_id, bmap.full)

@command(priv=Privileges.Normal, public=True)
async def last(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Show information about your most recent score."""
    if not (s := p.recent_score):
        return 'No scores found :o'

    return (f'[{s.mode!r}] {s.bmap.embed} +{s.mods!r} {s.acc:.2f}% | '
            f'{s.pp:.2f}pp #{s.rank}')

_mapsearch_fmt = (
    '[https://osu.ppy.sh/b/{id} {artist} - {title} [{version}]] '
    '([{mirror}/d/{set_id} download])'
)
_mapsearch_func = lambda row: _mapsearch_fmt.format(**row, mirror=glob.config.mirror)
@command(priv=Privileges.Normal, public=False)
async def mapsearch(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Search map titles with user input as a wildcard."""
    if not msg:
        return 'Invalid syntax: !mapsearch <title>'

    if not (res := await glob.db.fetchall(
        'SELECT id, set_id, artist, title, version '
        'FROM maps WHERE title LIKE %s LIMIT 25',
        [f'%{" ".join(msg)}%']
    )): return 'No matches found :('

    return '\n'.join(map(_mapsearch_func, res)) + f'\nMaps: {len(res)}'

@command(triggers=['with'], priv=Privileges.Normal, public=False)
async def _with(p: Player, c: Messageable, msg: Sequence[str]) -> str:
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

    _msg.append(repr(mods))

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
@command(triggers=['map'], priv=Privileges.Nominator, public=True)
async def _map(p: Player, c: Messageable, msg: Sequence[str]) -> str:
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
            if cached['map'] is p.last_np:
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

@command(priv=Privileges.Mod, public=False)
async def notes(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Retrieve the logs of a specified player by name."""
    if len(msg) != 2 or not msg[1].isdecimal():
        return 'Invalid syntax: !notes <name> <days_back>'

    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
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

@command(priv=Privileges.Mod, public=False)
async def addnote(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Add a note to a specified player by name."""
    if len(msg) < 2:
        return 'Invalid syntax: !addnote <name> <note ...>'

    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    log_msg = f'{p} added note: {" ".join(msg[1:])}'

    await glob.db.execute(
        'INSERT INTO logs (`from`, `to`, `msg`, `time`) '
        'VALUES (%s, %s, %s, NOW())',
        [p.id, t.id, log_msg]
    )

    return f'Added note to {p}.'

@command(priv=Privileges.Mod, public=False)
async def silence(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Silence `p` with a specified duration & reason."""
    if len(msg) < 3:
        return 'Invalid syntax: !silence <name> <duration> <reason>'

    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
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

@command(priv=Privileges.Mod, public=False)
async def unsilence(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Unsilence `p`."""
    if len(msg) != 1:
        return 'Invalid syntax: !unsilence <name>'

    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
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

@command(priv=Privileges.Admin, public=False)
async def ban(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Ban a player's account, with a reason."""
    if len(msg) < 2:
        return 'Invalid syntax: !ban <name> (reason)'

    # find any user matching (including offline).
    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    reason = ' '.join(msg[1:])

    await t.ban(p, reason)
    return f'{t} was banned.'

@command(priv=Privileges.Admin, public=False)
async def unban(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Unban a player's account, with a reason."""
    if (len_msg := len(msg)) < 2:
        return 'Invalid syntax: !ban <name> (reason)'

    # find any user matching (including offline).
    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    reason = ' '.join(msg[2:]) if len_msg > 2 else None

    await t.unban(p, reason)
    return f'{t} was unbanned.'

@command(priv=Privileges.Admin, public=False)
async def alert(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Send a notification to all players."""
    if len(msg) < 1:
        return 'Invalid syntax: !alert <msg>'

    glob.players.enqueue(packets.notification(' '.join(msg)))
    return 'Alert sent.'

@command(triggers=['alertu'], priv=Privileges.Admin, public=False)
async def alert_user(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Send a notification to a specific player by name."""
    if len(msg) < 2:
        return 'Invalid syntax: !alertu <name> <msg>'

    if not (t := await glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(packets.notification(' '.join(msg[1:])))
    return 'Alert sent.'

""" Developer commands
# The commands below are either dangerous or
# simply not useful for any other roles.
"""

@command(priv=Privileges.Dangerous, public=True)
async def recalc(p: Player, c: Messageable, msg: Sequence[str]) -> str:
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

@command(triggers=['switchserv'], priv=Privileges.Dangerous, public=False)
async def switch_server(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Switch servers to a specified ip address."""
    if len(msg) != 1:
        return 'Invalid syntax: !switch <endpoint>'

    p.enqueue(packets.switchTournamentServer(msg[0]))
    return 'Have a nice journey..'

# rest in peace rtx - oct 2020 :candle:
#@command(priv=Privileges.Dangerous, public=False)
#async def rtx(p: Player, c: Messageable, msg: Sequence[str]) -> str:
#    """Send an RTX packet with a message to a user."""
#    if len(msg) != 2:
#        return 'Invalid syntax: !rtx <name> <msg>'
#
#    if not (t := await glob.players.get_by_name(msg[0])):
#        return 'Could not find a user by that name.'
#
#    t.enqueue(packets.RTX(msg[1]))
#    return 'pong'

@command(priv=Privileges.Dangerous, public=False)
async def debug(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Toggle the console's debug setting."""
    glob.config.debug = not glob.config.debug
    return f"Toggled {'on' if glob.config.debug else 'off'}."

str_to_priv = lambda p: defaultdict(lambda: None, {
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
})[p]
@command(priv=Privileges.Dangerous, public=False)
async def setpriv(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Set privileges for a player (by name)."""
    if len(msg) < 2:
        return 'Invalid syntax: !setpriv <name> <role1 | role2 | ...>'

    # a mess that gets each unique privilege out of msg.
    # TODO: rewrite to be at least a bit more readable..
    priv = map(str_to_priv, set(''.join(msg[1:]).replace(' ', '').lower().split('|')))

    if any(x is None for x in priv):
        return 'Invalid privileges.'

    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return 'Could not find user.'

    new_priv = sum(priv)
    await glob.db.execute(
        'UPDATE users SET priv = %s WHERE id = %s',
        [new_priv, t.id]
    )

    t.priv = Privileges(new_priv)
    return 'Success.'

# temp command, to illustrate how menu options will work
@command(triggers=['men'], priv=Privileges.Dangerous, public=False)
async def menu_preview(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    async def callback():
        # this is called when the menu item is clicked
        p.enqueue(packets.notification('clicked!'))

    # add the option to their menu opts & send them a button
    opt_id = await p.add_to_menu(callback)
    return f'[osu://dl/{opt_id} option]'

# XXX: this actually comes in handy sometimes, i initially
# wrote it completely as a joke, but i might keep it in for
# devs.. Comes in handy when debugging to be able to run something
# like `!py return await glob.players.get_by_name('cmyui').status.action`
# or for anything while debugging on-the-fly..
@command(priv=Privileges.Dangerous, public=False)
async def py(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    # create the new coroutine definition as a string
    # with the lines from our message (split by '\n').
    lines = ' '.join(msg).split(r'\n')
    definition = '\n '.join(['async def __py(p, c, msg):'] + lines)

    try:
        # define, and run the coroutine
        exec(definition)

        _locals = locals()
        loop = asyncio.get_event_loop()

        try:
            task = loop.create_task(_locals['__py'](p, c, msg))
            ret = await asyncio.wait_for(asyncio.shield(task), 5.0)
        except asyncio.TimeoutError:
            ret = 'Left running (took >=5 sec).'

        del _locals['__py']
    except Exception as e:
        # code was invalid, return
        # the error in the osu! chat.
        ret = f'{e.__class__}: {e}'

    return ret or 'Success.'

""" Multiplayer commands
# The commands below are specifically for
# multiplayer match management.
"""

@mp_commands.add(triggers=['help', 'h'], priv=Privileges.Normal, public=True)
async def mp_help(p: Player, m: Match, msg: Sequence[str]) -> str:
    cmds = []

    for cmd in mp_commands.commands:
        if not cmd.doc or not p.priv & cmd.priv:
            # no doc, or insufficient permissions.
            continue

        cmds.append(f'!mp {cmd.triggers[0]}: {cmd.doc}')

    return '\n'.join(cmds)

@mp_commands.add(triggers=['start', 'st'], priv=Privileges.Normal, public=True)
async def mp_start(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Start a multiplayer match."""
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

@mp_commands.add(triggers=['abort', 'a'], priv=Privileges.Normal, public=True)
async def mp_abort(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Abort an in-progress multiplayer match."""
    if not m.in_progress:
        return 'Abort what?'

    m.unready_players(expected=SlotStatus.playing)

    m.in_progress = False
    m.enqueue(packets.matchAbort())
    m.enqueue_state()
    return 'Match aborted.'

@mp_commands.add(priv=Privileges.Admin, public=False)
async def mp_force(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Force a player into the current match by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp force <name>'

    if not (t := await glob.players.get_by_name(' '.join(msg))):
        return 'Could not find a user by that name.'

    await t.join_match(m)
    return 'Welcome.'

@mp_commands.add(priv=Privileges.Normal, public=True)
async def mp_map(p: Player, m: Match, msg: Sequence[str]) -> str:
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

@mp_commands.add(priv=Privileges.Normal, public=True)
async def mp_mods(p: Player, m: Match, msg: Sequence[str]) -> str:
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

@mp_commands.add(triggers=['freemods', 'fm'], priv=Privileges.Normal, public=True)
async def mp_freemods(p: Player, m: Match, msg: Sequence[str]) -> str:
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

@mp_commands.add(priv=Privileges.Normal, public=True)
async def mp_host(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Set the current match's current host by id."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp host <name>'

    if not (t := await glob.players.get_by_name(' '.join(msg))):
        return 'Could not find a user by that name.'

    if t is m.host:
        return "They're already host, silly!"

    if t not in m:
        return 'Found no such player in the match.'

    m.host = t
    m.host.enqueue(packets.matchTransferHost())
    m.enqueue_state(lobby=False)
    return 'Match host updated.'

@mp_commands.add(priv=Privileges.Normal, public=True)
async def mp_randpw(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Randomize the current match's password."""
    m.passwd = cmyui.rstring(16)
    return 'Match password randomized.'

@mp_commands.add(triggers=['invite', 'inv'], priv=Privileges.Normal, public=True)
async def mp_invite(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Invite a player to the current match by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp invite <name>'

    if not (t := await glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    if p is t:
        return "You can't invite yourself!"

    t.enqueue(packets.matchInvite(p, t.name))
    return f'Invited {t} to the match.'

@mp_commands.add(priv=Privileges.Normal, public=True)
async def mp_addref(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Add a referee to the current match by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp addref <name>'

    if not (t := await glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    if t not in m:
        return 'User must be in the current match!'

    if t in m.refs:
        return f'{t} is already a match referee!'

    m._refs.add(t)
    return 'Match referees updated.'

@mp_commands.add(priv=Privileges.Normal, public=True)
async def mp_rmref(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Remove a referee from the current match by name."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp addref <name>'

    if not (t := await glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    if t not in m.refs:
        return f'{t} is not a match referee!'

    if t is m.host:
        return 'The host is always a referee!'

    m._refs.remove(t)
    return 'Match referees updated.'

@mp_commands.add(priv=Privileges.Normal, public=True)
async def mp_listref(p: Player, m: Match, msg: Sequence[str]) -> str:
    """List all referees from the current match."""
    return ', '.join(map(str, m.refs)) + '.'

@mp_commands.add(priv=Privileges.Normal, public=True)
async def mp_lock(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Lock all unused slots in the current match."""
    for slot in m.slots:
        if slot.status == SlotStatus.open:
            slot.status = SlotStatus.locked

    m.enqueue_state()
    return 'All unused slots locked.'

@mp_commands.add(priv=Privileges.Normal, public=True)
async def mp_unlock(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Unlock locked slots in the current match."""
    for slot in m.slots:
        if slot.status == SlotStatus.locked:
            slot.status = SlotStatus.open

    m.enqueue_state()
    return 'All locked slots unlocked.'

@mp_commands.add(priv=Privileges.Normal, public=True)
async def mp_teams(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Change the team mode for the current match."""
    if len(msg) != 1 or msg[0] not in ('head-to-head', 'tag-coop',
                                       'team-vs', 'tag-team-vs'):
        return 'Invalid syntax: !mp teams <mode>'

    m.team_type = {
        'head-to-head': MatchTeamTypes.head_to_head,
        'tag-coop': MatchTeamTypes.tag_coop,
        'team-vs': MatchTeamTypes.team_vs,
        'tag-team-vs': MatchTeamTypes.tag_team_vs
    }[msg[0]]

    # find the new appropriate default team.
    # defaults are (ffa: neutral, teams: red).
    if m.team_type in (MatchTeamTypes.head_to_head,
                       MatchTeamTypes.tag_coop):
        new_t = Teams.neutral
    else:
        new_t = Teams.red

    # change each active slots team to
    # fit the correspoding team mode.
    for s in m.slots:
        if s.status & SlotStatus.has_player:
            s.team = new_t

    if m.winning_pts != 0:
        # reset score if scrimming.
        m.match_points.clear()

    m.enqueue_state()
    return 'Match team mode updated.'

@mp_commands.add(triggers=['condition', 'cond'], priv=Privileges.Normal, public=True)
async def mp_condition(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Change the win condition for the match."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp condition <mode>'

    cond = msg[0]

    if cond == 'pp':
        # special case - pp can't actually be used as an ingame
        # win condition, but gulag allows it to be passed into
        # this command during a scrims to use pp as a win cond.
        if m.winning_pts == 0:
            return 'PP is only useful as a win condition during scrims.'
        if m.use_pp_scoring:
            return 'PP scoring already enabled.'

        m.use_pp_scoring = True
    else:
        if m.use_pp_scoring:
            m.use_pp_scoring = False

        if cond == 'score':
            m.win_condition = MatchScoringTypes.score
        elif cond in ('accuracy', 'acc'):
            m.win_condition = MatchScoringTypes.accuracy
        elif cond == 'combo':
            m.win_condition = MatchScoringTypes.combo
        elif cond in ('scorev2', 'v2'):
            m.win_condition = MatchScoringTypes.scorev2
        else:
            return 'Invalid win condition. (score, acc, combo, scorev2, *pp)'

    m.enqueue_state(lobby=False)
    return 'Match win condition updated.'

@mp_commands.add(priv=Privileges.Normal, public=True)
async def mp_scrim(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Start a scrim in the current match."""
    if len(msg) != 1 \
    or not (rgx := re.match(r'^(?:bo)?(\d{1,2})$', msg[0])):
        return 'Invalid syntax: !mp scrim <bo#>'

    if not 0 <= (best_of := int(rgx[1])) < 16:
        return 'Best of must be in range 0-15.'

    winning_pts = (best_of // 2) + 1

    if winning_pts != 0:
        # setting to real num
        if m.winning_pts != 0:
            return 'Already scrimming!'

        if ~winning_pts & 1:
            return 'Best of must be an odd number!'

        msg = (f'A scrimmage has been started by {p.name}; '
               f'first to {winning_pts} points wins. Best of luck!')
    else:
        # setting to 0
        if m.winning_pts == 0:
            return 'Not currently scrimming!'

        msg = 'Scrimming cancelled.'

    m.winning_pts = winning_pts
    m.match_points.clear()

    return msg

# Mappool commands

@mp_commands.add(triggers=['lp', 'loadpool'], priv=Privileges.Normal, public=True)
async def mp_loadpool(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Load a specified mappool into the current match."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp loadpool <name>'

    if p is not m.host:
        return 'Only available to the host.'

    name = msg[0]

    if not (pool := glob.pools.get(name)):
        return 'Could not find a pool with that name!'

    if m.pool is pool:
        return f'{pool!r} already selected!'

    m.pool = pool
    return f'{pool!r} selected.'

@mp_commands.add(priv=Privileges.Normal, public=True)
async def mp_ban(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Ban a specified pick in the current pool from being picked."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp ban <mods#>'

    if not m.pool:
        return 'No pool currently selected!'

    mods_slot = msg[0]

    # separate mods & slot
    if not (rgx := re.match(r'^([a-zA-Z]+)([0-9]+)$', mods_slot)):
        return 'Invalid <mods#> syntax; correct example: "hd2".'

    mods = Mods.from_str(rgx[1])
    slot = int(rgx[2])

    if (mods, slot) not in m.pool.maps:
        return f'Found no {mods_slot} pick in the pool.'

    if (mods, slot) in m.bans:
        return 'That pick is already banned!'

    m.bans.add((mods, slot))
    return f'{mods_slot} banned.'

@mp_commands.add(priv=Privileges.Normal, public=True)
async def mp_pick(p: Player, m: Match, msg: Sequence[str]) -> str:
    """Pick a map from the currently selected mappool."""
    if len(msg) != 1:
        return 'Invalid syntax: !mp pick <mods#>'

    if not m.pool:
        return 'No pool currently selected!'

    mods_slot = msg[0]

    # separate mods & slot
    if not (rgx := re.match(r'^([a-zA-Z]+)([0-9]+)$', mods_slot)):
        return 'Invalid <mods#> syntax; correct example: "hd2".'

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

""" Event management commands
# The commands below are for event managers
# and tournament hosts/referees to help automate
# tedious processes of running tournaments.
"""

@pool_commands.add(triggers=['create', 'c'], priv=Privileges.Tournament, public=False)
async def pool_create(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Add a new mappool to the database."""
    if len(msg) != 1:
        return 'Invalid syntax: !pool create <name>'

    name = msg[0]

    if glob.pools.get(name):
        return 'Pool already exists with that name!'

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

    glob.pools.add(MapPool(**res))

    return f'{name} created.'

@pool_commands.add(triggers=['delete', 'd'], priv=Privileges.Tournament, public=False)
async def pool_delete(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Remove a mappool from the database."""
    if len(msg) != 1:
        return 'Invalid syntax: !pool delete <name>'

    name = msg[0]

    if not (pool := glob.pools.get(name)):
        return 'Could not find a pool with that name!'

    # delete from db
    await glob.db.execute(
        'DELETE FROM tourney_pools '
        'WHERE name = %s',
        [name]
    )

    # remove from cache
    glob.pools.remove(pool)

    return f'{name} deleted.'

@pool_commands.add(triggers=['add', 'a'], priv=Privileges.Tournament, public=False)
async def pool_add(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Add a new map to a mappool in the database."""
    if len(msg) != 2:
        return 'Invalid syntax: !pool add <name> <mods#>'

    if not p.last_np:
        return 'Please /np a map first!'

    name, mods_slot = msg

    # separate mods & slot
    if not (rgx := re.match(r'^([a-zA-Z]+)([0-9]+)$', mods_slot)):
        return 'Invalid <mods#> syntax; correct example: "hd2".'

    if not ~len(rgx[1]) & 1:
        return 'Invalid mods.'

    mods = int(Mods.from_str(rgx[1]))
    slot = int(rgx[2])

    if not (pool := glob.pools.get(name)):
        return 'Could not find a pool with that name!'

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

@pool_commands.add(triggers=['remove', 'r'], priv=Privileges.Tournament, public=False)
async def pool_remove(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Remove a map from a mappool in the database."""
    if len(msg) != 2:
        return 'Invalid syntax: !pool remove <name> <mods#>'

    name, mods_slot = msg

    # separate mods & slot
    if not (rgx := re.match(r'^([a-zA-Z]+)([0-9]+)$', mods_slot)):
        return 'Invalid <mods#> syntax; correct example: "hd2".'

    mods = Mods.from_str(rgx[1])
    slot = int(rgx[2])

    if not (pool := glob.pools.get(name)):
        return 'Could not find a pool with that name!'

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

@pool_commands.add(triggers=['list', 'l'], priv=Privileges.Tournament, public=False)
async def pool_list(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """List all existing mappools information."""

    if not (pools := glob.pools.pools):
        return 'There are currently no pools!'

    l = [f'Mappools ({len(pools)})']

    for pool in pools:
        l.append(f'[{pool.created_at:%Y-%m-%d}] {pool.id}. {pool.name}, by {pool.created_by}.')

    return '\n'.join(l)

@pool_commands.add(triggers=['info', 'i'], priv=Privileges.Tournament, public=False)
async def pool_info(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Get all information for a specific mappool."""
    if len(msg) != 1:
        return 'Invalid syntax: !pool info <name>'

    name = msg[0]

    if not (pool := glob.pools.get(name)):
        return 'Could not find a pool with that name!'

    _time = pool.created_at.strftime('%H:%M:%S%p')
    _date = pool.created_at.strftime('%Y-%m-%d')
    datetime_fmt = f'Created at {_time} on {_date}'
    l = [f'{pool.id}. {pool.name}, by {pool.created_by} | {datetime_fmt}']

    for (mods, slot), bmap in pool.maps.items():
        l.append(f'{mods!r}{slot}: {bmap.embed}')

    return '\n'.join(l)

@pool_commands.add(triggers=['help', 'h'], priv=Privileges.Tournament, public=False)
async def pool_help(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    cmds = []

    for cmd in pool_commands.commands:
        if not cmd.doc or not p.priv & cmd.priv:
            # no doc, or insufficient permissions.
            continue

        cmds.append(f'!pool {cmd.triggers[0]}: {cmd.doc}')

    return '\n'.join(cmds)

async def process_commands(p: Player, t: Messageable,
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

                if p not in m.refs or not p.priv & Privileges.Tournament:
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
                    'public': cmd.public
                }

            return {'public': True}
