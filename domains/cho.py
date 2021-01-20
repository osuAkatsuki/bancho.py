# -*- coding: utf-8 -*-

import asyncio
import re
import time
import bcrypt
from cmyui import (Connection, Domain,
                   log, Ansi, _isdecimal)
from datetime import datetime as dt, timedelta as td

import packets
from packets import Packets, BanchoPacket, BanchoPacketReader

from constants.types import osuTypes
from constants.mods import Mods
from constants.privileges import Privileges
from constants.gamemodes import GameMode
from constants import commands
from constants import regexes

from objects.match import MatchTeamTypes, SlotStatus, MatchTeams
from objects.player import Player, PresenceFilter, Action
from objects.channel import Channel
from objects.beatmap import Beatmap
from objects.clan import ClanRank
from objects import glob

from utils.misc import make_safe_name

""" Bancho: handle connections from the osu! client """

domain = Domain(re.compile(r'^c[e4-6]?\.ppy\.sh$'))

@domain.route('/')
async def bancho_http_handler(conn: Connection) -> bytes:
    # Handle requests from browser by returning html
    return b'<!DOCTYPE html>' + '<br>'.join((
        f'Running gulag v{glob.version}',
        f'Players online: {len(glob.players) - 1}',
        '<a href="https://github.com/cmyui/gulag">Source code</a>',
        '',
        f'<b>Packets handled ({len(glob.bancho_packets)})</b>',
        '<br>'.join(f'{p.name} ({p.value})' for p in glob.bancho_packets)
    )).encode()

@domain.route('/', methods=['POST'])
async def bancho_handler(conn: Connection) -> bytes:
    if 'User-Agent' not in conn.headers \
    or conn.headers['User-Agent'] != 'osu!':
        return

    # check for 'osu-token' in the headers.
    # if it's not there, this is a login request.

    if 'osu-token' not in conn.headers:
        # login is a bit of a special case,
        # so we'll handle it separately.
        async with asyncio.Lock():
            resp, token = await login(
                conn.body, conn.headers['X-Real-IP']
            )

        conn.add_resp_header(f'cho-token: {token}')
        return resp

    # get the player from the specified osu token.
    player = await glob.players.get(token=conn.headers['osu-token'])

    if not player:
        # token was not found; changes are, we just restarted
        # the server. just tell their client to re-connect.
        return packets.notification('Server is restarting') + \
               packets.restartServer(0) # send 0ms since server is up

    # bancho connections can be comprised of multiple packets;
    # our reader is designed to iterate through them individually,
    # allowing logic to be implemented around the actual handler.

    # NOTE: the reader will internally discard any
    # packets whose logic has not been defined.
    # TODO: why is the packet reader async lol
    async for packet in BanchoPacketReader(conn.body):
        await packet.handle(player)

        if glob.config.debug:
            log(f'{packet.type!r}', Ansi.LMAGENTA)

    player.last_recv_time = time.time()

    # TODO: this could probably be done better?
    resp = bytearray()

    while not player.queue_empty():
        # read all queued packets into stream
        resp += player.dequeue()

    conn.add_resp_header('Content-Type: text/html; charset=UTF-8')
    resp = bytes(resp)

    # even if the packet is empty, we have to
    # send back an empty response so the client
    # knows it was successfully delivered.
    return resp

""" Packet logic """

glob.bancho_packets = {}

def register(cls: BanchoPacket):
    """Register a handler in `glob.bancho_packets`."""
    glob.bancho_packets |= {cls.type: cls}
    return cls

@register
class ChangeAction(BanchoPacket, type=Packets.OSU_CHANGE_ACTION):
    action: osuTypes.u8
    info_text: osuTypes.string
    map_md5: osuTypes.string
    mods: osuTypes.u32
    mode: osuTypes.u8
    map_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        # update the user's status.
        p.status.action = Action(self.action)
        p.status.info_text = self.info_text
        p.status.map_md5 = self.map_md5
        p.status.mods = Mods(self.mods)

        if p.status.mods & Mods.RELAX:
            self.mode += 4
        elif p.status.mods & Mods.AUTOPILOT:
            self.mode = 7

        p.status.mode = GameMode(self.mode)
        p.status.map_id = self.map_id

        # broadcast it to all online players.
        glob.players.enqueue(packets.userStats(p))

