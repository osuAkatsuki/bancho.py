# -*- coding: utf-8 -*-

from typing import Callable
from datetime import datetime as dt, timedelta as td
import time
from cmyui import log, Ansi, _isdecimal
import bcrypt

import packets
from packets import ClientPacketType, ClientPacket # convenience

from constants.types import osuTypes
from constants.mods import Mods
from constants import commands
from constants import regexes
from objects import glob
from objects.match import MatchTeamTypes, SlotStatus, Teams
from objects.player import Player, PresenceFilter, Action
from objects.beatmap import Beatmap
from constants.privileges import Privileges

glob.bancho_map = {}

def bancho_packet(packet: ClientPacketType) -> Callable:
    def register_callback(callback: Callable) -> Callable:
        glob.bancho_map |= {packet: callback}
        return callback
    return register_callback

def register(cls: ClientPacket):
    # Append the handler to our map.
    glob.bancho_map |= {cls.type: cls}
    return cls

@register
class ChangeAction(ClientPacket, type=ClientPacketType.CHANGE_ACTION):
    action: osuTypes.u8
    info_text: osuTypes.string
    map_md5: osuTypes.string
    mods: osuTypes.u32
    mode: osuTypes.u8
    map_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        # update the user's status.
        p.status.update(
            self.action, self.info_text,
            self.map_md5, self.mods,
            self.mode, self.map_id
        )

        # broadcast it to all online players.
        glob.players.enqueue(packets.userStats(p))

@register
class SendMessage(ClientPacket, type=ClientPacketType.SEND_PUBLIC_MESSAGE):
    msg: osuTypes.message

    async def handle(self, p: Player) -> None:
        if p.silenced:
            log(f'{p} sent a message while silenced.', Ansi.YELLOW)
            return

        msg = self.msg.msg
        target = self.msg.target

        if target == '#spectator':
            if p.spectating:
                # we are spectating someone
                spec_id = p.spectating.id
            elif p.spectators:
                # we are being spectated
                spec_id = p.id
            else:
                return

            t = glob.channels[f'#spec_{spec_id}']
        elif target == '#multiplayer':
            if not p.match:
                # they're not in a match?
                return

            t = glob.channels[f'#multi_{p.match.id}']
        else:
            t = glob.channels[target]

        if not t:
            log(f'{p} wrote to non-existent {target}.', Ansi.YELLOW)
            return

        if not p.priv & t.write:
            log(f'{p} wrote to {target} with insufficient privileges.')
            return

        # limit message length to 2048 characters
        msg = f'{msg[:2045]}...' if msg[2048:] else msg

        cmd = msg.startswith(glob.config.command_prefix) \
        and await commands.process_commands(p, t, msg)

        if cmd:
            # a command was triggered.
            if cmd['public']:
                await t.send(p, msg)
                if 'resp' in cmd:
                    await t.send(glob.bot, cmd['resp'])
            else:
                staff = glob.players.staff
                await t.send_selective(p, msg, staff - {p})
                if 'resp' in cmd:
                    await t.send_selective(glob.bot, cmd['resp'], staff | {p})

        else:
            # no commands were triggered

            # check if the user is /np'ing a map.
            # even though this is a public channel,
            # we'll update the player's last np stored.
            if _match := regexes.now_playing.match(msg):
                # the player is /np'ing a map.
                # save it to their player instance
                # so we can use this elsewhere owo..
                p.last_np = await Beatmap.from_bid(int(_match['bid']))

            await t.send(p, msg)

        log(f'{p} @ {t}: {msg}', Ansi.CYAN, fd='.data/logs/chat.log')

@register
class Logout(ClientPacket, type=ClientPacketType.LOGOUT):
    _: osuTypes.i32 # pretty awesome design on osu!'s end :P

    async def handle(self, p: Player) -> None:
        if (time.time() - p.login_time) < 2:
            # osu! has a weird tendency to log out immediately when
            # it logs in, then reconnects? not sure why..?
            return

        await p.logout()
        log(f'{p} logged out.', Ansi.LYELLOW)

@register
class StatsUpdateRequest(ClientPacket, type=ClientPacketType.REQUEST_STATUS_UPDATE):
    async def handle(self, p: Player) -> None:
        p.enqueue(packets.userStats(p))

