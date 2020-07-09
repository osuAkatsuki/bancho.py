# -*- coding: utf-8 -*-

from typing import Tuple
from time import time
from datetime import datetime as dt, timezone as tz
from bcrypt import checkpw

import packets
from console import *
from constants.types import osuTypes
from constants.mods import Mods
from constants import commands
from objects import glob
from objects.match import SlotStatus, Teams
from objects.player import Player
from objects.channel import Channel
from constants.privileges import Privileges

# PacketID: 0
def readStatus(p: Player, pr: packets.PacketReader) -> None:
    data = pr.read(
        osuTypes.i8, # actionType
        osuTypes.string, # infotext
        osuTypes.string, # beatmap md5
        osuTypes.i32, # mods
        osuTypes.i8, # gamemode
        osuTypes.i32 # beatmapid
    )

    p.status.update(*data) # TODO: probably refactor some status stuff
    p.rx = p.status.mods & Mods.RELAX > 0
    glob.players.enqueue(packets.userStats(p))

# PacketID: 1
def sendMessage(p: Player, pr: packets.PacketReader) -> None:
    if p.silenced:
        printlog(f'{p} tried to send a message while silenced.', Ansi.YELLOW)
        return

    # client_id only proto >= 14
    client, msg, target, client_id = pr.read(osuTypes.message)

    # no nice wrapper to do it in reverse :P
    if target == '#spectator':
        target = f'#spec_{p.spectating.id if p.spectating else p.id}'
    elif target == '#multiplayer':
        target = f'#multi_{p.match.id if p.match is not None else 0}'

    if not (t := glob.channels.get(target)):
        printlog(f'{p} tried to write to non-existant {target}.', Ansi.YELLOW)
        return

    # Limit message length to 2048 characters
    msg = f'{msg[:2045]}...' if msg[2048:] else msg
    client, client_id = p.name, p.id

    cmd = msg.startswith(glob.config.command_prefix) \
        and commands.process_commands(p, t, msg)

    if cmd and cmd['resp']:
        if cmd['public']:
            # Send our message & response to all in the channel.
            t.send(p, msg)
            t.send(glob.bot, cmd['resp'])
        else: # Send response to only player and staff.
            staff = {p for p in glob.players if p.priv & Privileges.Mod}
            t.send_selective(p, msg, staff - {p})
            t.send_selective(glob.bot, cmd['resp'], {p} | staff)
    else: # No command.
        t.send(p, msg)

    printlog(f'{p} @ {t}: {msg}', Ansi.CYAN, fd = 'logs/chat.log')

# PacketID: 2
def logout(p: Player, pr: packets.PacketReader) -> None:
    pr.ignore(4) # osu client sends \x00\x00\x00\x00 every time lol

    if (time() - p.login_time) < 1:
        # osu! has a weird tendency to log out immediately when
        # it logs in, then reconnects? not sure why..?
        return

    glob.players.remove(p)

    glob.players.enqueue(packets.logout(p.id))

    for c in p.channels:
        p.leave_channel(c)

    # stop spectating
    if (host := p.spectating):
        host.remove_spectator(p)

    # leave match
    # remove match if only player

    printlog(f'{p} logged out.', Ansi.LIGHT_YELLOW)

# PacketID: 3
def statsUpdateRequest(p: Player, pr: packets.PacketReader) -> None:
    p.enqueue(packets.userStats(p))

# PacketID: 4
def ping(p: Player, pr: packets.PacketReader) -> None:
    p.ping_time = int(time())

