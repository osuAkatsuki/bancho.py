# -*- coding: utf-8 -*-

from typing import Tuple
from time import time

import packets
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
    p.rx = p.status.mods & Mods.RELAX
    glob.players.broadcast(packets.userStats(p))

# PacketID: 2
def logout(p: Player, pr: packets.PacketReader) -> None:
    glob.players.remove(p)

    glob.players.broadcast(packets.logout(p.id))

    for c in p.channels:
        p.leave_channel(c)
        #c.leave(p) # player object oriented

    # stop spectating
    # leave match
    # remove match if only player

    print(f'{p.name} logged out.')

# PacketID: 3
def statsUpdateRequest(p: Player, pr: packets.PacketReader) -> None:
    p.enqueue(packets.userStats(p))

# PacketID: 4
def ping(p: Player, pr: packets.PacketReader) -> None:
    p.time = time()

# PacketID: 63
def channelJoin(p: Player, pr: packets.PacketReader) -> None:
    if not (chan := pr.read(Type.string)):
        print(f'{p.name} tried to join nonexistant channel {chan}')
        return

    chan = chan[0] # need refactor.. this will be an endless uphill battle

    if (c := glob.channels.get(chan)) and p.join_channel(c):
        p.enqueue(packets.channelJoin(chan))
    else:
        print(f'Failed to find channel {chan} that {p.name} attempted to join.')

# PacketID: 78
def channelPart(p: Player, pr: packets.PacketReader) -> None:
    if not (chan := pr.read(Type.string)):
        return

    chan = chan[0]

    if (c := glob.channels.get(chan)):
        p.leave_channel(c)
    else:
        print(f'Failed to find channel {chan} that {p.name} attempted to leave.')

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

# Login is a bit special, we return the response bytes
# and token in a tuple so that we can pass it as a header
# in our packetstream obj back in server.py
def login(data: bytes) -> Tuple[bytes, str]:
    username, pw_hash, user_data = [s for s in data.decode().split('\n') if s]
    build_name, utc_offset, display_city, client_hashes, pm_private = user_data.split('|')

    if not (res := glob.db.fetch(
        'SELECT id, name, priv, pw_hash FROM users WHERE name_safe = %s',
        [Player.ensure_safe(username)]
    )): return packets.loginResponse(-1), 'no' # account does not exist

    if pw_hash != res['pw_hash']:
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

        # TODO: friends list

    return bytes(res), p.token