registration_msg = '\n'.join((
    "Hey! Welcome to [https://github.com/cmyui/gulag/ the gulag].",
    "",
    "Command help: !help",
    "If you have any questions or find any strange behaviour,",
    "please feel feel free to contact cmyui(#0425) directly!"
))
# no specific packet id, triggered when the
# client sends a request without an osu-token.
async def login(origin: bytes, ip: str) -> tuple[bytes, str]:
    # login is a bit special, we return the response bytes
    # and token in a tuple - we need both for our response.
    if len(s := origin.decode().split('\n')[:-1]) != 3:
        return

    if p := await glob.players.get_by_name(username := s[0]):
        if (time.time() - p.last_recv_time) > 10:
            # if the current player obj online hasn't
            # pinged the server in > 10 seconds, log
            # them out and login the new user.
            await p.logout()
        else:
            # the user is currently online, send back failure.
            data = packets.userID(-1) + \
                   packets.notification('User already logged in.')

            return data, 'no'

    del p

    pw_hash = s[1].encode()

    if len(s := s[2].split('|')) != 5:
        return

    if not (r := regexes.osu_ver.match(s[0])):
        # invalid client version?
        return packets.userID(-2), 'no'

    # parse their osu version into a datetime object.
    # this will be saved to `p.osu_ver` if login succeeds.
    osu_ver = dt.strptime(r['ver'], '%Y%m%d')

    if osu_ver < dt.now() - td(60):
        # the osu! client is older than 2 months old,
        # disallow login and force an update re-check.
        return (packets.versionUpdateForced() +
                packets.userID(-2)), 'no'

    if not _isdecimal(s[1], _negative=True):
        # utc-offset isn't a number (negative inclusive).
        return packets.userID(-1), 'no'

    utc_offset = int(s[1])
    display_city = s[2] == '1'

    # Client hashes contain a few values useful to us.
    # [0]: md5(osu path)
    # [1]: adapters (network physical addresses delimited by '.')
    # [2]: md5(adapters)
    # [3]: md5(uniqueid) (osu! uninstall id)
    # [4]: md5(uniqueid2) (disk signature/serial num)
    client_hashes = s[3].split(':')[:-1]
    client_hashes.pop(1) # no need for non-md5 adapters

    pm_private = s[4] == '1'

    p_row = await glob.db.fetch(
        'SELECT id, name, priv, pw_hash, silence_end '
        'FROM users WHERE name_safe = %s',
        [Player.make_safe(username)]
    )

    if not p_row:
        # no account by this name exists.
        return packets.userID(-1), 'no'

    # get our bcrypt cache.
    bcrypt_cache = glob.cache['bcrypt']

    # their account exists in sql.
    # check their account status & credentials against db.

    if pw_hash in bcrypt_cache: # ~0.01 ms
        # cache hit - this saves ~200ms on subsequent logins.
        if bcrypt_cache[pw_hash] != p_row['pw_hash']:
            # password wrong
            return packets.userID(-1), 'no'

    else:
        # cache miss, their first login since the server started.
        if not bcrypt.checkpw(pw_hash, p_row['pw_hash'].encode()):
            return packets.userID(-1), 'no'

        bcrypt_cache[pw_hash] = p_row['pw_hash']

    if not p_row['priv'] & Privileges.Normal:
        return packets.userID(-3), 'no'

    """ handle client hashes """

    # insert new set/occurrence
    await glob.db.execute(
        'INSERT INTO client_hashes '
        'VALUES (%s, %s, %s, %s, %s, NOW(), 0) '
        'ON DUPLICATE KEY UPDATE '
        'occurrences = occurrences + 1, '
        'latest_time = NOW() ',
        [p_row['id'], *client_hashes]
    )

    # TODO: runningunderwine support

    # find any other users from any of the same hwid values.
    hwid_matches = await glob.db.fetchall(
        'SELECT u.`name`, u.`priv`, h.`occurrences` '
        'FROM `client_hashes` h '
        'LEFT JOIN `users` u ON h.`userid` = u.`id` '
        'WHERE h.`userid` != %s AND (h.`adapters` = %s '
        'OR h.`uninstall_id` = %s OR h.`disk_serial` = %s)',
        [p_row['id'], *client_hashes[1:]]
    )

    if hwid_matches:
        # we have other accounts with matching hashes

        # NOTE: this is an area i've seen a lot of implementations rush
        # through and poorly design; this section is CRITICAL for both
        # keeping multiaccounting down, but perhaps more importantly in
        # scenarios where multiple users are forced to use a single pc
        # (lan meetups, at a friends place, shared computer, etc.).
        # these scenarios are usually the ones where new players will
        # get invited to your server.. first impressions are important
        # and you don't want a ban and support ticket to be this users
        # first experience. :P

        # anyways yeah needless to say i'm gonna think about this one

        if not p_row['priv'] & Privileges.Verified:
            # this player is not verified yet, this is their first
            # time connecting in-game and submitting their hwid set.
            # we will not allow any banned matches; if there are any,
            # then ask the user to contact staff and resolve manually.
            if not all(x['priv'] & Privileges.Normal for x in hwid_matches):
                return (packets.notification('Please contact staff directly '
                                                   'to create an account.') +
                        packets.userID(-1)), 'no'

        else:
            # player is verified
            # TODO: add discord webhooks to cmyui_pkg, it would be a
            # perfect addition here.. will have to think about how
            # to organize it in config tho :o
            pass

    if not p_row['priv'] & Privileges.Verified:
        # verify the account if it's made it this far
        p_row['priv'] |= int(Privileges.Verified)

        await glob.db.execute(
            'UPDATE users SET priv = priv | %s WHERE id = %s',
            [p_row['priv'], p_row['id']]
        )

    p_row |= {
        'utc_offset': utc_offset,
        'pm_private': pm_private,
        'osu_ver': osu_ver
    }

    p = Player(**p_row)

    data = bytearray(
        packets.userID(p.id) +
        packets.protocolVersion(19) +
        packets.banchoPrivileges(p.bancho_priv) +
        packets.notification('Welcome back to the gulag!\n'
                                   f'Current build: {glob.version}') +

        # tells osu! to load channels from config, i believe?
        packets.channelInfoEnd()
    )

    # channels
    for c in glob.channels:
        if not p.priv & c.read:
            continue # no priv to read

        # autojoinable channels
        if c.auto_join and await p.join_channel(c):
            # NOTE: p.join_channel enqueues channelJoin, but
            # if we don't send this back in this specific request,
            # the client will attempt to join the channel again.
            data.extend(packets.channelJoin(c.name))

        data.extend(packets.channelInfo(*c.basic_info))

    # fetch some of the player's
    # information from sql to be cached.
    await p.stats_from_sql_full()
    await p.friends_from_sql()

    if glob.config.server_build:
        # update their country data with
        # the IP from the login request.
        await p.fetch_geoloc(ip)

    # update our new player's stats, and broadcast them.
    user_data = (
        packets.userPresence(p) +
        packets.userStats(p)
    )

    data.extend(user_data)

    # o for online, or other
    for o in glob.players:
        # enqueue us to them
        o.enqueue(user_data)

        # enqueue them to us.
        data.extend(
            packets.userPresence(o) +
            packets.userStats(o)
        )

    data.extend(
        packets.mainMenuIcon() +
        packets.friendsList(*p.friends) +
        packets.silenceEnd(p.remaining_silence)
    )

    # thank u osu for doing this by username rather than id
    query = ('SELECT m.`msg`, m.`time`, m.`from_id`, '
             '(SELECT name FROM users WHERE id = m.`from_id`) AS `from`, '
             '(SELECT name FROM users WHERE id = m.`to_id`) AS `to` '
             'FROM `mail` m WHERE m.`to_id` = %s AND m.`read` = 0')

    # the player may have been sent mail while offline,
    # enqueue any messages from their respective authors.
    async for msg in glob.db.iterall(query, p.id):
        msg_time = dt.fromtimestamp(msg['time'])
        msg_ts = f'[{msg_time:%Y-%m-%d %H:%M:%S}] {msg["msg"]}'

        data.extend(packets.sendMessage(
            msg['from'], msg_ts,
            msg['to'], msg['from_id']
        ))

    # add `p` to the global player list,
    # making them officially logged in.
    glob.players.add(p)

    log(f'{p} logged in.', Ansi.LCYAN)
    return bytes(data), p.token

