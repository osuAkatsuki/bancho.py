# -*- coding: utf-8 -*-

from typing import List, Optional, Union

from objects import glob
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges
import packets

# TODO: context object?
# for now i'll just send in player, channel and
# msg split (trigger won't be included in split)
Messageable = Union[Channel, Player]

def help(p: Player, c: Messageable, msg: List[str]) -> Optional[str]:
    if not msg or len(msg) > 1:
        return 'Invalid syntax.'

    return 'yAYeayEYAEYAEAEYEAYEA'

def rtx(p: Player, c: Messageable, msg: List[str]) -> str:
    if len(msg) != 2:
        return 'Invalid syntax.'

    if not (t := glob.players.get_by_name(msg[0])):
        return 'Could not find a user by that name.'

    t.enqueue(packets.RTX(msg[1]))
    return 'pong'

glob.commands = (
    {
        'trigger': '!help',
        'callback': help,
        'priv': Privileges.Verified
    },
    {
        'trigger': '!rtx',
        'callback': rtx,
        'priv': Privileges.Dangerous
    }
)

def process_commands(p: Player, c: Messageable, msg: str) -> bool:
    # Return whether we actually hit any commands.

    split = msg.split(' ')

    for cmd in glob.commands:
        if split[0] == cmd['trigger'] and p.priv & cmd['priv']:
            # Command found & we have privileges - run it.
            if (res := cmd['callback'](p, c, split[1:])):
                # Returned a message for us to send back.
                c.enqueue(packets.sendMessage(glob.config.botname, res, c.name, 1))
            return True

    return False
