# -*- coding: utf-8 -*-

from typing import List, Optional, Union
from time import time
from random import randrange

from objects import glob
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges
import packets

# TODO: context object?
# for now i'll just send in player, channel and
# msg split (trigger won't be included in split)
Messageable = Union[Channel, Player]

# TODO: Tuple rather than str for msg

def roll(p: Player, c: Messageable, msg: List[str]) -> str:
    maxPoints = ( # Cap !roll to 32767
        len(msg) and msg[0].isnumeric() and min(int(msg[0]), 32767)
    ) or 100

    points = randrange(0, maxPoints)
    return f'{p.name} rolls {points} points!'

def rtx(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) != 2:
        return 'Invalid syntax.'

    if not (t := glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(packets.RTX(msg[1]))
    return 'pong'

def alert(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) < 1:
        return 'Invalid syntax.'

    glob.players.broadcast(packets.notification(' '.join(msg)))
    return 'Alert sent.'

def alert_user(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) < 2:
        return 'Invalid syntax.'

    if not (t := glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(packets.notification(' '.join(msg[1:])))
    return 'Alert sent.'

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
    }
)

def process_commands(client: Player, target: Messageable, msg: str) -> bool:
    # Return whether we actually hit any commands.
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