@register
class StartSpectating(ClientPacket, type=ClientPacketType.START_SPECTATING):
    target_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (host := await glob.players.get_by_id(self.target_id)):
            log(f'{p} tried to spectate nonexistant id {self.target_id}.', Ansi.YELLOW)
            return

        if c_host := p.spectating:
            await c_host.remove_spectator(p)

        await host.add_spectator(p)

@register
class StopSpectating(ClientPacket, type=ClientPacketType.STOP_SPECTATING):
    async def handle(self, p: Player) -> None:
        host = p.spectating

        if not host:
            log(f"{p} tried to stop spectating when they're not..?", Ansi.LRED)
            return

        await host.remove_spectator(p)

@register
class SpectateFrames(ClientPacket, type=ClientPacketType.SPECTATE_FRAMES):
    play_data: osuTypes.raw

    async def handle(self, p: Player) -> None:
        # this runs very frequently during spectation,
        # so it's written to run pretty quick.

        # read the entire data of the packet, and ignore it internally
        data = packets.spectateFrames(self.play_data)

        # enqueue the data
        # to all spectators.
        for t in p.spectators:
            t.enqueue(data)

@register
class CantSpectate(ClientPacket, type=ClientPacketType.CANT_SPECTATE):
    async def handle(self, p: Player) -> None:
        if not p.spectating:
            log(f"{p} sent can't spectate while not spectating?", Ansi.LRED)
            return

        data = packets.spectatorCantSpectate(p.id)

        host = p.spectating
        host.enqueue(data)

        for t in host.spectators:
            t.enqueue(data)

