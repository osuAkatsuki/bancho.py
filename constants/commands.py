# -*- coding: utf-8 -*-

from pp.owoppai import Owoppai
from typing import Sequence, Optional, Union, Callable
import time
import cmyui
import random
from collections import defaultdict

import packets
from objects import glob
from objects.player import Player
from objects.channel import Channel
from objects.beatmap import Beatmap, RankedStatus
from objects.match import Match, SlotStatus
from constants.privileges import Privileges
from constants.mods import Mods

Messageable = Union[Channel, Player]
CommandResponse = dict[str, str]

# not sure if this should be in glob or not,
# trying to think of some use cases lol..
glob.commands = []

def command(priv: Privileges, public: bool,
            trigger: Optional[str] = None) -> Callable:
    def register_callback(callback: Callable):
        glob.commands.append({
            'trigger': trigger or f'!{callback.__name__}',
            'callback': callback,
            'priv': priv,
            'public': public,
            'doc': callback.__doc__
        })

        return callback
    return register_callback

""" User commands
# The commands below are not considered dangerous,
# and are granted to any unbanned players.
"""

@command(trigger='!help', priv=Privileges.Normal, public=False)
async def _help(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Show information of all documented commands `p` can use."""
    return '\n'.join('{trigger}: {doc}'.format(**cmd)
                     for cmd in glob.commands if cmd['doc']
                     if p.priv & cmd['priv'])

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
async def last(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Show information about your most recent score."""
    if not (s := p.recent_score):
        return 'No scores found :o'

    return (f'[{s.mode!r}] {s.bmap.embed} {s.mods!r} {s.acc:.2f}% | '
            f'{s.pp:.2f}pp #{s.rank}')

@command(priv=Privileges.Normal, public=False)
async def mapsearch(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Search map titles with user input as a wildcard."""
    if not msg:
        return 'Invalid syntax: !mapsearch <title>'

    if not (res := await glob.db.fetchall(
        'SELECT id, set_id, artist, title, version '
        'FROM maps WHERE title LIKE %s '
        'LIMIT 50', [f'%{" ".join(msg)}%']
    )): return 'No matches found :('

    mirror = glob.config.mirror

    return '\n'.join(
        '[https://osu.ppy.sh/b/{id} {artist} - {title} [{version}]] '
        '([{mirror}/d/{set_id} download])'.format(**row, mirror=mirror)
        for row in res
    ) + f'\nMaps: {len(res)}'

# TODO: refactor with acc and more stuff
@command(trigger='!with', priv=Privileges.Normal, public=False)
async def _with(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Specify custom accuracy & mod combinations with `/np`."""
    if isinstance(c, Channel) or c.id != 1:
        return 'This command can only be used in DM with Aika.'

    if not p.last_np:
        return 'Please /np a map first!'

    # +?<mods> <acc>%?
    if 1 < len(msg) > 2:
        return 'Invalid syntax: !with <mods/acc> ...'

    mods = acc = None

    for param in (p.strip('+%') for p in msg):
        if cmyui._isdecimal(param, _float=True):
            acc = float(param)
        elif ~len(param) & 1: # len(param) % 2 == 0
            mods = Mods.from_str(param)
        else:
            return 'Invalid syntax: !with <mods/acc> ...'

    _msg = [p.last_np.embed]
    if not mods:
        mods = Mods.NOMOD

    _msg.append(repr(mods))

    if acc:
        # they're requesting pp for specified acc value.
        async with Owoppai(p.last_np.id, acc=acc, mods=mods) as owo:
            await owo.calc()
            pp_values = [(owo.acc, owo.pp)]
    else:
        # they're requesting pp for general accuracy values.
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
    'rank': 2,
    'unrank': 0,
    'love': 5
}[s]
@command(trigger='!map', priv=Privileges.Nominator, public=True)
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
            'UPDATE maps SET status = %s '
            'WHERE set_id = %s',
            [new_status, p.last_np.set_id]
        )

        for cached in glob.cache['beatmap'].values():
            # not going to bother checking timeout
            if cached['map'].set_id == p.last_np.set_id:
                cached['map'].status = RankedStatus(new_status)

    else:
        # update only map
        await glob.db.execute(
            'UPDATE maps SET status = %s '
            'WHERE id = %s',
            [new_status, p.last_np.id]
        )

        for cached in glob.cache['beatmap'].values():
            # not going to bother checking timeout
            if cached['map'].id == p.last_np.id:
                cached['map'].status = RankedStatus(new_status)
                break

    return 'Map updated!'

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

@command(trigger='!alertu', priv=Privileges.Admin, public=False)
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

@command(trigger='!switchserv', priv=Privileges.Dangerous, public=False)
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

