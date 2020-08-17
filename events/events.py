# -*- coding: utf-8 -*-

from typing import Tuple, Callable
from time import time
from bcrypt import checkpw, hashpw, gensalt
from hashlib import md5
from cmyui.utils import rstring
from re import compile as re_compile

import packets
from packets import Packet, PacketReader # convenience

from console import *
from constants.types import osuTypes
from constants.mods import Mods
from constants import commands
from objects import glob
from objects.match import SlotStatus, Teams
from objects.player import Player, PresenceFilter, Action
from objects.beatmap import Beatmap
from constants.privileges import Privileges

glob.bancho_map = {}

def bancho_packet(ID: int) -> Callable:
    def register_callback(callback: Callable) -> Callable:
        glob.bancho_map.update({ID: callback})
        return callback
    return register_callback

# PacketID: 0
@bancho_packet(Packet.c_changeAction)
def readStatus(p: Player, pr: PacketReader) -> None:
    data = pr.read(
        osuTypes.u8, # actionType
        osuTypes.string, # infotext
        osuTypes.string, # beatmap md5
        osuTypes.u32, # mods
        osuTypes.u8, # gamemode
        osuTypes.i32 # beatmapid
    )

    p.status.update(*data) # TODO: probably refactor some status stuff
    p.rx = p.status.mods & Mods.RELAX > 0
    glob.players.enqueue(packets.userStats(p))

_np_regex = re_compile(r'^\x01ACTION is (?:editing|watching|listening to) \[https://osu.ppy.sh/b/(?P<bid>\d+) .+\]\x01$')
# PacketID: 1
@bancho_packet(Packet.c_sendPublicMessage)
def sendMessage(p: Player, pr: PacketReader) -> None:
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

    if not p.priv & t.write:
        printlog(f'{p} tried to write to {target} without privileges.')
        return

    # Limit message length to 2048 characters
    msg = f'{msg[:2045]}...' if msg[2048:] else msg
    client, client_id = p.name, p.id

    cmd = msg.startswith(glob.config.command_prefix) \
      and commands.process_commands(p, t, msg)

    if cmd: # A command was triggered.
        if cmd['public']:
            t.send(p, msg)
            if 'resp' in cmd:
                t.send(glob.bot, cmd['resp'])
        else:
            staff = {p for p in glob.players if p.priv & Privileges.Staff}
            t.send_selective(p, msg, staff - {p})
            if 'resp' in cmd:
                t.send_selective(glob.bot, cmd['resp'], {p} | staff)

    else: # No command was triggered.
        if _match := _np_regex.match(msg):
            # User is /np'ing a map.
            # Save it to their player instance
            # so we can use this elsewhere owo..
            p.last_np = Beatmap.from_bid(int(_match['bid']))

        t.send(p, msg)

    printlog(f'{p} @ {t}: {msg}', Ansi.CYAN, fd = 'logs/chat.log')

# PacketID: 2
@bancho_packet(Packet.c_logout)
def logout(p: Player, pr: PacketReader) -> None:
    pr.ignore(4) # osu client sends \x00\x00\x00\x00 every time lol

    if (time() - p.login_time) < 2:
        # osu! has a weird tendency to log out immediately when
        # it logs in, then reconnects? not sure why..?
        return

    p.logout()
    printlog(f'{p} logged out.', Ansi.LIGHT_YELLOW)

# PacketID: 3
@bancho_packet(Packet.c_requestStatusUpdate)
def statsUpdateRequest(p: Player, pr: PacketReader) -> None:
    p.enqueue(packets.userStats(p))

# PacketID: 4
@bancho_packet(Packet.c_ping)
def ping(p: Player, pr: PacketReader) -> None:
    p.ping_time = int(time())