@register
class SendPrivateMessage(ClientPacket, type=ClientPacketType.SEND_PRIVATE_MESSAGE):
    msg = osuTypes.message

    async def handle(self, p: Player) -> None:
        if p.silenced:
            log(f'{p} tried to send a dm while silenced.', Ansi.YELLOW)
            return

        msg = self.msg.msg
        target = self.msg.target

        if not (t := await glob.players.get_by_name(target)):
            log(f'{p} tried to write to non-existant user {target}.', Ansi.YELLOW)
            return

        if t.pm_private and p.id not in t.friends:
            p.enqueue(packets.userPMBlocked(target))
            log(f'{p} tried to message {t}, but they are blocking dms.')
            return

        if t.silenced:
            p.enqueue(packets.targetSilenced(target))
            log(f'{p} tried to message {t}, but they are silenced.')
            return

        msg = f'{msg[:2045]}...' if msg[2048:] else msg
        client, client_id = p.name, p.id

        if t.status.action == Action.Afk and t.away_msg:
            # send away message if target is afk and has one set.
            p.enqueue(packets.sendMessage(client, t.away_msg, target, client_id))

        if t.id == 1:
            # target is the bot, check if message is a command.
            cmd = msg.startswith(glob.config.command_prefix) \
            and await commands.process_commands(p, t, msg)

            if cmd and 'resp' in cmd:
                # command triggered and there is a response to send.
                p.enqueue(packets.sendMessage(t.name, cmd['resp'], client, t.id))

            else:
                # no commands triggered.
                if match := regexes.now_playing.match(msg):
                    # user is /np'ing a map.
                    # save it to their player instance
                    # so we can use this elsewhere owo..
                    p.last_np = await Beatmap.from_bid(int(match['bid']))

                    if p.last_np:
                        if match['mods']:
                            # [1:] to remove leading whitespace
                            mods = Mods.from_np(match['mods'][1:])
                        else:
                            mods = Mods.NOMOD

                        if mods not in p.last_np.pp_cache:
                            await p.last_np.cache_pp(mods)

                        # since this is a DM to the bot, we should
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

                    else:
                        msg = 'Could not find map.'

                    p.enqueue(packets.sendMessage(t.name, msg, client, t.id))

        else:
            # target is not aika, send the message normally
            t.enqueue(packets.sendMessage(client, msg, target, client_id))

            # insert mail into db,
            # marked as unread.
            await glob.db.execute(
                'INSERT INTO `mail` (`from_id`, `to_id`, `msg`, `time`) '
                'VALUES (%s, %s, %s, UNIX_TIMESTAMP())',
                [p.id, t.id, msg]
            )

        log(f'{p} @ {t}: {msg}', Ansi.CYAN, fd='.data/logs/chat.log')

@register
class LobbyPart(ClientPacket, type=ClientPacketType.PART_LOBBY):
    async def handle(self, p: Player) -> None:
        p.in_lobby = False