# XXX: not very useful, mostly just for testing/fun.
@command(trigger='!spack', priv=Privileges.Dangerous, public=False)
async def send_empty_packet(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Send a specific (empty) packet by id to a player."""
    if len(msg) < 2 or not msg[-1].isdecimal():
        return 'Invalid syntax: !spack <name> <packetid>'

    if not (t := await glob.players.get_by_name(' '.join(msg[:-1]))):
        return 'Could not find a user by that name.'

    packet = packets.BanchoPacket(int(msg[-1]))
    t.enqueue(packets.write(packet))
    return f'Wrote {packet!r} to {t}.'

@command(priv=Privileges.Dangerous, public=False)
async def debug(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """Toggle the console's debug setting."""
    glob.config.debug = not glob.config.debug
    return f"Toggled {'on' if glob.config.debug else 'off'}."

str_to_priv = lambda p: defaultdict(lambda: None, {
    'normal': Privileges.Normal,
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
    priv = [str_to_priv(i) for i in set(''.join(msg[1:]).replace(' ', '').lower().split('|'))]
    if any(x is None for x in priv):
        return 'Invalid privileges.'

    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return 'Could not find user.'

    await glob.db.execute('UPDATE users SET priv = %s WHERE id = %s',
                    [newpriv := sum(priv), t.id])

    t.priv = Privileges(newpriv)
    return 'Success.'

# temp command, to illustrate how menu options will work
@command(trigger='men', priv=Privileges.Dangerous, public=False)
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
# like `!ev return await glob.players.get_by_name('cmyui').status.action`
# or for anything while debugging on-the-fly..
@command(priv=Privileges.Dangerous, public=False)
async def ex(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    # create the new coroutine definition as a string
    # with the lines from our message (split by '\n').
    lines = ' '.join(msg).split(r'\n')
    definition = '\n '.join(['async def __ex():'] + lines)

    try:
        # define, and run the coroutine
        exec(definition)
        ret = await locals()['__ex']() # type: ignore
    except Exception as e:
        # code was invalid, return
        # the error in the osu! chat.
        return str(e)

    return ret if ret else 'Success'

""" Multiplayer commands
# The commands below are specifically for
# multiplayer match management.
"""

# start a match.
async def mp_start(p: Player, m: Match, msg: Sequence[str]) -> str:
    for s in m.slots:
        if s.status & SlotStatus.has_player \
        and not s.status & SlotStatus.no_map:
            s.status = SlotStatus.playing

    m.in_progress = True
    m.enqueue(packets.matchStart(m))
    return 'Good luck!'

# abort a match in progress.
async def mp_abort(p: Player, m: Match, msg: Sequence[str]) -> str:
    if not m.in_progress:
        return 'Abort what?'

    for s in m.slots:
        if s.status & SlotStatus.playing:
            s.status = SlotStatus.not_ready

    m.in_progress = False
    m.enqueue(packets.updateMatch(m))
    m.enqueue(packets.matchAbort())
    return 'Match aborted.'

# force a player into a multiplayer match by name.
async def mp_force(p: Player, m: Match, msg: Sequence[str]) -> str:
    if len(msg) < 1:
        return 'Invalid syntax: !mp force <name>'

    if not (t := await glob.players.get_by_name(' '.join(msg))):
        return 'Could not find a user by that name.'

    await t.join_match(m)
    return 'Welcome.'

# set the current beatmap (by id).
async def mp_map(p: Player, m: Match, msg: Sequence[str]) -> str:
    if len(msg) < 1 or not msg[0].isdecimal():
        return 'Invalid syntax: !mp map <beatmapid>'

    if not (bmap := await Beatmap.from_bid(int(msg[0]))):
        return 'Beatmap not found.'

    m.bmap = bmap
    m.enqueue(packets.updateMatch(m))
    return f'Map selected: {bmap.embed}.'

_mp_triggers = defaultdict(lambda: None, {
    'force': {
        'callback': mp_force,
        'priv': Privileges.Admin
    },
    'abort': {
        'callback': mp_abort,
        'priv': Privileges.Normal
    },
    'start': {
        'callback': mp_start,
        'priv': Privileges.Normal
    },
    'map': {
        'callback': mp_map,
        'priv': Privileges.Normal
    }
})

@command(trigger='!mp', priv=Privileges.Normal, public=True)
async def multiplayer(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    """A parent command to subcommands for multiplayer match manipulation."""
    # used outside of a multiplayer match.
    if not (c._name.startswith('#multi_') and (m := p.match)):
        return

    # no subcommand specified, send back a list.
    if not msg:
        # TODO: maybe filter to only the commands they can actually use?
        return f"Available subcommands: {', '.join(_mp_triggers.keys())}."

    # no valid subcommands triggered.
    if not (trigger := _mp_triggers[msg[0]]):
        return 'Invalid subcommand.'

    # missing privileges to use mp commands.
    if not (p == m.host or p.priv & Privileges.Tournament):
        return

    # missing privileges to run this specific mp command.
    if not p.priv & trigger['priv']:
        return

    # forward the params to the specific command.
    # XXX: here, rather than sending the channel
    # as the 2nd arg, we'll send the match obj.
    # this is used much more frequently, and we've
    # already asserted than p.match.chat == c anyways.
    return await trigger['callback'](p, m, msg[1:])

async def process_commands(p: Player, t: Messageable,
                           msg: str) -> Optional[CommandResponse]:
    # response is either a CommandResponse if we hit a command,
    # or simply False if we don't have any command hits.
    st = time.time_ns()
    trigger, *args = msg.strip().split(' ')

    for cmd in glob.commands:
        if trigger == cmd['trigger'] and p.priv & cmd['priv']:
            # command found & we have privileges - run it.
            if (res := await cmd['callback'](p, t, args)):
                # returned a message for us to send back.
                # print elapsed time in milliseconds.
                time_taken = (time.time_ns() - st) / 1000000

                return {
                    'resp': f'{res} | Elapsed: {time_taken:.2f}ms',
                    'public': cmd['public']
                }

            return {'public': True}
