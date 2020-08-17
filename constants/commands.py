# -*- coding: utf-8 -*-

from typing import List, Dict, Optional, Union, Callable
from time import time
from random import randrange
from re import match as re_match, compile as re_comp
from codecs import escape_decode
from collections import defaultdict

from objects import glob
from objects.player import Player
from objects.channel import Channel
from objects.match import Match, SlotStatus
from constants.privileges import Privileges
import packets

# TODO: context object?
# for now i'll just send in player, channel and
# msg split (trigger won't be included in split)
Messageable = Union[Channel, Player]
CommandResponse = Dict[str, str]

# Not sure if this should be in glob or not,
# trying to think of some use cases lol..
# Could be interesting?
glob.commands = []

def command(priv: Privileges, public: bool,
            trigger: Optional[str] = None) -> Callable:
    def register_callback(callback: Callable):
        glob.commands.append({
            'trigger': trigger if trigger else f'!{callback.__name__}',
            'callback': callback,
            'priv': priv,
            'public': public
        })

        return callback
    return register_callback

""" User commands
# The commands below are not considered dangerous,
# and are granted to any unrestricted players.
"""

# Send a random number between 1 and whatever they type (max 32767).
@command(priv=Privileges.Normal, public=True)
def roll(p: Player, c: Messageable, msg: List[str]) -> str:
    # Syntax: !roll <max>
    maxPoints = ( # Cap !roll to 32767 to prevent spam.
        msg and msg[0].isnumeric() and min(int(msg[0]), 32767)
    ) or 100

    points = randrange(0, maxPoints)
    return f'{p.name} rolls {points} points!'

# Send information about the user's most recent score.
@command(priv=Privileges.Normal, public=True)
def last(p: Player, c: Messageable, msg: List[str]) -> str:
    if not (s := p.recent_scores[p.status.game_mode]):
        return 'No recent score found for current mode!'

    return f'#{s.rank} @ {s.map.embed} ({s.pp:.2f}pp)'

# Find all maps matching %title%.
@command(priv=Privileges.Normal, public=False)
def mapsearch(p: Player, c: Messageable, msg: List[str]) -> str:
    if not (res := glob.db.fetchall(
        'SELECT id, set_id, artist, title, version '
        'FROM maps WHERE title LIKE %s '
        'LIMIT 50', [f'%{" ".join(msg)}%']
    )): return 'No matches found :('

    return '\n'.join(
        '[https://osu.gatari.pw/d/{set_id} DL] [https://osu.ppy.sh/b/{id} {artist} - {title} [{version}]]'.format(**row)
        for row in res
    ) + f'\nMaps: {len(res)}'

""" Nominators commands
# The commands below allow users to
# manage  the server's state of beatmaps.
"""

status_to_id = lambda s: {
    'rank': 2,
    'unrank': 0,
    'love': 5
}[s]
# Change the ranked status of the last beatmap /np'ed.
@command(priv=Privileges.Nominator, public=True)
def map(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) != 2 \
    or msg[0] not in {'rank', 'unrank', 'love'} \
    or msg[1] not in {'set', 'map'}:
        return 'Invalid syntax: !map <rank/unrank/love> <map/set>'

    if not p.last_np:
        return 'You must /np a map first!'

    _set = msg[0] == 'set'
    params = ('set_id', p.last_np.set_id) if _set \
        else ('id', p.last_np.id)

    glob.db.execute(
        f'UPDATE maps SET status = %s WHERE {params[0]} = %s',
        [status_to_id(msg[0]), params[1]]
    )
    return 'Map updated!'

""" Admin commands
# The commands below are relatively dangerous,
# and are generally for managing users.
"""