# PacketID: 5
def login(origin: bytes) -> Tuple[bytes, str]:
    # Login is a bit special, we return the response bytes
    # and token in a tuple so that we can pass it as a header
    # in our packetstream obj back in server.py

    split = [s for s in origin.decode().split('\n') if s]
    username = split[0]
    pw_hash = split[1].encode()

    split = split[2].split('|')
    build_name = split[0]

    if not split[1].replace('-', '', 1).isnumeric():
        return packets.userID(-1), 'no'

    utc_offset = int(split[1])
    display_city = split[2] == '1'

    client_hashes = split[3].split(':')
    # TODO: client hashes

    pm_private = split[4] == '1'

    res = glob.db.fetch(
        'SELECT id, name, priv, pw_hash, silence_end '
        'FROM users WHERE name_safe = %s',
        [Player.ensure_safe(username)])

    if not res: # Account does not exist.
        return packets.userID(-1), 'no'

    # Account is banned.
    if res['priv'] == Privileges.Banned:
        return packets.userID(-3), 'no'

    # Password is incorrect.
    if pw_hash in glob.bcrypt_cache: # ~0.01 ms
        # Cache hit - this saves ~190ms on subsequent logins.
        if glob.bcrypt_cache[pw_hash] != res['pw_hash']:
            return packets.userID(-1), 'no'
    else: # Cache miss, must be first login.
        if not checkpw(pw_hash, res['pw_hash'].encode()):
            return packets.userID(-1), 'no'

        glob.bcrypt_cache.update({pw_hash: res['pw_hash']})

    p = Player(utc_offset = utc_offset, pm_private = pm_private, **res)
    p.silence_end = res['silence_end']
    glob.players.add(p)

    # No need to use packetstream here,
    # we're only dealing with body w/o headers.
    data = packets.BinaryArray()
    data += packets.userID(p.id)
    data += packets.protocolVersion(19)
    data += packets.banchoPrivileges(p.bancho_priv)
    data += packets.notification(f'Welcome back to the gulag (v{glob.version:.2f})')

    # Channels
    data += packets.channelInfoEnd() # tells osu client to load channels from config i think?
    for c in glob.channels:
        if not p.priv & c.read:
            continue # no priv to read

        data += packets.channelInfo(*c.basic_info)

        # Autojoinable channels
        if c.auto_join and p.join_channel(c):
            data += packets.channelJoin(c.name)

    # Fetch some of the player's
    # information from sql to be cached.
    # (stats, friends, etc.)
    p.query_info()

    # Update our new player's stats, and broadcast them.
    our_presence = packets.userPresence(p)
    our_stats = packets.userStats(p)

    data += our_presence + our_stats

    # o for online, or other
    for o in glob.players:
        # TODO: variadic params for enqueue

        # Enqueue us to them
        o.enqueue(our_presence + our_stats)

        # Enqueue them to us
        p.enqueue(packets.userPresence(o) + packets.userStats(o))

    data += packets.mainMenuIcon()
    data += packets.friendsList(*p.friends)
    data += packets.silenceEnd(max(p.silence_end - time(), 0))

    printlog(f'{p} logged in.', Ansi.LIGHT_YELLOW)
    return bytes(data), p.token

# PacketID: 15
def spectateFrames(p: Player, pr: packets.PacketReader) -> None:
    data = packets.spectateFrames(pr.data[:pr.length])
    pr.ignore_packet()
    for t in p.spectators:
        t.enqueue(data)

# PacketID: 16
def startSpectating(p: Player, pr: packets.PacketReader) -> None:
    target_id = pr.read(osuTypes.i32)[0]

    if not (host := glob.players.get_by_id(target_id)):
        printlog(f'{p} tried to spectate nonexistant id {target_id}.', Ansi.YELLOW)
        return

    if (c_host := p.spectating):
        c_host.remove_spectator(p)

    host.add_spectator(p)

# PacketID: 17
def stopSpectating(p: Player, pr: packets.PacketReader) -> None:
    if not p.spectating:
        printlog(f"{p} Tried to stop spectating when they're not..?", Ansi.LIGHT_RED)
        return

    host: Player = p.spectating
    host.remove_spectator(p)

# PacketID: 21
def cantSpectate(p: Player, pr: packets.PacketReader) -> None:
    if not p.spectating:
        printlog(f"{p} Sent can't spectate while not spectating?", Ansi.LIGHT_RED)
        return

    data = packets.spectatorCantSpectate(p.id)

    host: Player = p.spectating
    host.enqueue(data)

    for t in host.spectators:
        t.enqueue(data)

# PacketID: 25
def sendPrivateMessage(p: Player, pr: packets.PacketReader) -> None:
    if p.silenced:
        printlog(f'{p} tried to send a dm while silenced.', Ansi.YELLOW)
        return

    client, msg, target, client_id = pr.read(osuTypes.message)

    if not (t := glob.players.get_by_name(target)):
        printlog(f'{p} tried to write to non-existant user {target}.', Ansi.YELLOW)
        return

    if t.pm_private and p.id not in t.friends:
        p.enqueue(packets.userPMBlocked(target))
        printlog(f'{p} tried to message {t}, but they are blocking dms.')
        return

    if t.silenced:
        p.enqueue(packets.targetSilenced(target))
        printlog(f'{p} tried to message {t}, but they are silenced.')
        return

    msg = msg[:2045] + '...' if msg[2048:] else msg
    client, client_id = p.name, p.id

    if t.id == 1:
        # Target is Aika, check if message is a command.
        cmd = msg.startswith(glob.config.command_prefix) \
            and commands.process_commands(p, t, msg)

        if cmd and 'resp' in cmd:
            # Command triggered and there is a response to send.
            p.enqueue(packets.sendMessage(t.name, cmd['resp'], client, t.id))
    else: # Not Aika
        t.enqueue(packets.sendMessage(client, msg, target, client_id))

    printlog(f'{p} @ {t}: {msg}', Ansi.CYAN, fd = 'logs/chat.log')