@register
class LobbyJoin(ClientPacket, type=ClientPacketType.JOIN_LOBBY):
    async def handle(self, p: Player) -> None:
        p.in_lobby = True

        for m in (_m for _m in glob.matches if _m):
            p.enqueue(packets.newMatch(m))

@register
class MatchCreate(ClientPacket, type=ClientPacketType.CREATE_MATCH):
    match: osuTypes.match

    async def handle(self, p: Player) -> None:
        self.match.host = p
        await p.join_match(self.match, self.match.passwd)
        log(f'{p} created a new multiplayer match.')

@register
class MatchJoin(ClientPacket, type=ClientPacketType.JOIN_MATCH):
    match_id: osuTypes.i32
    match_passwd: osuTypes.string

    async def handle(self, p: Player) -> None:
        if 64 > self.match_id > 0:
            # make sure it's
            # a valid match id.
            return

        if not (m := glob.matches[self.match_id]):
            log(f'{p} tried to join a non-existant mp lobby?')
            return

        await p.join_match(m, self.match_passwd)

@register
class MatchPart(ClientPacket, type=ClientPacketType.PART_MATCH):
    async def handle(self, p: Player) -> None:
        await p.leave_match()

@register
class MatchChangeSlot(ClientPacket, type=ClientPacketType.MATCH_CHANGE_SLOT):
    slot_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        # read new slot ID
        if self.slot_id not in range(16):
            return

        if m.slots[self.slot_id].status & SlotStatus.has_player:
            log(f'{p} tried to switch to slot {self.slot_id} which has a player.')
            return

        # swap with current slot.
        s = m.get_slot(p)
        m.slots[self.slot_id].copy(s)
        s.reset()
        m.enqueue(packets.updateMatch(m))

@register
class MatchReady(ClientPacket, type=ClientPacketType.MATCH_READY):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.get_slot(p).status = SlotStatus.ready
        m.enqueue(packets.updateMatch(m))

@register
class MatchLock(ClientPacket, type=ClientPacketType.MATCH_LOCK):
    slot_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        # read new slot ID
        if self.slot_id not in range(16):
            return

        slot = m.slots[self.slot_id]

        if slot.status & SlotStatus.locked:
            slot.status = SlotStatus.open
        else:
            if slot.player:
                slot.reset()
            slot.status = SlotStatus.locked

        m.enqueue(packets.updateMatch(m))

@register
class MatchChangeSettings(ClientPacket, type=ClientPacketType.MATCH_CHANGE_SETTINGS):
    new: osuTypes.match

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        if self.new.freemods != m.freemods:
            # freemods status has been changed.
            if self.new.freemods:
                # switching to freemods.
                # central mods -> all players mods.
                for s in m.slots:
                    if s.status & SlotStatus.has_player:
                        s.mods = m.mods & ~Mods.SPEED_CHANGING

                m.mods = m.mods & Mods.SPEED_CHANGING
            else:
                # switching to centralized mods.
                # host mods -> central mods.
                for s in m.slots:
                    if s.player and s.player.id == m.host.id:
                        m.mods = s.mods | (m.mods & Mods.SPEED_CHANGING)
                        break

        if not self.new.bmap:
            # map being changed, unready players.
            for s in m.slots:
                if s.status & SlotStatus.ready:
                    s.status = SlotStatus.not_ready
        elif not m.bmap:
            # new map has been chosen, send to match chat.
            await m.chat.send(glob.bot, f'Map selected: {self.new.bmap.embed}.')

        # copy basic match info into our match.
        m.bmap = self.new.bmap
        m.freemods = self.new.freemods
        m.mode = self.new.mode

        if m.team_type != self.new.team_type:
            # team type is changing, find the new appropriate default team.
            # if it's head vs. head, the default should be red, otherwise neutral.
            if self.new.team_type in (MatchTeamTypes.head_to_head,
                                      MatchTeamTypes.tag_coop):
                new_t = Teams.red
            else:
                new_t = Teams.neutral

            # change each active slots team to
            # fit the correspoding team type.
            for s in m.slots:
                if s.player:
                    s.team = new_t

            # change the matches'.
            m.team_type = self.new.team_type

        m.match_scoring = self.new.match_scoring
        m.name = self.new.name

        m.enqueue(packets.updateMatch(m))