@register
class SendMessage(BanchoPacket, type=Packets.OSU_SEND_PUBLIC_MESSAGE):
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

            t = p.match.chat
        else:
            t = glob.channels[target]

        if not t:
            log(f'{p} wrote to non-existent {target}.', Ansi.YELLOW)
            return

        if not p.priv & t.write_priv:
            log(f'{p} wrote to {target} with insufficient privileges.')
            return

        # limit message length to 2048 characters
        msg = f'{msg[:2045]}...' if msg[2048:] else msg

        cmd = msg.startswith(glob.config.command_prefix) \
          and await commands.process_commands(p, t, msg)

        if cmd:
            # a command was triggered.
            if not cmd['hidden']:
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

        await p.update_latest_activity()
        log(f'{p} @ {t}: {msg}', Ansi.CYAN, fd='.data/logs/chat.log')

@register
class Logout(BanchoPacket, type=Packets.OSU_LOGOUT):
    _: osuTypes.i32 # pretty awesome design on osu!'s end :P

    async def handle(self, p: Player) -> None:
        if (time.time() - p.login_time) < 2:
            # osu! has a weird tendency to log out immediately when
            # it logs in, then reconnects? not sure why..?
            return

        await p.logout()
        await p.update_latest_activity()
        log(f'{p} logged out.', Ansi.LYELLOW)

@register
class StatsUpdateRequest(BanchoPacket, type=Packets.OSU_REQUEST_STATUS_UPDATE):
    async def handle(self, p: Player) -> None:
        p.enqueue(packets.userStats(p))