# PacketID: 29
def lobbyPart(p: Player, pr: packets.PacketReader) -> None:
    p.in_lobby = False

# PacketID: 30
def lobbyJoin(p: Player, pr: packets.PacketReader) -> None:
    p.in_lobby = True

    for m in glob.matches:
        if m:
            p.enqueue(packets.newMatch(m))

# PacketID: 31
def matchCreate(p: Player, pr: packets.PacketReader) -> None:
    m = pr.read(osuTypes.match)[0]

    m.host = p
    p.join_match(m, m.passwd)
    printlog(f'{p} created a new multiplayer match.')

# PacketID: 32
def matchJoin(p: Player, pr: packets.PacketReader) -> None:
    id, passwd = pr.read(osuTypes.i32, osuTypes.string)
    if id not in range(64):
        return

    if not (m := glob.matches.get_by_id(id)):
        printlog(f'{p} tried to join a non-existant mp lobby?')
        return

    p.join_match(m, passwd)

# PacketID: 33
def matchPart(p: Player, pr: packets.PacketReader) -> None:
    p.leave_match()

# PacketID: 38
def matchChangeSlot(p: Player, pr: packets.PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried changing slot outside of a match?')
        return

    # Ready new slot ID
    if (slotID := pr.read(osuTypes.i32)[0]) not in range(16):
        return

    if m.slots[slotID].status & SlotStatus.has_player:
        printlog(f'{p} tried to switch to slot {slotID} which has a player.')
        return

    for s in m.slots:
        if p == s.player:
            # Swap current slot with
            m.slots[slotID].copy(s)
            s.reset()
            break
    else:
        printlog(f"Failed to find {p}'s current slot?")
        return

    m.enqueue(packets.updateMatch(m))

# PacketID: 39
def matchReady(p: Player, pr: packets.PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried readying outside of a match? (1)')
        return

    for s in m.slots:
        if p == s.player:
            s.status = SlotStatus.ready
            break
    else:
        printlog(f'{p} tried readying outside of a match? (2)')
        return

    m.enqueue(packets.updateMatch(m))

# PacketID: 40
def matchLock(p: Player, pr: packets.PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried locking a slot outside of a match?')
        return

    # Ready new slot ID
    if (slotID := pr.read(osuTypes.i32)[0]) not in range(16):
        return

    slot = m.slots[slotID]

    if slot.status & SlotStatus.locked:
        slot.status = SlotStatus.open
    else:
        if slot.player:
            slot.reset()
        slot.status = SlotStatus.locked

    m.enqueue(packets.updateMatch(m))

# PacketID: 41
def matchChangeSettings(p: Player, pr: packets.PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried changing multi settings outside of a match?')
        return

    # Read new match data
    new = pr.read(osuTypes.match)[0]

    # Copy our new match data into our current match.
    m.copy(new)

    m.enqueue(packets.updateMatch(m))

# PacketID: 44
def matchStart(p: Player, pr: packets.PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried starting match outside of a match?')
        return

    for s in m.slots:
        if s.status & SlotStatus.ready:
            s.status = SlotStatus.playing

    m.in_progress = True
    m.enqueue(packets.matchStart(m))

# PacketID: 48
def matchScoreUpdate(p: Player, pr: packets.PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} sent a scoreframe outside of a match?')
        return

    # Read 37 bytes if using scorev2,
    # otherwise only read 29 bytes.
    size = 37 if pr.data[28] else 29
    data = pr.data[:size]
    data[4] = m.get_slot_id(p)

    m.enqueue(b'0\x00\x00' + size.to_bytes(4, 'little') + data, lobby = False)
    pr.ignore(size)

# PacketID: 49
def matchComplete(p: Player, pr: packets.PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} sent a scoreframe outside of a match?')
        return

    for s in m.slots:
        if p == s.player:
            s.status = SlotStatus.complete
            break

    all_completed = True

    for s in m.slots:
        if s.status.playing:
            all_completed = False
            break

    if all_completed:
        m.in_progress = False
        m.enqueue(packets.matchComplete())

        for s in m.slots: # Reset match statuses
            if s.status == SlotStatus.complete:
                s.status = SlotStatus.not_ready

# PacketID: 51
def matchChangeMods(p: Player, pr: packets.PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried changing multi mods outside of a match?')
        return

    mods = pr.read(osuTypes.i32)[0]
    m.mods = mods # cursed?

    m.enqueue(packets.updateMatch(m))

# PacketID: 52
def matchLoadComplete(p: Player, pr: packets.PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} sent a scoreframe outside of a match?')
        return

    # Ready up our player.
    for s in m.slots:
        if p == s.player:
            s.loaded = True
            break

    # Check if all players are ready.
    if not any(s.status & SlotStatus.playing and not s.loaded for s in m.slots):
        m.enqueue(packets.matchAllPlayerLoaded(), lobby = False)

# PacketID: 55
def matchNotReady(p: Player, pr: packets.PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried unreadying outside of a match? (1)')
        return

    for s in m.slots:
        if p == s.player:
            s.status = SlotStatus.not_ready
            break
    else:
        printlog(f'{p} tried unreadying outside of a match? (2)')
        return

    m.enqueue(packets.updateMatch(m), lobby = False)

# PacketID: 60
def matchSkipRequest(p: Player, pr: packets.PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried unreadying outside of a match? (1)')
        return

    for s in m.slots:
        if p == s.player:
            s.skipped = True
            m.enqueue(packets.matchPlayerSkipped(p.id))
            break

    for s in m.slots:
        if s.status & SlotStatus.playing and not s.skipped:
            return

    # All users have skipped, enqueue a skip.
    m.enqueue(packets.matchSkip(), lobby = False)

# PacketID: 63
def channelJoin(p: Player, pr: packets.PacketReader) -> None:
    if not (chan := pr.read(osuTypes.string)[0]):
        printlog(f'{p} tried to join nonexistant channel {chan}. (1)')
        return

    if (c := glob.channels.get(chan)) and p.join_channel(c):
        p.enqueue(packets.channelJoin(chan))
    else:
        printlog(f'{p} tried to join nonexistant channel {chan}. (2)')

# PacketID: 70
def matchTransferHost(p: Player, pr: packets.PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried transferring host of a match? (1)')
        return

    if (slotID := pr.read(osuTypes.i32)[0]) not in range(16):
        return

    if not (t := m[slotID].player):
        printlog(f'{p} tried to transfer host to an empty slot?')
        return

    m.host = t
    m.host.enqueue(packets.matchTransferHost())
    m.enqueue(packets.updateMatch(m), lobby = False)

# PacketID: 73
def friendAdd(p: Player, pr: packets.PacketReader) -> None:
    userID = pr.read(osuTypes.i32)[0]

    if not (t := glob.players.get_by_id(userID)):
        printlog(f'{t} tried to add a user who is not online! ({userID})')
        return

    p.add_friend(t)

# PacketID: 74
def friendRemove(p: Player, pr: packets.PacketReader) -> None:
    userID = pr.read(osuTypes.i32)[0]

    if not (t := glob.players.get_by_id(userID)):
        printlog(f'{t} tried to remove a user who is not online! ({userID})')
        return

    p.remove_friend(t)

# PacketID: 77
def matchChangeTeam(p: Player, pr: packets.PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried changing team outside of a match? (1)')
        return

    for s in m.slots:
        if p == s.player:
            s.team = Teams.blue if s.team != Teams.blue else Teams.red
            break
    else:
        printlog(f'{p} tried changing team outside of a match? (2)')
        return

    m.enqueue(packets.updateMatch(m), lobby = False)

# PacketID: 78
def channelPart(p: Player, pr: packets.PacketReader) -> None:
    if not (chan := pr.read(osuTypes.string)[0]):
        return

    if (c := glob.channels.get(chan)):
        p.leave_channel(c)
    else:
        printlog(f'Failed to find channel {chan} that {p} attempted to leave.')

# PacketID: 85
def statsRequest(p: Player, pr: packets.PacketReader) -> None:
    if len(pr.data) < 6:
        return

    userIDs = pr.read(osuTypes.i32_list)
    is_online = lambda o: o in glob.players.ids

    for online in filter(is_online, userIDs):
        target = glob.players.get_by_id(online)
        p.enqueue(packets.userStats(target))

# PacketID: 87
def matchInvite(p: Player, pr: packets.PacketReader) -> None:
    pass

# PacketID: 97
def userPresenceRequest(p: Player, pr: packets.PacketReader) -> None:
    for id in pr.read(osuTypes.i32_list):
        p.enqueue(packets.userPresence(id))

# PacketID: 99
def toggleBlockingDMs(p: Player, pr: packets.PacketReader) -> None:
    p.pm_private = pr.read(osuTypes.i32)[0] == 1

# PacketID: 100
def setAwayMessage(p: Player, pr: packets.PacketReader) -> None:
    pr.ignore(3) # why does first string send \x0b\x00?
    p.away_message = pr.read(osuTypes.string)[0]
    pr.ignore(4)