@register
class MatchStart(ClientPacket, type=ClientPacketType.MATCH_START):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        for s in m.slots:
            if s.status & SlotStatus.ready:
                s.status = SlotStatus.playing

        m.in_progress = True
        m.enqueue(packets.matchStart(m))

@register
class MatchScoreUpdate(ClientPacket, type=ClientPacketType.MATCH_SCORE_UPDATE):
    play_data: osuTypes.raw

    async def handle(self, p: Player) -> None:
        # this runs very frequently in matches,
        # so it's written to run pretty quick.

        if not (m := p.match):
            return

        # if scorev2 is enabled, read an extra 8 bytes.
        size = 37 if self.play_data[28] else 29 # no idea if required
        data = bytearray(self.play_data)
        data[4] = m.get_slot_id(p)

        m.enqueue(b'0\x00\x00' + size.to_bytes(4, 'little') + data, lobby = False)

@register
class MatchComplete(ClientPacket, type=ClientPacketType.MATCH_COMPLETE):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
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

            for s in m.slots: # reset match statuses
                if s.status == SlotStatus.complete:
                    s.status = SlotStatus.not_ready

@register
class MatchChangeMods(ClientPacket, type=ClientPacketType.MATCH_CHANGE_MODS):
    mods: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        if m.freemods:
            if p.id == m.host.id:
                # allow host to change speed-changing mods.
                m.mods = self.mods & Mods.SPEED_CHANGING

            # set slot mods
            m.get_slot(p).mods = self.mods & ~Mods.SPEED_CHANGING
        else:
            # not freemods, set match mods.
            m.mods = self.mods

        m.enqueue(packets.updateMatch(m))

@register
class MatchLoadComplete(ClientPacket, type=ClientPacketType.MATCH_LOAD_COMPLETE):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        # ready up our player.
        m.get_slot(p).loaded = True

        # check if all players are ready.
        if not any(s.status & SlotStatus.playing and not s.loaded for s in m.slots):
            m.enqueue(packets.matchAllPlayerLoaded(), lobby = False)

@register
class MatchNoBeatmap(ClientPacket, type=ClientPacketType.MATCH_NO_BEATMAP):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.get_slot(p).status = SlotStatus.no_map
        m.enqueue(packets.updateMatch(m))

@register
class MatchNotReady(ClientPacket, type=ClientPacketType.MATCH_NOT_READY):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.get_slot(p).status = SlotStatus.not_ready
        m.enqueue(packets.updateMatch(m), lobby = False)

@register
class MatchFailed(ClientPacket, type=ClientPacketType.MATCH_FAILED):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        # find the player's slot id, and enqueue that
        # they've failed to all other players in the match.
        m.enqueue(packets.matchPlayerFailed(m.get_slot_id(p)))

@register
class MatchHasBeatmap(ClientPacket, type=ClientPacketType.MATCH_HAS_BEATMAP):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.get_slot(p).status = SlotStatus.not_ready
        m.enqueue(packets.updateMatch(m))

@register
class MatchSkipRequest(ClientPacket, type=ClientPacketType.MATCH_SKIP_REQUEST):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.get_slot(p).skipped = True
        m.enqueue(packets.matchPlayerSkipped(p.id))

        for s in m.slots:
            if s.status & SlotStatus.playing and not s.skipped:
                return

        # all users have skipped, enqueue a skip.
        m.enqueue(packets.matchSkip(), lobby = False)

@register
class ChannelJoin(ClientPacket, type=ClientPacketType.CHANNEL_JOIN):
    name: osuTypes.string

    async def handle(self, p: Player) -> None:
        c = glob.channels[self.name]

        if not c or not await p.join_channel(c):
            log(f'{p} failed to join {self.name}.', Ansi.YELLOW)
            return

        # enqueue channelJoin to our player.
        p.enqueue(packets.channelJoin(c.name))

@register
class MatchTransferHost(ClientPacket, type=ClientPacketType.MATCH_TRANSFER_HOST):
    slot_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        # read new slot ID
        if self.slot_id not in range(16):
            return

        if not (t := m[self.slot_id].player):
            log(f'{p} tried to transfer host to an empty slot?')
            return

        m.host = t
        m.host.enqueue(packets.matchTransferHost())
        m.enqueue(packets.updateMatch(m), lobby = False)