# no specific packet id, triggered when the
# client sends a request without an osu-token.
async def login(origin: bytes, ip: str) -> tuple[bytes, str]:
    # login is a bit special, we return the response bytes
    # and token in a tuple - we need both for our response.
    if len(s := origin.decode().split('\n')[:-1]) != 3:
        return

    username = s[0]
    login_time = time.time()

    if p := await glob.players.get(name=username):
        if (login_time - p.last_recv_time) > 10:
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

    pw_md5 = s[1].encode()

    if len(s := s[2].split('|')) != 5:
        return packets.userID(-2), 'no'

    if not (r := regexes.osu_ver.match(s[0])):
        # invalid client version?
        return packets.userID(-2), 'no'

    osu_ver = dt.strptime(r['ver'], '%Y%m%d')

    if not glob.config.debug:
        # disallow the login if their osu! client is older
        # than two months old, forcing an update re-check.
        if osu_ver < (dt.now() - td(60)):
            return (packets.versionUpdateForced() +
                    packets.userID(-2)), 'no'

    if not _isdecimal(s[1], _negative=True):
        # utc-offset isn't a number (negative inclusive).
        return packets.userID(-1), 'no'

    utc_offset = int(s[1])
    #display_city = s[2] == '1'

    # Client hashes contain a few values useful to us.
    # [0]: md5(osu path)
    # [1]: adapters (network physical addresses delimited by '.')
    # [2]: md5(adapters)
    # [3]: md5(uniqueid) (osu! uninstall id)
    # [4]: md5(uniqueid2) (disk signature/serial num)
    client_hashes = s[3].split(':')[:-1]
    client_hashes.pop(1) # no need for non-md5 adapters

    pm_private = s[4] == '1'

    user_info = await glob.db.fetch(
        'SELECT id, name, priv, pw_bcrypt, '
        'silence_end, clan_id, clan_rank '
        'FROM users WHERE safe_name = %s',
        [make_safe_name(username)]
    )

    if not user_info:
        # no account by this name exists.
        return packets.userID(-1), 'no'

    # get our bcrypt cache.
    bcrypt_cache = glob.cache['bcrypt']
    pw_bcrypt = user_info['pw_bcrypt'].encode()
    user_info['pw_bcrypt'] = pw_bcrypt

    # check credentials against db.
    # algorithms like these are intentionally
    # designed to be slow; we'll cache the
    # results to speed up subsequent logins.
    if pw_bcrypt in bcrypt_cache: # ~0.01 ms
        if pw_md5 != bcrypt_cache[pw_bcrypt]:
            return packets.userID(-1), 'no'
    else: # ~200ms
        if not bcrypt.checkpw(pw_md5, pw_bcrypt):
            return packets.userID(-1), 'no'

        bcrypt_cache[pw_bcrypt] = pw_md5

    # check if the user is banned.
    if not user_info['priv'] & Privileges.Normal:
        return packets.userID(-3), 'no'

    """ handle client hashes """

    # insert new set/occurrence.
    await glob.db.execute(
        'INSERT INTO client_hashes '
        'VALUES (%s, %s, %s, %s, %s, NOW(), 0) '
        'ON DUPLICATE KEY UPDATE '
        'occurrences = occurrences + 1, '
        'latest_time = NOW() ',
        [user_info['id'], *client_hashes]
    )

    # TODO: runningunderwine support

    # find any other users from any of the same hwid values.
    hwid_matches = await glob.db.fetchall(
        'SELECT u.`name`, u.`priv`, h.`occurrences` '
        'FROM `client_hashes` h '
        'INNER JOIN `users` u ON h.`userid` = u.`id` '
        'WHERE h.`userid` != %s AND (h.`adapters` = %s '
        'OR h.`uninstall_id` = %s OR h.`disk_serial` = %s)',
        [user_info['id'], *client_hashes[1:]]
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

        if not user_info['priv'] & Privileges.Verified:
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

    if first_login := not user_info['priv'] & Privileges.Verified:
        # verify the account if it's made it this far
        user_info['priv'] |= int(Privileges.Verified)

        # if this is the first user to create an account,
        # grant them all gulag privileges.
        if user_info['id'] == 3:
            user_info['priv'] |= int(
                Privileges.Staff | Privileges.Donator |
                Privileges.Tournament | Privileges.Whitelisted
            )

        await glob.db.execute(
            'UPDATE users '
            'SET priv = %s '
            'WHERE id = %s',
            [user_info['priv'], user_info['id']]
        )

    # get clan & clan rank if we're in a clan
    if user_info['clan_id'] != 0:
        clan = glob.clans.get(id=user_info.pop('clan_id'))
        clan_rank = ClanRank(user_info.pop('clan_rank'))
    else:
        del user_info['clan_id']
        del user_info['clan_rank']
        clan = clan_rank = None

    # user_info: {id, name, priv, pw_bcrypt, silence_end}
    p = Player.login(user_info, utc_offset=utc_offset,
                     osu_ver=osu_ver, pm_private=pm_private,
                     login_time=login_time, clan=clan,
                     clan_rank=clan_rank)

    data = bytearray(packets.userID(p.id))
    data += packets.protocolVersion(19)
    data += packets.banchoPrivileges(p.bancho_priv)
    data += packets.notification('Welcome back to the gulag!\n'
                                f'Current build: {glob.version}')

    # tells osu! to load channels from config, i believe?
    data += packets.channelInfoEnd()

    # channels
    for c in glob.channels:
        if not p.priv & c.read_priv:
            continue # no priv to read

        # autojoinable channels
        if c.auto_join and await p.join_channel(c):
            # NOTE: p.join_channel enqueues channelJoin, but
            # if we don't send this back in this specific request,
            # the client will attempt to join the channel again.
            data += packets.channelJoin(c.name)

        data += packets.channelInfo(*c.basic_info)

    # fetch some of the player's
    # information from sql to be cached.
    await p.achievements_from_sql()
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

    data += user_data

    # o for online, or other
    for o in glob.players:
        # enqueue us to them
        o.enqueue(user_data)

        # enqueue them to us.
        data += packets.userPresence(o)
        data += packets.userStats(o)

    data += packets.mainMenuIcon()
    data += packets.friendsList(*p.friends)
    data += packets.silenceEnd(p.remaining_silence)

    # thank u osu for doing this by username rather than id
    query = ('SELECT m.`msg`, m.`time`, m.`from_id`, '
             '(SELECT name FROM users WHERE id = m.`from_id`) AS `from`, '
             '(SELECT name FROM users WHERE id = m.`to_id`) AS `to` '
             'FROM `mail` m WHERE m.`to_id` = %s AND m.`read` = 0')

    # the player may have been sent mail while offline,
    # enqueue any messages from their respective authors.
    async for msg in glob.db.iterall(query, [p.id]):
        msg_time = dt.fromtimestamp(msg['time'])
        msg_ts = f'[{msg_time:%a %b %d @ %H:%M%p}] {msg["msg"]}'

        data += packets.sendMessage(
            msg['from'], msg_ts,
            msg['to'], msg['from_id']
        )

    # TODO: add a registration message if `first_login` == True?

    # TODO: enqueue ingame admin panel to staff members.
    """
    if p.priv & Privileges.Staff:
        async def get_server_stats():
            notif = packets.notification('\n'.join((
                f'Players online: {len(glob.players)}',
                f'Staff online: {len(glob.players.staff)}'
            )))

            p.enqueue(notif)

        server_stats = await p.add_to_menu(get_server_stats, reusable=True)

        admin_panel = (
            f'[osu://dl/{server_stats} server_stats]',
        )

        await p.send(glob.bot, ' '.join(admin_panel))
    """

    # add `p` to the global player list,
    # making them officially logged in.
    glob.players.append(p)

    log(f'{p} logged in.', Ansi.LCYAN)
    await p.update_latest_activity()
    return bytes(data), p.token

@register
class StartSpectating(BanchoPacket, type=Packets.OSU_START_SPECTATING):
    target_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (host := await glob.players.get(id=self.target_id)):
            log(f'{p} tried to spectate nonexistant id {self.target_id}.', Ansi.YELLOW)
            return

        if c_host := p.spectating:
            await c_host.remove_spectator(p)

        await host.add_spectator(p)

@register
class StopSpectating(BanchoPacket, type=Packets.OSU_STOP_SPECTATING):
    async def handle(self, p: Player) -> None:
        host = p.spectating

        if not host:
            log(f"{p} tried to stop spectating when they're not..?", Ansi.LRED)
            return

        await host.remove_spectator(p)

@register
class SpectateFrames(BanchoPacket, type=Packets.OSU_SPECTATE_FRAMES):
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
class CantSpectate(BanchoPacket, type=Packets.OSU_CANT_SPECTATE):
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
class SendPrivateMessage(BanchoPacket, type=Packets.OSU_SEND_PRIVATE_MESSAGE):
    msg: osuTypes.message

    async def handle(self, p: Player) -> None:
        if p.silenced:
            log(f'{p} tried to send a dm while silenced.', Ansi.YELLOW)
            return

        msg = self.msg.msg
        target = self.msg.target

        # allow this to get from sql - players can receive
        # messages offline, due to the mail system. B)
        if not (t := await glob.players.get(name=target, sql=True)):
            log(f'{p} tried to write to non-existent user {target}.', Ansi.YELLOW)
            return

        if t.pm_private and p.id not in t.friends:
            p.enqueue(packets.userDMBlocked(target))
            log(f'{p} tried to message {t}, but they are blocking dms.')
            return

        if t.silenced:
            # if target is silenced, inform player.
            p.enqueue(packets.targetSilenced(target))
            log(f'{p} tried to message {t}, but they are silenced.')
            return

        msg = f'{msg[:2045]}...' if msg[2048:] else msg

        if t.status.action == Action.Afk and t.away_msg:
            # send away message if target is afk and has one set.
            await p.send(p.name, t.away_msg)

        if t is glob.bot:
            # may have a command in the message.
            cmd = msg.startswith(glob.config.command_prefix) \
            and await commands.process_commands(p, t, msg)

            if cmd:
                # command triggered, send response if any.
                if 'resp' in cmd:
                    await p.send(t, cmd['resp'])
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
                            _msg.append(f'+{mods!r}')

                        msg = f"{' '.join(_msg)}: " + ' | '.join(
                            f'{acc}%: {pp:.2f}pp'
                            for acc, pp in zip(
                                (90, 95, 98, 99, 100),
                                p.last_np.pp_cache[mods]
                            ))

                    else:
                        msg = 'Could not find map.'

                    await p.send(t, msg)

        else:
            # target is not aika, send the message normally if online
            if t.online:
                await t.send(p, msg)
            else:
                # inform user they're offline, but
                # will receive the mail @ next login.
                p.enqueue(packets.notification(
                    f'{t.name} is currently offline, but will '
                    'receive your messsage on their next login.'
                ))

            # insert mail into db,
            # marked as unread.
            await glob.db.execute(
                'INSERT INTO `mail` (`from_id`, `to_id`, `msg`, `time`) '
                'VALUES (%s, %s, %s, UNIX_TIMESTAMP())',
                [p.id, t.id, msg]
            )

        await p.update_latest_activity()
        log(f'{p} @ {t}: {msg}', Ansi.CYAN, fd='.data/logs/chat.log')

@register
class LobbyPart(BanchoPacket, type=Packets.OSU_PART_LOBBY):
    async def handle(self, p: Player) -> None:
        p.in_lobby=False

@register
class LobbyJoin(BanchoPacket, type=Packets.OSU_JOIN_LOBBY):
    async def handle(self, p: Player) -> None:
        p.in_lobby = True

        for m in (_m for _m in glob.matches if _m):
            p.enqueue(packets.newMatch(m))

@register
class MatchCreate(BanchoPacket, type=Packets.OSU_CREATE_MATCH):
    match: osuTypes.match

    async def handle(self, p: Player) -> None:
        if not glob.matches.append(self.match):
            # failed to create match (match slots full).
            await p.send(glob.bot, 'Failed to create match (no slots available).')
            p.enqueue(packets.matchJoinFail())
            return

        # create the channel and add it
        # to the global channel list as
        # an instanced channel.
        chan = Channel(
            name=f'#multi_{self.match.id}',
            topic=f"MID {self.match.id}'s multiplayer channel.",
            auto_join=False,
            instance=True
        )

        glob.channels.append(chan)
        self.match.chat = chan

        await p.update_latest_activity()
        await p.join_match(self.match, self.match.passwd)
        log(f'{p} created a new multiplayer match.')

@register
class MatchJoin(BanchoPacket, type=Packets.OSU_JOIN_MATCH):
    match_id: osuTypes.i32
    match_passwd: osuTypes.string

    async def handle(self, p: Player) -> None:
        if not 0 <= self.match_id < 64:
            # make sure it's
            # a valid match id.
            return

        if not (m := glob.matches[self.match_id]):
            log(f'{p} tried to join a non-existant mp lobby?')
            return

        await p.update_latest_activity()
        await p.join_match(m, self.match_passwd)

@register
class MatchPart(BanchoPacket, type=Packets.OSU_PART_MATCH):
    async def handle(self, p: Player) -> None:
        await p.update_latest_activity()
        await p.leave_match()

@register
class MatchChangeSlot(BanchoPacket, type=Packets.OSU_MATCH_CHANGE_SLOT):
    slot_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        # read new slot ID
        if not 0 <= self.slot_id < 16:
            return

        if m.slots[self.slot_id].status & SlotStatus.has_player:
            log(f'{p} tried to move into a slot with another player.')
            return

        if m.slots[self.slot_id].status == SlotStatus.locked:
            log(f'{p} tried to move to into locked slot.')
            return

        # swap with current slot.
        s = m.get_slot(p)
        m.slots[self.slot_id].copy(s)
        s.reset()
        m.enqueue_state() # technically not needed for host?

@register
class MatchReady(BanchoPacket, type=Packets.OSU_MATCH_READY):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.get_slot(p).status = SlotStatus.ready
        m.enqueue_state(lobby=False)

@register
class MatchLock(BanchoPacket, type=Packets.OSU_MATCH_LOCK):
    slot_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        # read new slot ID
        if not 0 <= self.slot_id < 16:
            return

        slot = m.slots[self.slot_id]

        if slot.status == SlotStatus.locked:
            slot.status = SlotStatus.open
        else:
            if slot.player:
                slot.reset()
            slot.status = SlotStatus.locked

        m.enqueue_state()

@register
class MatchChangeSettings(BanchoPacket, type=Packets.OSU_MATCH_CHANGE_SETTINGS):
    new: osuTypes.match

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        if self.new.freemods != m.freemods:
            # freemods status has been changed.

            if self.new.freemods:
                # match mods -> active slot mods.
                for s in m.slots:
                    if s.status & SlotStatus.has_player:
                        # the slot takes any non-speed
                        # changing mods from the match.
                        s.mods = m.mods & ~Mods.SPEED_CHANGING

                # keep only speed-changing mods.
                m.mods &= Mods.SPEED_CHANGING
            else:
                # host mods -> match mods.
                host = m.get_host_slot() # should always exist
                # the match keeps any speed-changing mods,
                # and also takes any mods the host has enabled.
                m.mods &= Mods.SPEED_CHANGING
                m.mods |= host.mods

        if self.new.map_id == -1:
            # map being changed, unready players.
            m.unready_players(expected=SlotStatus.ready)
        elif m.map_id == -1:
            # new map has been chosen, send to match chat.
            await m.chat.send(glob.bot, f'Map selected: {self.new.map_embed}.')

        # copy map & basic match info
        m.map_id = self.new.map_id
        m.map_md5 = self.new.map_md5
        m.map_name = self.new.map_name
        m.freemods = self.new.freemods
        m.mode = self.new.mode

        if m.team_type != self.new.team_type:
            # if theres currently a scrim going on, only allow
            # team type to change by using the !mp teams command.
            if m.is_scrimming:
                _team = (
                    'head-to-head', 'tag-coop',
                    'team-vs', 'tag-team-vs'
                )[self.new.team_type]

                msg = ('Changing team type while scrimming will reset '
                       'the overall score - to do so, please use the '
                       f'!mp teams {_team} command.')
                await m.chat.send(glob.bot, msg)
            else:
                # find the new appropriate default team.
                # defaults are (ffa: neutral, teams: red).
                if self.new.team_type in (MatchTeamTypes.head_to_head,
                                          MatchTeamTypes.tag_coop):
                    new_t = MatchTeams.neutral
                else:
                    new_t = MatchTeams.red

                # change each active slots team to
                # fit the correspoding team type.
                for s in m.slots:
                    if s.status & SlotStatus.has_player:
                        s.team = new_t

                # change the matches'.
                m.team_type = self.new.team_type

        if m.win_condition != self.new.win_condition:
            # win condition changing; if `use_pp_scoring`
            # is enabled, disable it. always use new cond.
            if m.use_pp_scoring:
                m.use_pp_scoring = False

            m.win_condition = self.new.win_condition

        m.name = self.new.name

        m.enqueue_state()

@register
class MatchStart(BanchoPacket, type=Packets.OSU_MATCH_START):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.start()

@register
class MatchScoreUpdate(BanchoPacket, type=Packets.OSU_MATCH_SCORE_UPDATE):
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

        m.enqueue(b'0\x00\x00' + size.to_bytes(4, 'little') + data, lobby=False)

@register
class MatchComplete(BanchoPacket, type=Packets.OSU_MATCH_COMPLETE):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.get_slot(p).status = SlotStatus.complete

        # check if there are any players that haven't finished.
        if any(s.status == SlotStatus.playing for s in m.slots):
            return

        # find any players just sitting in the multi room
        # that have not been playing the map; they don't
        # need to know all the players have completed, only
        # the ones who are playing (just new match info).
        not_playing = [s.player.id for s in m.slots
                       if s.status & SlotStatus.has_player
                       and s.status != SlotStatus.complete]

        was_playing = [s for s in m.slots if s.player
                       and s.player.id not in not_playing]

        m.unready_players(expected=SlotStatus.complete)

        m.in_progress = False
        m.enqueue(packets.matchComplete(), lobby=False, immune=not_playing)
        m.enqueue_state()

        if m.is_scrimming:
            # determine winner, update match points & inform players.
            asyncio.create_task(m.update_matchpoints(was_playing))

@register
class MatchChangeMods(BanchoPacket, type=Packets.OSU_MATCH_CHANGE_MODS):
    mods: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        if m.freemods:
            if p is m.host:
                # allow host to set speed-changing mods.
                m.mods = self.mods & Mods.SPEED_CHANGING

            # set slot mods
            m.get_slot(p).mods = self.mods & ~Mods.SPEED_CHANGING
        else:
            # not freemods, set match mods.
            m.mods = self.mods

        m.enqueue_state()

@register
class MatchLoadComplete(BanchoPacket, type=Packets.OSU_MATCH_LOAD_COMPLETE):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        # our player has loaded in and is ready to play.
        m.get_slot(p).loaded = True

        is_playing = lambda s: s.status == SlotStatus.playing \
                           and not s.loaded

        # check if all players are loaded,
        # if so, tell all players to begin.
        if not any(map(is_playing, m.slots)):
            m.enqueue(packets.matchAllPlayerLoaded(), lobby=False)

@register
class MatchNoBeatmap(BanchoPacket, type=Packets.OSU_MATCH_NO_BEATMAP):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.get_slot(p).status = SlotStatus.no_map
        m.enqueue_state(lobby=False)

@register
class MatchNotReady(BanchoPacket, type=Packets.OSU_MATCH_NOT_READY):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.get_slot(p).status = SlotStatus.not_ready
        m.enqueue_state(lobby=False)

@register
class MatchFailed(BanchoPacket, type=Packets.OSU_MATCH_FAILED):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        # find the player's slot id, and enqueue that
        # they've failed to all other players in the match.
        m.enqueue(packets.matchPlayerFailed(m.get_slot_id(p)), lobby=False)

@register
class MatchHasBeatmap(BanchoPacket, type=Packets.OSU_MATCH_HAS_BEATMAP):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.get_slot(p).status = SlotStatus.not_ready
        m.enqueue_state(lobby=False)

@register
class MatchSkipRequest(BanchoPacket, type=Packets.OSU_MATCH_SKIP_REQUEST):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.get_slot(p).skipped = True
        m.enqueue(packets.matchPlayerSkipped(p.id))

        for s in m.slots:
            if s.status == SlotStatus.playing and not s.skipped:
                return

        # all users have skipped, enqueue a skip.
        m.enqueue(packets.matchSkip(), lobby=False)

@register
class ChannelJoin(BanchoPacket, type=Packets.OSU_CHANNEL_JOIN):
    name: osuTypes.string

    async def handle(self, p: Player) -> None:
        c = glob.channels[self.name]

        if not c or not await p.join_channel(c):
            log(f'{p} failed to join {self.name}.', Ansi.YELLOW)
            return

        # enqueue channelJoin to our player.
        p.enqueue(packets.channelJoin(c.name))

@register
class MatchTransferHost(BanchoPacket, type=Packets.OSU_MATCH_TRANSFER_HOST):
    slot_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        if p is not m.host:
            return

        # read new slot ID
        if not 0 <= self.slot_id < 16:
            return

        if not (t := m[self.slot_id].player):
            log(f'{p} tried to transfer host to an empty slot?')
            return

        m.host = t
        m.host.enqueue(packets.matchTransferHost())
        m.enqueue_state()

@register
class FriendAdd(BanchoPacket, type=Packets.OSU_FRIEND_ADD):
    user_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (t := await glob.players.get(id=self.user_id)):
            log(f'{p} tried to add a user who is not online! ({self.user_id})')
            return

        if t.id in (1, p.id):
            # trying to add the bot, or themselves.
            # these are already appended to the friends list
            # on login, so disallow the user from *actually*
            # editing these in sql.
            return

        await p.update_latest_activity()
        await p.add_friend(t)

@register
class FriendRemove(BanchoPacket, type=Packets.OSU_FRIEND_REMOVE):
    user_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not (t := await glob.players.get(id=self.user_id)):
            log(f'{p} tried to remove a user who is not online! ({self.user_id})')
            return

        if t.id in (1, p.id):
            # trying to remove the bot, or themselves.
            # these are already appended to the friends list
            # on login, so disallow the user from *actually*
            # editing these in sql.
            return

        await p.update_latest_activity()
        await p.remove_friend(t)

@register
class MatchChangeTeam(BanchoPacket, type=Packets.OSU_MATCH_CHANGE_TEAM):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        for s in m.slots:
            if p is s.player:
                s.team = MatchTeams.blue if s.team != MatchTeams.blue else MatchTeams.red
                break
        else:
            log(f'{p} tried changing team outside of a match? (2)')
            return

        m.enqueue_state(lobby=False)

@register
class ChannelPart(BanchoPacket, type=Packets.OSU_CHANNEL_PART):
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
class ReceiveUpdates(BanchoPacket, type=Packets.OSU_RECEIVE_UPDATES):
    value: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not 0 <= self.value < 3:
            log(f'{p} tried to set his presence filter to {self.value}?')
            return

        p.pres_filter = PresenceFilter(self.value)

@register
class SetAwayMessage(BanchoPacket, type=Packets.OSU_SET_AWAY_MESSAGE):
    msg: osuTypes.message

    async def handle(self, p: Player) -> None:
        p.away_msg = self.msg.msg

@register
class StatsRequest(BanchoPacket, type=Packets.OSU_USER_STATS_REQUEST):
    user_ids: osuTypes.i32_list

    async def handle(self, p: Player) -> None:
        is_online = lambda o: o in glob.players.ids and o != p.id

        for online in filter(is_online, self.user_ids):
            if t := await glob.players.get(id=online):
                p.enqueue(packets.userStats(t))

@register
class MatchInvite(BanchoPacket, type=Packets.OSU_MATCH_INVITE):
    user_id: osuTypes.i32

    async def handle(self, p: Player) -> None:
        if not p.match:
            return

        if not (t := await glob.players.get(id=self.user_id)):
            log(f'{p} tried to invite a user who is not online! ({self.user_id})')
            return

        t.enqueue(packets.matchInvite(p, t.name))
        await p.update_latest_activity()

        log(f'{p} invited {t} to their match.')

@register
class MatchChangePassword(BanchoPacket, type=Packets.OSU_MATCH_CHANGE_PASSWORD):
    match: osuTypes.match

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        m.passwd = self.match.passwd
        m.enqueue_state()

@register
class UserPresenceRequest(BanchoPacket, type=Packets.OSU_USER_PRESENCE_REQUEST):
    user_ids: osuTypes.i32_list

    async def handle(self, p: Player) -> None:
        for pid in self.user_ids:
            if t := await glob.players.get(id=pid):
                p.enqueue(packets.userPresence(t))

@register
class UserPresenceRequestAll(BanchoPacket, type=Packets.OSU_USER_PRESENCE_REQUEST_ALL):
    async def handle(self, p: Player) -> None:
        # XXX: this only sends when the client can see > 256 players,
        # so this probably won't have much use for private servers.

        # NOTE: i'm not exactly sure how bancho implements this and whether
        # i'm supposed to filter the users presences to send back with the
        # player's presence filter; i can add it in the future perhaps.
        for t in glob.players:
            if p is not t:
                p.enqueue(packets.userPresence(t))

@register
class ToggleBlockingDMs(BanchoPacket, type=Packets.OSU_TOGGLE_BLOCK_NON_FRIEND_DMS):
    value: osuTypes.i32

    async def handle(self, p: Player) -> None:
        p.pm_private = self.value == 1

        await p.update_latest_activity()