# No specific packetID, triggered when the
# client sends a request without an osu-token.
def login(origin: bytes, ip: str) -> Tuple[bytes, str]:
    # Login is a bit special, we return the response bytes
    # and token in a tuple - we need both for our response.

    s = origin.decode().split('\n')

    if p := glob.players.get_by_name(username := s[0]):
        if (time() - p.ping_time) > 20:
            # If the current player obj online hasn't
            # pinged the server in > 20 seconds, log
            # them out and login the new user.
            p.logout()
        else: # User is currently online, send back failure.
            return packets.notification('User already logged in.') \
                 + packets.userID(-1), 'no'

    del p

    pw_hash = s[1].encode()

    s = s[2].split('|')
    build_name = s[0]

    if not s[1].replace('-', '', 1).isnumeric():
        return packets.userID(-1), 'no'

    utc_offset = int(s[1])
    display_city = s[2] == '1'

    # TODO: use these
    # 0: md5(osu path)
    # 1: adapters (network physical addresses delimited by '.')
    # 2: md5(adapters)
    # 3: md5(uniqueid) (osu! uninstall id)
    # 4: md5(uniqueid2) (disk signature/serial num)
    client_hashes = s[3].split(':')[:-1]

    pm_private = s[4] == '1'

    res = glob.db.fetch(
        'SELECT id, name, priv, pw_hash, silence_end '
        'FROM users WHERE name_safe = %s',
        [Player.ensure_safe(username)])

    if res:
        # Account exists.
        # Check their account status & credentials against db.
        if not res['priv'] & Privileges.Normal:
            return packets.userID(-3), 'no'

        # Password is incorrect.
        if pw_hash in glob.cache['bcrypt']: # ~0.01 ms
            # Cache hit - this saves ~190ms on subsequent logins.
            if glob.cache['bcrypt'][pw_hash] != res['pw_hash']:
                return packets.userID(-1), 'no'
        else: # Cache miss, must be first login.
            if not checkpw(pw_hash, res['pw_hash'].encode()):
                return packets.userID(-1), 'no'

            glob.cache['bcrypt'][pw_hash] = res['pw_hash']

        p = Player(utc_offset = utc_offset,
                   pm_private = pm_private,
                   **res)
    else:
        # Account does not exist, register using credentials passed.
        pw_bcrypt = hashpw(pw_hash, gensalt()).decode()
        glob.cache['bcrypt'][pw_hash] = pw_bcrypt

        # Add to `users` table.
        userID = glob.db.execute(
            'INSERT INTO users (name, name_safe, pw_hash, email) '
            'VALUES (%s, %s, %s, %s)', [
                username, Player.ensure_safe(username),
                pw_bcrypt, f'{rstring(6)}@gmail.com'
            ]
        )

        # Add to `stats` table.
        glob.db.execute('INSERT INTO stats (id) VALUES (%s)', [userID])

        p = Player(id = userID, name = username,
                   priv = Privileges.Normal,
                   silence_end = 0)

        printlog(f'{p} has registered!', Ansi.LIGHT_GREEN)

        p.enqueue(packets.notification('\n'.join((
            'Your account has been created.',
            '',
            'If you have any questions or find any strange server '
            'behaviour, please contact cmyui directly!',
            '',
            'Enjoy!'
        ))))

    data = bytearray(
        packets.userID(p.id) +
        packets.protocolVersion(19) +
        packets.banchoPrivileges(p.bancho_priv) +
        packets.notification(f'Welcome back to the gulag!\nCurrent build: {glob.version}') +

        # Tells osu! to load channels from config, I believe?
        packets.channelInfoEnd()
    )

    # Channels
    for c in glob.channels:
        if not p.priv & c.read:
            continue # no priv to read

        data.extend(packets.channelInfo(*c.basic_info))

        # Autojoinable channels
        if c.auto_join and p.join_channel(c):
            data.extend(packets.channelJoin(c.name))

    # Fetch some of the player's
    # information from sql to be cached.
    p.stats_from_sql_full()
    p.friends_from_sql()

    if glob.config.server_build:
        # Update their country data with
        # the IP from the login request.
        p.fetch_geoloc(ip)

    # Update our new player's stats, and broadcast them.
    user_data = packets.userPresence(p) + packets.userStats(p)

    data.extend(user_data)

    # o for online, or other
    for o in glob.players:
        # Enqueue us to them
        o.enqueue(user_data)

        # Enqueue them to us.
        data.extend(packets.userPresence(o) + packets.userStats(o))

    data.extend(packets.mainMenuIcon())
    data.extend(packets.friendsList(*p.friends))
    data.extend(packets.silenceEnd(max(p.silence_end - time(), 0)))

    glob.players.add(p)
    printlog(f'{p} logged in.', Ansi.LIGHT_YELLOW)
    return bytes(data), p.token

