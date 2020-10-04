# -*- coding: utf-8 -*-

from typing import (Sequence, Optional,
                    Union, Callable)
import time
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

# Not sure if this should be in glob or not,
# trying to think of some use cases lol..
# Could be interesting?
glob.commands = []

def command(priv: Privileges, public: bool,
            trigger: Optional[str] = None,
            doc: Optional[str] = None) -> Callable:
    def register_callback(callback: Callable):
        glob.commands.append({
            'trigger': trigger if trigger else f'!{callback.__name__}',
            'callback': callback,
            'priv': priv,
            'public': public,
            'doc': doc
        })

        return callback
    return register_callback

""" User commands
# The commands below are not considered dangerous,
# and are granted to any unrestricted players.
"""

_help_doc = 'Show information of all documented commands.'
@command(priv=Privileges.Normal, public=False, doc=_help_doc)
async def help(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    return '\n'.join('{trigger}: {doc}'.format(**cmd)
                     for cmd in glob.commands if cmd['doc']
                     if p.priv & cmd['priv'])

_roll_doc = ('Roll an n-sided die where n is the '
             'number you write (100 if empty).')
@command(priv=Privileges.Normal, public=True, doc=_roll_doc)
async def roll(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    if msg and msg[0].isdecimal():
        # Cap roll to 32767 to prevent spam.
        max_roll = min(int(msg[0]), 32767)
    else:
        max_roll = 100

    points = random.randrange(0, max_roll)
    return f'{p.name} rolls {points} points!'

_last_doc = 'Show information about your most recent score.'
@command(priv=Privileges.Normal, public=True, doc=_last_doc)
async def last(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    mode = p.status.mode + ((p.rx and p.status.mode != 3) and 4)

    if not (s := p.recent_scores[mode]):
        return 'No recent score found for current mode!'

    return (f'[{s.mode!r}] {s.bmap.embed} {s.mods!r} {s.acc:.2f}% | '
            f'{s.pp:.2f}pp #{s.rank}')

_mapsearch_doc = ('Search map titles with '
                  'user input as a wildcard.')
@command(priv=Privileges.Normal, public=False, doc=_mapsearch_doc)
async def mapsearch(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    if not (res := await glob.db.fetchall(
        'SELECT id, set_id, artist, title, version '
        'FROM maps WHERE title LIKE %s '
        'LIMIT 50', [f'%{" ".join(msg)}%']
    )): return 'No matches found :('

    return '\n'.join(
        '[https://osu.gatari.pw/d/{set_id} DL] '
        '[https://osu.ppy.sh/b/{id} {artist} - {title} [{version}]]'.format(**row)
        for row in res
    ) + f'\nMaps: {len(res)}'

# TODO: refactor with acc and more stuff
_mods_doc = ('Adjust the mods for a '
             'pp-calculation request.')
@command(priv=Privileges.Normal, public=False, doc=_mods_doc)
async def mods(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    if isinstance(c, Channel) or c.id != 1:
        return 'This command can only be used in DM with Aika.'

    if not p.last_np:
        return 'Please /np a map first!'

    msg = ''.join(msg).replace(' ', '')
    if msg[0] == '+': # remove +
        msg = msg[1:]

    mods = Mods.from_str(msg)

    if mods not in p.last_np.pp_cache:
        # cach
        await p.last_np.cache_pp(mods)

    # Since this is a DM to the bot, we should
    # send back a list of general PP values.
    # TODO: !acc and !mods in commands to
    #       modify these values :P
    _msg = [p.last_np.embed]
    if mods:
        _msg.append(f'{mods!r}')

    msg = f"{' '.join(_msg)}: " + ' | '.join(
        f'{acc}%: {pp:.2f}pp'
        for acc, pp in zip(
            (90, 95, 98, 99, 100),
            p.last_np.pp_cache[mods]
        ))

    return msg

""" Nominators commands
# The commands below allow users to
# manage  the server's state of beatmaps.
"""

status_to_id = lambda s: {
    'rank': 2,
    'unrank': 0,
    'love': 5
}[s]
_map_doc = ("Changes the ranked status of "
            "the most recently /np'ed map.")
@command(priv=Privileges.Nominator, public=True, doc=_map_doc)
async def map(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    if len(msg) != 2 \
    or msg[0] not in ('rank', 'unrank', 'love') \
    or msg[1] not in ('set', 'map'):
        return 'Invalid syntax: !map <rank/unrank/love> <map/set>'

    if not p.last_np:
        return 'You must /np a map first!'

    new_status = status_to_id(msg[0])

    # update sql & cache based on scope
    # XXX: not sure if getting md5s from sql
    # for updating cache would be faster?
    # surely this will not scale as well..

    if msg[1] == 'set': # update whole set
        await glob.db.execute(
            'UPDATE maps SET status = %s '
            'WHERE set_id = %s',
            [new_status, p.last_np.set_id]
        )

        for cached in glob.cache['beatmap'].values():
            # not going to bother checking timeout
            if cached['map'].set_id == p.last_np.set_id:
                cached['map'].status = RankedStatus(new_status)

    else: # update only map
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

_ban_doc = "Ban a player's account, with a reason."
@command(priv=Privileges.Admin, public=False, doc=_ban_doc)
async def ban(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    if len(msg) < 2:
        return 'Invalid syntax: !ban <name> <reason>'

    # Find any user matching (including offline).
    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    await t.restrict() # TODO: use reason as param?
    return f'{t} was banned.'

_unban_doc = "Unban a player's account, with a reason."
@command(priv=Privileges.Admin, public=False, doc=_unban_doc)
async def unban(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    if len(msg) < 2:
        return 'Invalid syntax: !ban <name> <reason>'

    # Find any user matching (including offline).
    if not (t := await glob.players.get_by_name(msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    await t.unrestrict() # TODO: use reason as param?
    return f'{t} was unbanned.'

_alert_doc = 'Send a notification to all players.'
@command(priv=Privileges.Admin, public=False, doc=_alert_doc)
async def alert(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    if len(msg) < 1:
        return 'Invalid syntax: !alert <msg>'

    glob.players.enqueue(await packets.notification(' '.join(msg)))
    return 'Alert sent.'

_alertu_doc = 'Send a notification to a specific player by name.'
@command(trigger='!alertu', priv=Privileges.Admin, public=False, doc=_alertu_doc)
async def alert_user(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    if len(msg) < 2:
        return 'Invalid syntax: !alertu <name> <msg>'

    if not (t := await glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(await packets.notification(' '.join(msg[1:])))
    return 'Alert sent.'

""" Developer commands
# The commands below are either dangerous or
# simply not useful for any other roles.
"""

_switch_doc = 'Switch servers to a specified ip address.'
@command(priv=Privileges.Dangerous, public=False, doc=_switch_doc)
async def switch(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    if len(msg) != 1:
        return 'Invalid syntax: !switch <ip>'

    p.enqueue(await packets.switchTournamentServer(msg[0]))
    return 'Have a nice journey..'

_rtx_doc = 'Send an RTX packet with a message to a user.'
@command(priv=Privileges.Dangerous, public=False, doc=_rtx_doc)
async def rtx(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    if len(msg) != 2:
        return 'Invalid syntax: !rtx <name> <msg>'

    if not (t := await glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(await packets.RTX(msg[1]))
    return 'pong'

# XXX: Not very useful, mostly just for testing/fun.
_spack_doc = 'Send a specific (empty) packet by id to a player.'
@command(trigger='!spack', priv=Privileges.Dangerous, public=False, doc=_spack_doc)
async def send_empty_packet(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    if len(msg) < 2 or not msg[-1].isdecimal():
        return 'Invalid syntax: !spack <name> <packetid>'

    if not (t := await glob.players.get_by_name(' '.join(msg[:-1]))):
        return 'Could not find a user by that name.'

    packet = packets.BanchoPacket(int(msg[-1]))
    t.enqueue(await packets.write(packet))
    return f'Wrote {packet} to {t}.'

_debug_doc = "Toggle the console's debug setting."
@command(priv=Privileges.Dangerous, public=False, doc=_debug_doc)
async def debug(p: Player, c: Messageable, msg: Sequence[str]) -> str:
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
_setpriv_doc = 'Set privileges for a player (by name).'
@command(priv=Privileges.Dangerous, public=False, doc=_setpriv_doc)
async def setpriv(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    if len(msg) < 2:
        return 'Invalid syntax: !setpriv <name> <role1 | role2 | ...>'

    # A mess that gets each unique privilege out of msg.
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

# temp command
@command(priv=Privileges.Dangerous, public=False)
async def menu(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    async def callback():
        p.enqueue(await packets.notification('yay!'))

    opt_id = await p.add_to_menu(callback)
    return f'[osu://dl/{opt_id} option]'

# XXX: This actually comes in handy sometimes, I initially
# wrote it completely as a joke, but I might keep it in for
# devs.. Comes in handy when debugging to be able to run something
# like `!ev print(await glob.players.get_by_name('cmyui').status.action)`
# or for anything while debugging on-the-fly..
@command(priv=Privileges.Dangerous, public=False)
async def ex(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    lines = '\n '.join(' '.join(msg).split('\\n'))
    try: # pinnacle of the gulag
        exec(f"async def __ex():\n {lines}")
        ret = await locals()['__ex']()
        return ret if ret else 'Success'
    except Exception as e:
        return str(e)

""" Multiplayer commands
# The commands below are specifically for
# multiplayer match management.
"""

# Start a match.
async def mp_start(p: Player, m: Match, msg: Sequence[str]) -> str:
    for s in m.slots:
        if s.status & SlotStatus.has_player \
        and not s.status & SlotStatus.no_map:
            s.status = SlotStatus.playing

    m.in_progress = True
    m.enqueue(await packets.matchStart(m))
    return 'Good luck!'

# Abort a match in progress.
async def mp_abort(p: Player, m: Match, msg: Sequence[str]) -> str:
    if not m.in_progress:
        return 'Abort what?'

    for s in m.slots:
        if s.status & SlotStatus.playing:
            s.status = SlotStatus.not_ready

    m.in_progress = False
    m.enqueue(await packets.updateMatch(m))
    m.enqueue(await packets.matchAbort())
    return 'Match aborted.'

# Force a user into a multiplayer match by username.
async def mp_force(p: Player, m: Match, msg: Sequence[str]) -> str:
    if len(msg) < 1:
        return 'Invalid syntax: !mp force <name>'

    if not (t := await glob.players.get_by_name(' '.join(msg))):
        return 'Could not find a user by that name.'

    await t.join_match(m)
    return 'Welcome.'

# Set the current beatmap (by id).
async def mp_map(p: Player, m: Match, msg: Sequence[str]) -> str:
    if len(msg) < 1 or not msg[0].isdecimal():
        return 'Invalid syntax: !mp map <beatmapid>'

    if not (bmap := await Beatmap.from_bid(int(msg[0]))):
        return 'Beatmap not found.'

    m.bmap = bmap
    m.enqueue(await packets.updateMatch(m))
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
_mp_doc = ('A parent command to subcommands '
           'for multiplayer match manipulation.')
@command(trigger='!mp', priv=Privileges.Normal, public=True, doc=_mp_doc)
async def multiplayer(p: Player, c: Messageable, msg: Sequence[str]) -> str:
    # Used outside of a multiplayer match.
    if not (c._name.startswith('#multi_') and (m := p.match)):
        return

    # No subcommand specified, send back a list.
    if not msg:
        # TODO: maybe filter to only the commands they can actually use?
        return f"Available subcommands: {', '.join(_mp_triggers.keys())}."

    # No valid subcommands triggered.
    if not (trigger := _mp_triggers[msg[0]]):
        return 'Invalid subcommand.'

    # Missing privileges to use mp commands.
    if not (p == m.host or p.priv & Privileges.Tournament):
        return

    # Missing privileges to run this specific mp command.
    if not p.priv & trigger['priv']:
        return

    # Forward the params to the specific command.
    # XXX: Here, rather than sending the channel
    # as the 2nd arg, we'll send the match obj.
    # This is used much more frequently, and we've
    # already asserted than p.match.chat == c anyways.
    return await trigger['callback'](p, m, msg[1:])

async def process_commands(p: Player, t: Messageable,
                           msg: str) -> Optional[CommandResponse]:
    # Basic commands setup for now.
    # Response is either a CommandResponse if we hit a command,
    # or simply False if we don't have any command hits.
    st = time.time_ns()
    trigger, *args = msg.strip().split(' ')

    for cmd in glob.commands:
        if trigger == cmd['trigger'] and p.priv & cmd['priv']:
            # Command found & we have privileges - run it.
            if (res := await cmd['callback'](p, t, args)):
                # Returned a message for us to send back.
                # Print elapsed time in milliseconds.
                time_taken = (time.time_ns() - st) / 1000000

                return {
                    'resp': f'{res} | Elapsed: {time_taken:.2f}ms',
                    'public': cmd['public']
                }

            return {'public': True}
