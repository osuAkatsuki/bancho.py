# -*- coding: utf-8 -*-

from typing import Tuple
from time import time
from datetime import datetime as dt, timezone as tz
from bcrypt import checkpw

import packets
from console import *
from constants import Type, Mods
from objects import glob
from objects.player import Player

# PacketID: 0
def readStatus(p: Player, pr: packets.PacketReader) -> None:
    data = pr.read(
        Type.i8, # actionType
        Type.string, # infotext
        Type.string, # beatmap md5
        Type.i32, # mods
        Type.i8, # gamemode
        Type.i32 # beatmapid
    )

    p.status.update(*data) # TODO: probably refactor some status stuff
    p.rx = p.status.mods & Mods.RELAX > 0
    glob.players.broadcast(packets.userStats(p))

# PacketID: 1
def sendMessage(p: Player, pr: packets.PacketReader) -> None:
    # target_id only proto >= 14
    client, msg, target, target_id = pr.read(*([Type.string] * 3), Type.i32)

    if not (c := glob.channels.get(target)):
        printlog(f'{p.name} tried to write to non-existant {target}.', Ansi.YELLOW)
        return

    # Limit message length to 2048 characters
    msg = msg[:2045] + '...' if msg[2048:] else msg
    client, target_id = p.name, p.id

    # Don't enqueue to ourselves
    c.enqueue(packets.sendMessage(client, msg, target, target_id), {p.id})
    printlog(f'{p.name} @ {target}: {msg}', Ansi.GRAY, fd = 'logs/chat.log')

# PacketID: 2
def logout(p: Player, pr: packets.PacketReader) -> None:
    pr.ignore(4) # osu client sends \x00\x00\x00\x00 every time lol
    glob.players.remove(p)

    glob.players.broadcast(packets.logout(p.id))

    for c in p.channels:
        p.leave_channel(c)
        #c.leave(p) # player object oriented

    # stop spectating
    # leave match
    # remove match if only player

    printlog(f'{p.name} logged out.', Ansi.LIGHT_YELLOW)

# PacketID: 3
def statsUpdateRequest(p: Player, pr: packets.PacketReader) -> None:
    p.enqueue(packets.userStats(p))

# PacketID: 4
def ping(p: Player, pr: packets.PacketReader) -> None:
    p.ping_time = time()

# PacketID: 5
def login(data: bytes) -> Tuple[bytes, str]:
    # Login is a bit special, we return the response bytes
    # and token in a tuple so that we can pass it as a header
    # in our packetstream obj back in server.py
    username, pw_hash, user_data = [s for s in data.decode().split('\n') if s]
    build_name, utc_offset, display_city, client_hashes, pm_private = user_data.split('|')

    if not (res := glob.db.fetch(
        'SELECT id, name, priv, pw_hash FROM users WHERE name_safe = %s',
        [Player.ensure_safe(username)]
    )): return packets.loginResponse(-1), 'no' # account does not exist

    if not checkpw(pw_hash.encode(), res['pw_hash'].encode()):
        return packets.loginResponse(-1), 'no' # pw does not match

    p = Player(utc_offset = int(utc_offset), pm_private = int(pm_private), **res)
    glob.players.add(p)

    # No need to use packetstream here,
    # we're only dealing with body w/o headers.
    res = packets.BinaryArray()
    res += packets.loginResponse(p.id)
    res += packets.protocolVersion(19)
    res += packets.banchoPrivileges(p.bancho_priv)
    res += packets.notification(f'Welcome back to The Gulag (v{glob.version:.2f})')

    # channels
    res += packets.channelinfoEnd()
    for c in glob.channels.channels: # TODO: __iter__ and __next__ in all collections
        if p.priv & c.read == 0:
            continue # no priv to read

        res += packets.channelInfo(*c.basic_info)

        # Autojoinable channels
        if c.auto_join and p.join_channel(c):
            res += packets.channelJoin(c.name)

    # Update our new player's stats, and broadcast them.
    p.stats_from_sql_full()
    our_presence = packets.userPresence(p)
    our_stats = packets.userStats(p)

    res += our_presence
    res += our_stats

    # o for online, or other
    for o in glob.players.players: # TODO: __iter__ & __next__
        # TODO: variadic params for enqueue

        # Enqueue us to them
        o.enqueue(our_presence)
        o.enqueue(our_stats)

        # Enqueue them to us
        p.enqueue(packets.userPresence(o))
        p.enqueue(packets.userStats(o))

    res += packets.mainMenuIcon()
        # TODO: friends list

    printlog(f'{p.name} logged in.', Ansi.LIGHT_YELLOW)
    return bytes(res), p.token

# PacketID: 63
def channelJoin(p: Player, pr: packets.PacketReader) -> None:
    if not (chan := pr.read(Type.string)):
        printlog(f'{p.name} tried to join nonexistant channel {chan}')
        return

    chan = chan[0] # need refactor.. this will be an endless uphill battle

    if (c := glob.channels.get(chan)) and p.join_channel(c):
        p.enqueue(packets.channelJoin(chan))
    else:
        printlog(f'Failed to find channel {chan} that {p.name} attempted to join.')

# PacketID: 78
def channelPart(p: Player, pr: packets.PacketReader) -> None:
    if not (chan := pr.read(Type.string)):
        return

    chan = chan[0]

    if (c := glob.channels.get(chan)):
        p.leave_channel(c)
    else:
        printlog(f'Failed to find channel {chan} that {p.name} attempted to leave.')

# PacketID: 85
def statsRequest(p: Player, pr: packets.PacketReader) -> None:
    if len(pr.data) < 6:
        return

    userIDs = pr.read(Type.i32_list)
    is_online = lambda o: o in glob.players.ids

    for online in filter(is_online, userIDs):
        target = glob.players.get_by_id(online)
        p.enqueue(packets.userStats(target))

# PacketID: 97
def userPresenceRequest(p: Player, pr: packets.PacketReader) -> None:
    for id in pr.read(Type.i32_list):
        p.enqueue(packets.userPresence(id))