@command(priv=Privileges.Admin, public=False)
def ban(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) < 2:
        return 'Invalid syntax: !ban <name> <reason>'

    # Find any user matching (including offline).
    if not (t := glob.players.get_by_name(msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    t.restrict() # TODO: use reason as param?
    return f'{t} was banned.'

@command(priv=Privileges.Admin, public=False)
def unban(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) < 2:
        return 'Invalid syntax: !ban <name> <reason>'

    # Find any user matching (including offline).
    if not (t := glob.players.get_by_name(msg[0], sql=True)):
        return f'"{msg[0]}" not found.'

    if t.priv & Privileges.Staff and not p.priv & Privileges.Dangerous:
        return 'Only developers can manage staff members.'

    t.unrestrict() # TODO: use reason as param?
    return f'{t} was unbanned.'

# Send a notification to all players.
@command(priv=Privileges.Admin, public=False)
def alert(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) < 1:
        return 'Invalid syntax: !alert <msg>'

    glob.players.enqueue(packets.notification(' '.join(msg)))
    return 'Alert sent.'

# Send a notification to a specific user by name.
@command(trigger='!alertu', priv=Privileges.Admin, public=False)
def alert_user(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) < 2:
        return 'Invalid syntax: !alertu <name> <msg>'

    if not (t := glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(packets.notification(' '.join(msg[1:])))
    return 'Alert sent.'

""" Developer commands
# The commands below are either dangerous or
# simply not useful for any other roles.
"""

# Send an RTX request with a message to a user by name.
@command(priv=Privileges.Dangerous, public=False)
def rtx(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) != 2:
        return 'Invalid syntax: !rtx <name> <msg>'

    if not (t := glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(packets.RTX(msg[1]))
    return 'pong'

# Send a specific (empty) packet by id to a user.
# XXX: Not very useful, mostly just for testing/fun.
@command(trigger='!spack', priv=Privileges.Dangerous, public=False)
def send_empty_packet(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) < 2 or not msg[-1].isnumeric():
        return 'Invalid syntax: !spack <name> <packetid>'

    if not (t := glob.players.get_by_name(' '.join(msg[:-1]))):
        return 'Could not find a user by that name.'

    packet = packets.Packet(int(msg[-1]))
    t.enqueue(packets.write(packet))
    return f'Wrote {packet} to {t}.'

# This ones a bit spooky, so we'll take some extra precautions..
_sbytes_re = re_comp(r"^(?P<name>[\w \[\]-]{2,15}) '(?P<bytes>[\w \\\[\]-]+)'$")
# Send specific bytes to a user.
# XXX: Not very useful, mostly just for testing/fun.
@command(trigger='!sbytes', priv=Privileges.Dangerous, public=False)
def send_bytes(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) < 2:
        return 'Invalid syntax: !sbytes <name> <packetid>'

    content = ' '.join(msg)
    if not (re := re_match(_sbytes_re, content)):
        return 'Invalid syntax.'

    if not (t := glob.players.get_by_name(re['name'])):
        return 'Could not find a user by that name.'

    t.enqueue(escape_decode(re['bytes'])[0])
    return f'Wrote data to {t}.'

# Enable/disable debug printing to the console.
@command(priv=Privileges.Dangerous, public=False)
def debug(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) != 1 or msg[0] not in {'0', '1'}:
        return 'Invalid syntax.'

    glob.config.debug = msg[0] == '1'
    return 'Success.'

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
# Set permissions for a user (by username).
@command(priv=Privileges.Dangerous, public=False)
def setpriv(p: Player, c: Messageable, msg: List[str]) -> str:
    if (msg_len := len(msg)) < 2:
        return 'Invalid syntax: !setpriv <name> <role1 | role2 | ...>'

    # A mess that gets each unique privilege out of msg.
    priv = [str_to_priv(i) for i in set(''.join(msg[1:]).replace(' ', '').lower().split('|'))]
    if any(x is None for x in priv):
        return 'Invalid privileges.'

    if not (t := glob.players.get_by_name(msg[0])): # TODO: db?
        return 'Could not find user.'

    glob.db.execute('UPDATE users SET priv = %s WHERE id = %s',
                    [newpriv := sum(priv), t.id])

    t.priv = Privileges(newpriv)
    return 'Success.'

# XXX: This actually comes in handy sometimes, I initially
# wrote it completely as a joke, but I might keep it in for
# devs.. Comes in handy when debugging to be able to run something
# like `!ev print(glob.players.get_by_name('cmyui').status.action)`
# or for anything while debugging on-the-fly..
@command(priv=Privileges.Dangerous, public=False)
def ev(p: Player, c: Messageable, msg: List[str]) -> str:
    try: # pinnacle of the gulag
        eval(' '.join(msg))
    except Exception as e:
        return str(e)

""" Multiplayer commands
# The commands below are specifically for
# multiplayer match management.
"""

# Start a match.
def mp_start(p: Player, m: Match, msg: List[str]) -> str:
    for s in m.slots:
        if s.status & SlotStatus.has_player \
        and not s.status & SlotStatus.no_map:
            s.status = SlotStatus.playing

    m.in_progress = True
    m.enqueue(packets.matchStart(m))
    return 'Good luck!'

# Abort a match in progress.
def mp_abort(p: Player, m: Match, msg: List[str]) -> str:
    if not m.in_progress:
        return 'Abort what?'

    for s in m.slots:
        if s.status & SlotStatus.playing:
            s.status = SlotStatus.not_ready

    m.in_progress = False
    m.enqueue(packets.updateMatch(m))
    m.enqueue(packets.matchAbort())
    return 'Match aborted.'

# Force a user into a multiplayer match by username.
def mp_force(p: Player, m: Match, msg: List[str]) -> str:
    if len(msg) < 1:
        return 'Invalid syntax: !mp force <name>'

    if not (t := glob.players.get_by_name(' '.join(msg))):
        return 'Could not find a user by that name.'

    t.join_match(m)
    return 'Welcome.'

# Set the current beatmap (by id).
def mp_map(p: Player, m: Match, msg: List[str]) -> str:
    if len(msg) < 1 or not msg[0].isnumeric():
        return 'Invalid syntax: !mp map <beatmapid>'

    if not (res := glob.db.fetch(
        'SELECT id, md5, name '
        'FROM maps WHERE id = %s',
        [msg[0]], _dict = False     # return a tuple for
    )): return 'Beatmap not found.' # quick assignment

    m.map_id, m.map_md5, m.map_name = res
    m.enqueue(packets.updateMatch(m))

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
# Routing command for all !mp subcommands.
@command(trigger='!mp', priv=Privileges.Normal, public=True)
def multiplayer(p: Player, c: Messageable, msg: List[str]) -> str:
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
    return trigger['callback'](p, m, msg[1:])

def process_commands(p: Player, t: Messageable,
                     msg: str) -> Optional[CommandResponse]:
    # Basic commands setup for now.
    # Response is either a CommandResponse if we hit a command,
    # or simply False if we don't have any command hits.
    start_time = time()
    trigger, *args = msg.strip().split(' ')

    for cmd in glob.commands:
        if trigger == cmd['trigger'] and p.priv & cmd['priv']:
            # Command found & we have privileges - run it.
            if (res := cmd['callback'](p, t, args)):
                # Returned a message for us to send back.
                ms_taken = (time() - start_time) * 1000

                return {
                    'resp': f'{res} | Elapsed: {ms_taken:.2f}ms',
                    'public': cmd['public']
                }

            return {'public': True}
