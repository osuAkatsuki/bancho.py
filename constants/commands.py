# -*- coding: utf-8 -*-

from typing import List, Dict, Optional, Union
from time import time
from random import randrange
from re import match as re_match, compile as re_comp

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

# TODO: Tuple rather than str for msg

def roll(p: Player, c: Messageable, msg: List[str]) -> str:
    # Syntax: !roll (max)
    maxPoints = ( # Cap !roll to 32767
        len(msg) and msg[0].isnumeric() and min(int(msg[0]), 32767)
    ) or 100

    points = randrange(0, maxPoints)
    return f'{p.name} rolls {points} points!'

def rtx(p: Player, c: Messageable, msg: List[str]) -> str:
    # Syntax: !rtx <username> <message>
    if len(msg) != 2:
        return 'Invalid syntax.'

    if not (t := glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(packets.RTX(msg[1]))
    return 'pong'

def alert(p: Player, c: Messageable, msg: List[str]) -> str:
    # Syntax: !alert <message>
    if len(msg) < 1:
        return 'Invalid syntax.'

    glob.players.enqueue(packets.notification(' '.join(msg)))
    return 'Alert sent.'

def alert_user(p: Player, c: Messageable, msg: List[str]) -> str:
    # Syntax: !alertu <username> <message>
    if len(msg) < 2:
        return 'Invalid syntax.'

    if not (t := glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(packets.notification(' '.join(msg[1:])))
    return 'Alert sent.'

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
def send_bytes(p: Player, c: Messageable, msg: List[str]) -> str:
    # Syntax: !sbytes <username> <packetid>
    if len(msg) < 2:
        return 'Invalid syntax.'

    content = ' '.join(msg)
    if not (re := re_match(_sbytes_re, content)):
        return 'Invalid syntax.'

    if not (t := glob.players.get_by_name(re['name'])):
        return 'Could not find a user by that name.'

    t.enqueue(re['bytes'].encode())
    return f'Wrote data to {t}.'

glob.commands = (
    {
        'trigger': '!roll',
        'callback': roll,
        'priv': Privileges.Verified,
        'public': True
    }, {
        'trigger': '!rtx',
        'callback': rtx,
        'priv': Privileges.Dangerous,
        'public': False
    }, {
        'trigger': '!alert',
        'callback': alert,
        'priv': Privileges.Admin,
        'public': False
    }, {
        'trigger': '!alertu',
        'callback': alert_user,
        'priv': Privileges.Admin,
        'public': False
    }, {
        'trigger': '!spack',
        'callback': send_empty_packet,
        'priv': Privileges.Dangerous,
        'public': False
    }, {
        'trigger': '!sbytes',
        'callback': send_bytes,
        'priv': Privileges.Dangerous,
        'public': False
    }
)

def process_commands(client: Player, target: Messageable,
                     msg: str) -> Union[CommandResponse, bool]:
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
                taken = (time() - start_time) * 1000

                return {
                    'resp': f'{res} | Elapsed: {taken:.2f}ms',
                    'public': cmd['public']
                }

            return {'public': True}
    return False