# PacketID: 16
@bancho_packet(Packet.c_startSpectating)
def startSpectating(p: Player, pr: PacketReader) -> None:
    target_id = pr.read(osuTypes.i32)[0]

    if not (host := glob.players.get_by_id(target_id)):
        printlog(f'{p} tried to spectate nonexistant id {target_id}.', Ansi.YELLOW)
        return

    if (c_host := p.spectating):
        c_host.remove_spectator(p)

    host.add_spectator(p)

# PacketID: 17
@bancho_packet(Packet.c_stopSpectating)
def stopSpectating(p: Player, pr: PacketReader) -> None:
    host: Player = p.spectating

    if not host:
        printlog(f"{p} tried to stop spectating when they're not..?", Ansi.LIGHT_RED)
        return

    host.remove_spectator(p)

# PacketID: 18
@bancho_packet(Packet.c_spectateFrames)
def spectateFrames(p: Player, pr: PacketReader) -> None:
    data = packets.spectateFrames(pr.data[:pr.length])
    pr.ignore_packet()
    for t in p.spectators:
        t.enqueue(data)

# PacketID: 21
@bancho_packet(Packet.c_cantSpectate)
def cantSpectate(p: Player, pr: PacketReader) -> None:
    if not p.spectating:
        printlog(f"{p} sent can't spectate while not spectating?", Ansi.LIGHT_RED)
        return

    data = packets.spectatorCantSpectate(p.id)

    host: Player = p.spectating
    host.enqueue(data)

    for t in host.spectators:
        t.enqueue(data)

# PacketID: 25
@bancho_packet(Packet.c_sendPrivateMessage)
def sendPrivateMessage(p: Player, pr: PacketReader) -> None:
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

    if t.status.action == Action.Afk and t.away_msg:
        # Send away message if target is afk and has one set.
        p.enqueue(packets.sendMessage(client, t.away_msg, target, client_id))

    if t.id == 1:
        # Target is Aika, check if message is a command.
        cmd = msg.startswith(glob.config.command_prefix) \
            and commands.process_commands(p, t, msg)

        if cmd and 'resp' in cmd:
            # Command triggered and there is a response to send.
            p.enqueue(packets.sendMessage(t.name, cmd['resp'], client, t.id))
        else: # No command triggered.
            if _match := _np_regex.match(msg):
                # User is /np'ing a map.
                # Save it to their player instance
                # so we can use this elsewhere owo..
                p.last_np = Beatmap.from_bid(int(_match['bid']))
    else: # Not Aika
        t.enqueue(packets.sendMessage(client, msg, target, client_id))

    printlog(f'{p} @ {t}: {msg}', Ansi.CYAN, fd = 'logs/chat.log')

# PacketID: 29
@bancho_packet(Packet.c_partLobby)
def lobbyPart(p: Player, pr: PacketReader) -> None:
    p.in_lobby = False

# PacketID: 30
@bancho_packet(Packet.c_joinLobby)
def lobbyJoin(p: Player, pr: PacketReader) -> None:
    p.in_lobby = True

    for m in filter(lambda m: m is not None, glob.matches):
        p.enqueue(packets.newMatch(m))