@register
class FriendAdd(ClientPacket, type=ClientPacketType.FRIEND_ADD):
    user_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (t := await glob.players.get_by_id(self.user_id)):
            log(f'{p} tried to add a user who is not online! ({self.user_id})')
            return

        if t.id in (1, p.id):
            # trying to add the bot, or themselves.
            # these are already appended to the friends list
            # on login, so disallow the user from *actually*
            # editing these in sql.
            return

        await p.add_friend(t)

@register
class FriendRemove(ClientPacket, type=ClientPacketType.FRIEND_REMOVE):
    user_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (t := await glob.players.get_by_id(self.user_id)):
            log(f'{p} tried to remove a user who is not online! ({self.user_id})')
            return

        if t.id in (1, p.id):
            # trying to remove the bot, or themselves.
            # these are already appended to the friends list
            # on login, so disallow the user from *actually*
            # editing these in sql.
            return

        await p.remove_friend(t)

@register
class MatchChangeTeam(ClientPacket, type=ClientPacketType.MATCH_CHANGE_TEAM):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        for s in m.slots:
            if p == s.player:
                s.team = Teams.blue if s.team != Teams.blue else Teams.red
                break
        else:
            log(f'{p} tried changing team outside of a match? (2)')
            return

        m.enqueue(packets.updateMatch(m), lobby = False)

@register
class ChannelPart(ClientPacket, type=ClientPacketType.CHANNEL_PART):
    name: osuTypes.string

    async def handle(self, p: Player) -> None:
        c = glob.channels[self.name]

        if not c:
            log(f'{p} failed to leave {self.name}.', Ansi.YELLOW)
            return

        if p not in c:
            # user not in chan
            return

        # leave the chan server-side.
        await p.leave_channel(c)

        # enqueue new playercount to all players.

@register
class ReceiveUpdates(ClientPacket, type=ClientPacketType.RECEIVE_UPDATES):
    value: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if self.value not in range(3):
            log(f'{p} tried to set his presence filter to {self.value}?')
            return

        p.pres_filter = PresenceFilter(self.value)

@register
class SetAwayMessage(ClientPacket, type=ClientPacketType.SET_AWAY_MESSAGE):
    msg: osuTypes.message

    async def handle(self, p: Player) -> None:
        p.away_msg = self.msg.msg

@register
class StatsRequest(ClientPacket, type=ClientPacketType.USER_STATS_REQUEST):
    user_ids: osuTypes.i32_list

    async def handle(self, p: Player) -> None:
        is_online = lambda o: o in glob.players.ids and o != p.id

        for online in filter(is_online, self.user_ids):
            if t := await glob.players.get_by_id(online):
                p.enqueue(packets.userStats(t))

@register
class MatchInvite(ClientPacket, type=ClientPacketType.MATCH_INVITE):
    user_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not p.match:
            return

        if not (t := await glob.players.get_by_id(self.user_id)):
            log(f'{p} tried to invite a user who is not online! ({self.user_id})')
            return

        t.enqueue(packets.matchInvite(p, t.name))
        log(f'{p} invited {t} to their match.')

@register
class MatchChangePassword(ClientPacket, type=ClientPacketType.MATCH_CHANGE_PASSWORD):
    passwd: osuTypes.string

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.passwd = self.passwd
        m.enqueue(packets.updateMatch(m), lobby=False)

@register
class UserPresenceRequest(ClientPacket, type=ClientPacketType.USER_PRESENCE_REQUEST):
    user_ids: osuTypes.i32_list

    async def handle(self, p: Player) -> None:
        for pid in self.user_ids:
            if t := await glob.players.get_by_id(pid):
                p.enqueue(packets.userPresence(t))

@register
class UserPresenceRequestAll(ClientPacket, type=ClientPacketType.USER_PRESENCE_REQUEST_ALL):
    async def handle(self, p: Player) -> None:
        # XXX: this only sends when the client can see > 256 players,
        # so this probably won't have much use for private servers.

        # NOTE: i'm not exactly sure how bancho implements this and whether
        # i'm supposed to filter the users presences to send back with the
        # player's presence filter; i can add it in the future perhaps.
        for t in glob.players:
            if p != t:
                p.enqueue(packets.userPresence(t))

@register
class ToggleBlockingDMs(ClientPacket, type=ClientPacketType.TOGGLE_BLOCK_NON_FRIEND_DMS):
    value: osuTypes.i32

    async def handle(self, p: Player) -> None:
        p.pm_private = self.value == 1
