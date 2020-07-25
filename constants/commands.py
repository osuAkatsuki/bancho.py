# -*- coding: utf-8 -*-

from typing import List, Dict, Optional, Union, Callable
from time import time
from random import randrange
from re import match as re_match, compile as re_comp
from codecs import escape_decode

from objects import glob
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges
import packets

# TODO: context object?
# for now i'll just send in player, channel and
# msg split (trigger won't be included in split)
Messageable = Union[Channel, Player]
CommandResponse = Dict[str, str]

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

@command(priv=Privileges.Verified, public=True)
def roll(p: Player, c: Messageable, msg: List[str]) -> str:
    # Syntax: !roll <max>
    maxPoints = ( # Cap !roll to 32767
        msg and msg[0].isnumeric() and min(int(msg[0]), 32767)
    ) or 100

    points = randrange(0, maxPoints)
    return f'{p.name} rolls {points} points!'

@command(priv=Privileges.Dangerous, public=False)
def rtx(p: Player, c: Messageable, msg: List[str]) -> str:
    # Syntax: !rtx <username> <message>
    if len(msg) != 2:
        return 'Invalid syntax.'

    if not (t := glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(packets.RTX(msg[1]))
    return 'pong'

@command(priv=Privileges.Admin, public=False)
def alert(p: Player, c: Messageable, msg: List[str]) -> str:
    # Syntax: !alert <message>
    if len(msg) < 1:
        return 'Invalid syntax.'

    glob.players.enqueue(packets.notification(' '.join(msg)))
    return 'Alert sent.'

@command(trigger='!alertu', priv=Privileges.Admin, public=False)
def alert_user(p: Player, c: Messageable, msg: List[str]) -> str:
    # Syntax: !alertu <username> <message>
    if len(msg) < 2:
        return 'Invalid syntax.'

    if not (t := glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(packets.notification(' '.join(msg[1:])))
    return 'Alert sent.'

@command(trigger='!spack', priv=Privileges.Dangerous, public=False)
def send_empty_packet(p: Player, c: Messageable, msg: List[str]) -> str:
    # Syntax: !spack <username> <packetid>
    if len(msg) < 2 or not msg[-1].isnumeric():
        return 'Invalid syntax.'

    if not (t := glob.players.get_by_name(' '.join(msg[:-1]))):
        return 'Could not find a user by that name.'

    packet = packets.Packet(int(msg[-1]))
    t.enqueue(packets.write(packet))
    return f'Wrote {packet} to {t}.'

# This ones a bit spooky, so we'll take some extra precautions..
_sbytes_re = re_comp(r"^(?P<name>[\w \[\]-]{2,15}) '(?P<bytes>[\w \\\[\]-]+)'$")
@command(trigger='!sbytes', priv=Privileges.Dangerous, public=False)
def send_bytes(p: Player, c: Messageable, msg: List[str]) -> str:
    # Syntax: !sbytes <username> <packetid>
    if len(msg) < 2:
        return 'Invalid syntax.'

    content = ' '.join(msg)
    if not (re := re_match(_sbytes_re, content)):
        return 'Invalid syntax.'

    if not (t := glob.players.get_by_name(re['name'])):
        return 'Could not find a user by that name.'

    t.enqueue(escape_decode(re['bytes'])[0])
    return f'Wrote data to {t}.'

@command(priv=Privileges.Admin, public=False)
def mpforce(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) < 1:
        return 'Invalid syntax.'

    if not (t := glob.players.get_by_name(' '.join(msg))):
        return 'Could not find a user by that name.'

    t.join_match(p.match)
    return 'Welcome.'

def process_commands(client: Player, target: Messageable,
                     msg: str) -> Optional[CommandResponse]:
    # Basic commands setup for now.
    # Response is either a CommandResponse if we hit a command,
    # or simply False if we don't have any command hits.
    start_time = time()
    split = msg.strip().split(' ')

    for cmd in glob.commands:
        if split[0] == cmd['trigger'] and client.priv & cmd['priv']:
            # Command found & we have privileges - run it.
            if (res := cmd['callback'](client, target, split[1:])):
                # Returned a message for us to send back.
                ms_taken = (time() - start_time) * 1000

                return {
                    'resp': f'{res} | Elapsed: {ms_taken:.2f}ms',
                    'public': cmd['public']
                }

            return {'public': True}