# PacketID: 31
@bancho_packet(Packet.c_createMatch)
def matchCreate(p: Player, pr: PacketReader) -> None:
    m = pr.read(osuTypes.match)[0]

    m.host = p
    p.join_match(m, m.passwd)
    printlog(f'{p} created a new multiplayer match.')

# PacketID: 32
@bancho_packet(Packet.c_joinMatch)
def matchJoin(p: Player, pr: PacketReader) -> None:
    m_id, passwd = pr.read(osuTypes.i32, osuTypes.string)
    if m_id not in range(64):
        return

    if not (m := glob.matches.get_by_id(m_id)):
        printlog(f'{p} tried to join a non-existant mp lobby?')
        return

    p.join_match(m, passwd)

# PacketID: 33
@bancho_packet(Packet.c_partMatch)
def matchPart(p: Player, pr: PacketReader) -> None:
    p.leave_match()

# PacketID: 38
@bancho_packet(Packet.c_matchChangeSlot)
def matchChangeSlot(p: Player, pr: PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried changing slot outside of a match?')
        return

    # Read new slot ID
    if (slotID := pr.read(osuTypes.i32)[0]) not in range(16):
        return

    if m.slots[slotID].status & SlotStatus.has_player:
        printlog(f'{p} tried to switch to slot {slotID} which has a player.')
        return

    # Swap with current slot.
    s = m.get_slot(p)
    m.slots[slotID].copy(s)
    s.reset()
    m.enqueue(packets.updateMatch(m))

# PacketID: 39
@bancho_packet(Packet.c_matchReady)
def matchReady(p: Player, pr: PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried readying outside of a match? (1)')
        return

    m.get_slot(p).status = SlotStatus.ready
    m.enqueue(packets.updateMatch(m))

# PacketID: 40
@bancho_packet(Packet.c_matchLock)
def matchLock(p: Player, pr: PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried locking a slot outside of a match?')
        return

    # Read new slot ID
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
@bancho_packet(Packet.c_matchChangeSettings)
def matchChangeSettings(p: Player, pr: PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried changing multi settings outside of a match?')
        return

    # Read new match data
    new = pr.read(osuTypes.match)[0]

    if new.freemods != m.freemods:
        # Freemods status has been changed.
        if new.freemods:
            # Switching to freemods.
            # Central mods -> all players mods.
            for s in m.slots:
                if s.status & SlotStatus.has_player:
                    s.mods = m.mods & ~Mods.SPEED_CHANGING

            m.mods = m.mods & Mods.SPEED_CHANGING
        else:
            # Switching to centralized mods.
            # Host mods -> Central mods.
            for s in m.slots:
                if s.player and s.player.id == m.host.id:
                    m.mods = s.mods | (m.mods & Mods.SPEED_CHANGING)
                    break

    if m.map_id == (1 << 32) - 1 and not m.map_md5:
        # Map being changed, unready players.
        for s in m.slots:
            if s.status & SlotStatus.ready:
                s.status = SlotStatus.not_ready

    # Copy basic match info into our match.
    m.map_id = new.map_id
    m.map_md5 = new.map_md5
    m.map_name = new.map_name
    m.freemods = new.freemods
    m.game_mode = new.game_mode
    m.team_type = new.team_type
    m.match_scoring = new.match_scoring
    #m.mods = new.mods
    m.name = new.name
    #m.copy(new)

    m.enqueue(packets.updateMatch(m))

# PacketID: 44
@bancho_packet(Packet.c_matchStart)
def matchStart(p: Player, pr: PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried starting match outside of a match?')
        return

    for s in m.slots:
        if s.status & SlotStatus.ready:
            s.status = SlotStatus.playing

    m.in_progress = True
    m.enqueue(packets.matchStart(m))

# PacketID: 48
@bancho_packet(Packet.c_matchScoreUpdate)
def matchScoreUpdate(p: Player, pr: PacketReader) -> None:
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
@bancho_packet(Packet.c_matchComplete)
def matchComplete(p: Player, pr: PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} sent a scoreframe outside of a match?')
        return

    m.get_slot(p).status = SlotStatus.complete

    all_completed = True

    for s in m.slots:
        if s.status & SlotStatus.playing:
            all_completed = False
            break

    if all_completed:
        m.in_progress = False
        m.enqueue(packets.matchComplete())

        for s in m.slots: # Reset match statuses
            if s.status == SlotStatus.complete:
                s.status = SlotStatus.not_ready

# PacketID: 51
@bancho_packet(Packet.c_matchChangeMods)
def matchChangeMods(p: Player, pr: PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried changing multi mods outside of a match?')
        return

    mods = pr.read(osuTypes.i32)[0]

    if m.freemods:
        if p.id == m.host.id:
            # Allow host to change speed-changing mods.
            m.mods = mods & Mods.SPEED_CHANGING

        # Set slot mods
        m.get_slot(p).mods = mods & ~Mods.SPEED_CHANGING
    else:
        # Not freemods, set match mods.
        m.mods = mods

    m.enqueue(packets.updateMatch(m))

# PacketID: 52
@bancho_packet(Packet.c_matchLoadComplete)
def matchLoadComplete(p: Player, pr: PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} sent a scoreframe outside of a match?')
        return

    # Ready up our player.
    m.get_slot(p).loaded = True

    # Check if all players are ready.
    if not any(s.status & SlotStatus.playing and not s.loaded for s in m.slots):
        m.enqueue(packets.matchAllPlayerLoaded(), lobby = False)

# PacketID: 54
@bancho_packet(Packet.c_matchNoBeatmap)
def matchNoBeatmap(p: Player, pr: PacketReader) -> None:
    if not (m := p.match):
        return

    m.get_slot(p).status = SlotStatus.no_map
    m.enqueue(packets.updateMatch(m))

# PacketID: 55
@bancho_packet(Packet.c_matchNotReady)
def matchNotReady(p: Player, pr: PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried unreadying outside of a match? (1)')
        return

    m.get_slot(p).status = SlotStatus.not_ready
    m.enqueue(packets.updateMatch(m), lobby = False)

# PacketID: 56
@bancho_packet(Packet.c_matchFailed)
def matchFailed(p: Player, pr: PacketReader) -> None:
    if not (m := p.match):
        return

    m.enqueue(packets.matchPlayerFailed(m.get_slot_id(p)))

# PacketID: 59
@bancho_packet(Packet.c_matchHasBeatmap)
def matchHasBeatmap(p: Player, pr: PacketReader) -> None:
    if not (m := p.match):
        return

    m.get_slot(p).status = SlotStatus.not_ready
    m.enqueue(packets.updateMatch(m))

# PacketID: 60
@bancho_packet(Packet.c_matchSkipRequest)
def matchSkipRequest(p: Player, pr: PacketReader) -> None:
    if not (m := p.match):
        printlog(f'{p} tried unreadying outside of a match? (1)')
        return

    m.get_slot(p).skipped = True
    m.enqueue(packets.matchPlayerSkipped(p.id))

    for s in m.slots:
        if s.status & SlotStatus.playing and not s.skipped:
            return

    # All users have skipped, enqueue a skip.
    m.enqueue(packets.matchSkip(), lobby = False)

# PacketID: 63
@bancho_packet(Packet.c_channelJoin)
def channelJoin(p: Player, pr: PacketReader) -> None:
    chan_name = pr.read(osuTypes.string)[0]
    c = glob.channels.get(chan_name)

    if not c or not p.join_channel(c):
        printlog(f'{p} failed to join {chan_name}.', Ansi.YELLOW)
        return

    p.enqueue(packets.channelJoin(c.name))

# PacketID: 70
@bancho_packet(Packet.c_matchTransferHost)
def matchTransferHost(p: Player, pr: PacketReader) -> None:
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
@bancho_packet(Packet.c_friendAdd)
def friendAdd(p: Player, pr: PacketReader) -> None:
    userID = pr.read(osuTypes.i32)[0]

    if not (t := glob.players.get_by_id(userID)):
        printlog(f'{t} tried to add a user who is not online! ({userID})')
        return

    if t.id in (1, p.id):
        # Trying to add the bot, or themselves.
        # These are already appended to the friends list
        # on login, so disallow the user from *actually*
        # editing these in the DB.
        return

    p.add_friend(t)

# PacketID: 74
@bancho_packet(Packet.c_friendRemove)
def friendRemove(p: Player, pr: PacketReader) -> None:
    userID = pr.read(osuTypes.i32)[0]

    if not (t := glob.players.get_by_id(userID)):
        printlog(f'{t} tried to remove a user who is not online! ({userID})')
        return

    if t.id in (1, p.id):
        # Trying to remove the bot, or themselves.
        # These are already appended to the friends list
        # on login, so disallow the user from *actually*
        # editing these in the DB.
        return

    p.remove_friend(t)

# PacketID: 77
@bancho_packet(Packet.c_matchChangeTeam)
def matchChangeTeam(p: Player, pr: PacketReader) -> None:
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
@bancho_packet(Packet.c_channelPart)
def channelPart(p: Player, pr: PacketReader) -> None:
    if not (chan := pr.read(osuTypes.string)[0]):
        return

    if (c := glob.channels.get(chan)):
        p.leave_channel(c)
    else:
        printlog(f'Failed to find channel {chan} that {p} attempted to leave.')

# PacketID: 79
@bancho_packet(Packet.c_ReceiveUpdates)
def receiveUpdates(p: Player, pr: PacketReader) -> None:
    if (f := pr.read(osuTypes.i32)[0]) not in range(3):
        printlog(f'{p} tried to set his presence filter to {f}?')
        return

    p.pres_filter = PresenceFilter(f)

# PacketID: 82
@bancho_packet(Packet.c_setAwayMessage)
def setAwayMessage(p: Player, pr: PacketReader) -> None:
    pr.ignore(3) # why does first string send \x0b\x00?
    p.away_msg = pr.read(osuTypes.string)[0]
    pr.ignore(4)

# PacketID: 85
@bancho_packet(Packet.c_userStatsRequest)
def statsRequest(p: Player, pr: PacketReader) -> None:
    if len(pr.data) < 6:
        return

    userIDs = pr.read(osuTypes.i32_list)
    is_online = lambda o: o in glob.players.ids and o != p.id

    for online in filter(is_online, userIDs):
        target = glob.players.get_by_id(online)
        p.enqueue(packets.userStats(target))

# PacketID: 87
@bancho_packet(Packet.c_matchInvite)
def matchInvite(p: Player, pr: PacketReader) -> None:
    if not p.match:
        printlog(f"{p} tried to invite someone to a match but isn't in one!")
        pr.ignore(4)
        return

    userID = pr.read(osuTypes.i32)[0]
    if not (t := glob.players.get_by_id(userID)):
        printlog(f'{t} tried to invite a user who is not online! ({userID})')
        return

    inv = f'Come join my game: {p.match.embed}.'
    t.enqueue(packets.sendMessage(p.name, inv, t.name, p.id))
    printlog(f'{p} invited {t} to their match.')

# PacketID: 97
@bancho_packet(Packet.c_userPresenceRequest)
def userPresenceRequest(p: Player, pr: PacketReader) -> None:
    for id in pr.read(osuTypes.i32_list):
        p.enqueue(packets.userPresence(id))

# PacketID: 99
@bancho_packet(Packet.c_userToggleBlockNonFriendPM)
def toggleBlockingDMs(p: Player, pr: PacketReader) -> None:
    p.pm_private = pr.read(osuTypes.i32)[0] == 1
