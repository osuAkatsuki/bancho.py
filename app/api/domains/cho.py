""" cho: handle connections from the osu! client """
import asyncio
import ipaddress
import struct
import time
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Callable
from typing import Literal
from typing import Optional
from typing import Type

import bcrypt
from cmyui.logging import Ansi
from cmyui.logging import log
from cmyui.logging import RGB
from cmyui.osu.oppai_ng import OppaiWrapper
from cmyui.utils import magnitude_fmt_time
from fastapi.param_functions import Header
from fastapi.requests import Request
from peace_performance_python.objects import Beatmap as PeaceMap
from peace_performance_python.objects import Calculator as PeaceCalculator

import app.misc.utils
import app.services
import packets
from app.constants import commands
from app.constants import regexes
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.mods import SPEED_CHANGING_MODS
from app.constants.privileges import ClientPrivileges
from app.constants.privileges import Privileges
from app.objects import glob
from app.objects.beatmap import Beatmap
from app.objects.beatmap import ensure_local_osu_file
from app.objects.channel import Channel
from app.objects.clan import ClanPrivileges
from app.objects.match import MatchTeams
from app.objects.match import MatchTeamTypes
from app.objects.match import Slot
from app.objects.match import SlotStatus
from app.objects.menu import Menu
from app.objects.menu import MenuCommands
from app.objects.menu import MenuFunction
from app.objects.player import Action
from app.objects.player import Player
from app.objects.player import PresenceFilter
from packets import BanchoPacketReader
from packets import BasePacket
from packets import ClientPackets

import sqlalchemy.ext.asyncio

# HTTPResponse = Optional[Union[bytes, tuple[int, bytes]]]

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

router = APIRouter(prefix="/cho", tags=["Bancho API"])

BEATMAPS_PATH = Path.cwd() / ".data/osu"

BASE_DOMAIN = glob.config.domain


@router.get("/")
async def bancho_http_handler() -> Response:
    """Handle a request from a web browser."""
    packets = glob.bancho_packets["all"]

    return HTMLResponse(
        b"<!DOCTYPE html>"
        + "<br>".join(
            (
                f"Running gulag v{glob.version}",
                f"Players online: {len(glob.players) - 1}",
                '<a href="https://github.com/cmyui/gulag">Source code</a>',
                "",
                f"<b>Packets handled ({len(packets)})</b>",
                "<br>".join([f"{p.name} ({p.value})" for p in packets]),
            ),
        ).encode(),
    )


@router.post("/")
async def bancho_handler(
    request: Request,
    response: Response,
    # TODO: add further validation to these params
    # forwarded to our server from nginx
    x_forwarded_for: str = Header(None),
    x_real_ip: str = Header(None),
    # forwarded to our server from cloudflare
    cf_connecting_ip: Optional[str] = Header(None),
    # sent to our server from the osu! client
    user_agent: Literal["osu!"] = Header(...),
    host: str = Header(None),
):
    if cf_connecting_ip is not None:
        ip_str = cf_connecting_ip
    else:
        # if the request has been forwarded, get the origin
        forwards = x_forwarded_for.split(",")
        if len(forwards) != 1:
            ip_str = forwards[0]
        else:
            ip_str = x_real_ip

    if ip_str in glob.cache["ip"]:
        ip = glob.cache["ip"][ip_str]
    else:
        ip = ipaddress.ip_address(ip_str)
        glob.cache["ip"][ip_str] = ip

    if user_agent != "osu!":
        url = f"{request.method} {host}{request['path']}"
        log(f"[{ip}] {url} missing user-agent.", Ansi.LRED)
        return

    # check for 'osu-token' in the headers.
    # if it's not there, this is a login request.

    if "osu-token" not in request.headers:
        # login is a bit of a special case,
        # so we'll handle it separately.
        async with glob.players._lock:
            async with app.services.database_session() as db_conn:
                login_data = await login(await request.body(), ip, db_conn)

        if login_data is None:
            # invalid login; failed.
            return

        token, body = login_data

        response.headers["cho-token"] = token
        return body

    # get the player from the specified osu token.
    player = glob.players.get(token=request.headers["osu-token"])

    if not player:
        # token not found; chances are that we just restarted
        # the server - tell their client to reconnect immediately.
        return packets.notification("Server has restarted.") + packets.restart_server(
            0,
        )  # send 0ms since server is up

    # restricted users may only use certain packet handlers.
    if not player.restricted:
        packet_map = glob.bancho_packets["all"]
    else:
        packet_map = glob.bancho_packets["restricted"]

    # bancho connections can be comprised of multiple packets;
    # our reader is designed to iterate through them individually,
    # allowing logic to be implemented around the actual handler.
    # NOTE: any unhandled packets will be ignored internally.

    packets_handled = []

    with memoryview(await request.body()) as body_view:
        for packet in BanchoPacketReader(body_view, packet_map):
            await packet.handle(player)
            packets_handled.append(packet.__class__.__name__)

        if glob.app.debug:
            packets_str = ", ".join(packets_handled) or "None"
            log(f"[BANCHO] {player} | {packets_str}.", RGB(0xFF68AB))

    player.last_recv_time = time.time()

    response.headers["Content-Type"] = "text/html; charset=UTF-8"
    return player.dequeue()


""" Packet logic """

# restricted users are able to
# access many less packet handlers.
glob.bancho_packets = {"all": {}, "restricted": {}}


def register(
    packet: ClientPackets,
    restricted: bool = False,
) -> Callable[[Type[BasePacket]], Type[BasePacket]]:
    """Register a handler in `glob.bancho_packets`."""

    def wrapper(cls: Type[BasePacket]) -> Type[BasePacket]:
        glob.bancho_packets["all"][packet] = cls

        if restricted:
            glob.bancho_packets["restricted"][packet] = cls

        return cls

    return wrapper


@register(ClientPackets.PING, restricted=True)
class Ping(BasePacket):
    async def handle(self, p: Player) -> None:
        pass  # ping be like


@register(ClientPackets.CHANGE_ACTION, restricted=True)
class ChangeAction(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.action = reader.read_u8()
        self.info_text = reader.read_string()
        self.map_md5 = reader.read_string()
        self.mods = reader.read_u32()
        self.mode = reader.read_u8()
        self.map_id = reader.read_i32()

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
        if not p.restricted:
            glob.players.enqueue(packets.user_stats(p))


IGNORED_CHANNELS = ["#highlight", "#userlog"]


@register(ClientPackets.SEND_PUBLIC_MESSAGE)
class SendMessage(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.msg = reader.read_message()

    async def handle(self, p: Player) -> None:
        if p.silenced:
            log(f"{p} sent a message while silenced.", Ansi.LYELLOW)
            return

        # remove leading/trailing whitespace
        msg = self.msg.text.strip()

        if not msg:
            return

        recipient = self.msg.recipient

        if recipient in IGNORED_CHANNELS:
            return
        elif recipient == "#spectator":
            if p.spectating:
                # we are spectating someone
                spec_id = p.spectating.id
            elif p.spectators:
                # we are being spectated
                spec_id = p.id
            else:
                return

            t_chan = glob.channels[f"#spec_{spec_id}"]
        elif recipient == "#multiplayer":
            if not p.match:
                # they're not in a match?
                return

            t_chan = p.match.chat
        else:
            t_chan = glob.channels[recipient]

        if not t_chan:
            log(f"{p} wrote to non-existent {recipient}.", Ansi.LYELLOW)
            return

        if p not in t_chan:
            log(f"{p} wrote to {recipient} without being in it.")
            return

        if not t_chan.can_write(p.priv):
            log(f"{p} wrote to {recipient} with insufficient privileges.")
            return

        # limit message length to 2k chars
        # perhaps this could be dangerous with !py..?
        if len(msg) > 2000:
            msg = f"{msg[:2000]}... (truncated)"
            p.enqueue(
                packets.notification(
                    "Your message was truncated\n" "(exceeded 2000 characters).",
                ),
            )

        if msg.startswith(glob.config.command_prefix):
            cmd = await commands.process_commands(p, t_chan, msg)
        else:
            cmd = None

        if cmd:
            # a command was triggered.
            if not cmd["hidden"]:
                t_chan.send(msg, sender=p)
                if cmd["resp"] is not None:
                    t_chan.send_bot(cmd["resp"])
            else:
                staff = glob.players.staff
                t_chan.send_selective(msg=msg, sender=p, recipients=staff - {p})
                if cmd["resp"] is not None:
                    t_chan.send_selective(
                        msg=cmd["resp"],
                        sender=glob.bot,
                        recipients=staff | {p},
                    )

        else:
            # no commands were triggered

            # check if the user is /np'ing a map.
            # even though this is a public channel,
            # we'll update the player's last np stored.
            if r_match := regexes.NOW_PLAYING.match(msg):
                # the player is /np'ing a map.
                # save it to their player instance
                # so we can use this elsewhere owo..
                bmap = await Beatmap.from_bid(int(r_match["bid"]))

                if bmap:
                    # parse mode_vn int from regex
                    if r_match["mode_vn"] is not None:
                        mode_vn = {"Taiko": 1, "CatchTheBeat": 2, "osu!mania": 3}[
                            r_match["mode_vn"]
                        ]
                    else:
                        # use player mode if not specified
                        mode_vn = p.status.mode.as_vanilla

                    p.last_np = {
                        "bmap": bmap,
                        "mode_vn": mode_vn,
                        "timeout": time.time() + 300,  # /np's last 5mins
                    }
                else:
                    # time out their previous /np
                    p.last_np["timeout"] = 0.0

            t_chan.send(msg, sender=p)

        p.update_latest_activity()
        log(f"{p} @ {t_chan}: {msg}", Ansi.LCYAN, file=".data/logs/chat.log")


@register(ClientPackets.LOGOUT, restricted=True)
class Logout(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        reader.read_i32()  # reserved

    async def handle(self, p: Player) -> None:
        if (time.time() - p.login_time) < 1:
            # osu! has a weird tendency to log out immediately after login.
            # i've tested the times and they're generally 300-800ms, so
            # we'll block any logout request within 1 second from login.
            return

        p.logout()

        p.update_latest_activity()


@register(ClientPackets.REQUEST_STATUS_UPDATE, restricted=True)
class StatsUpdateRequest(BasePacket):
    async def handle(self, p: Player) -> None:
        p.enqueue(packets.user_stats(p))


# Some messages to send on welcome/restricted/etc.
# TODO: these should probably be moved to the config.
WELCOME_MSG = "\n".join(
    (
        f"Welcome to {BASE_DOMAIN}.",
        "To see a list of commands, use !help.",
        "We have a public (Discord)[https://discord.gg/ShEQgUx]!",
        "Enjoy the server!",
    ),
)

RESTRICTED_MSG = (
    "Your account is currently in restricted mode. "
    "If you believe this is a mistake, or have waited a period "
    "greater than 3 months, you may appeal via the form on the site."
)

WELCOME_NOTIFICATION = packets.notification(
    f"Welcome back to {BASE_DOMAIN}!\n",  # f"Running gulag v{glob.version}.",
)

OFFLINE_NOTIFICATION = packets.notification(
    "The server is currently running in offline mode; "
    "some features will be unavailble.",
)

DELTA_90_DAYS = timedelta(days=90)


async def login(
    body: bytes,
    ip: IPAddress,
    db_conn: sqlalchemy.ext.asyncio.AsyncSession,
) -> Optional[tuple[str, bytes]]:
    """\
    Login has no specific packet, but happens when the osu!
    client sends a request without an 'osu-token' header.

    Some notes:
      this must be called with glob.players._lock held.
      we return a tuple of (response_bytes, user_token) on success.

    Request format:
      username\npasswd_md5\nosu_ver|utc_offset|display_city|client_hashes|pm_private\n

    Response format:
      Packet 5 (userid), with ID:
      -1: authentication failed
      -2: old client
      -3: banned
      -4: banned
      -5: error occurred
      -6: needs supporter
      -7: password reset
      -8: requires verification
      other: valid id, logged in
    """

    """ Parse data and verify the request is legitimate. """
    if len(split := body.decode().split("\n")[:-1]) != 3:
        log(f"Invalid login request from {ip}.", Ansi.LRED)
        return  # invalid request

    username = split[0]
    pw_md5 = split[1].encode()

    if len(client_info := split[2].split("|")) != 5:
        return  # invalid request

    osu_ver_str = client_info[0]

    if not (r_match := regexes.OSU_VERSION.match(osu_ver_str)):
        return  # invalid request

    # quite a bit faster than using dt.strptime.
    osu_ver_date = date(
        year=int(r_match["ver"][0:4]),
        month=int(r_match["ver"][4:6]),
        day=int(r_match["ver"][6:8]),
    )

    osu_ver_stream = r_match["stream"] or "stable"
    using_tourney_client = osu_ver_stream == "tourney"

    # disallow the login if their osu! client is older
    # than three months old, forcing an update re-check.
    # NOTE: this is disabled on debug since older clients
    #       can sometimes be quite useful when testing.
    if not glob.app.debug:
        # this is currently slow, but asottile is on the
        # case https://bugs.python.org/issue44307 :D
        if osu_ver_date < (date.today() - DELTA_90_DAYS):
            return "no", packets.version_update_forced() + packets.user_id(-2)

    # ensure utc_offset is a number (negative inclusive).
    if not client_info[1].replace("-", "").isdecimal():
        return  # invalid request

    utc_offset = int(client_info[1])
    # display_city = client_info[2] == '1'

    client_hashes = client_info[3][:-1].split(":")
    if len(client_hashes) != 5:
        return

    # TODO: should these be stored in player object?
    (
        osu_path_md5,
        adapters_str,
        adapters_md5,
        uninstall_md5,
        disk_sig_md5,
    ) = client_hashes

    is_wine = adapters_str == "runningunderwine"
    adapters = [a for a in adapters_str[:-1].split(".") if a]

    if not (is_wine or adapters):
        data = packets.user_id(-1) + packets.notification(
            "Please restart your osu! and try again.",
        )
        return "no", data

    pm_private = client_info[4] == "1"

    """ Parsing complete, now check the given data. """

    login_time = time.time()

    # TODO: improve tourney client support, this is not great.
    if not using_tourney_client:
        # Check if the player is already online
        if p := glob.players.get(name=username):
            # player is online, only allow multiple
            # logins if they're on a tourney client.
            if not p.tourney_client:
                if (login_time - p.last_recv_time) > 10:
                    # if the current player obj online hasn't
                    # pinged the server in > 10 seconds, log
                    # them out and login the new user.
                    p.logout()
                else:
                    # the user is currently online, send back failure.
                    data = packets.user_id(-1) + packets.notification(
                        "User already logged in.",
                    )

                    return "no", data

    user_info = await db_conn.fetch_one(
        "SELECT id, name, priv, pw_bcrypt, country, "
        "silence_end, clan_id, clan_priv, api_key "
        "FROM users WHERE safe_name = :username",
        {"username": app.misc.utils.make_safe_name(username)},
    )

    # make user_info mutable
    # TODO: fix this hackery
    user_info = dict(user_info)  # type: ignore

    if not user_info:
        # no account by this name exists.
        return "no", (
            packets.notification(f"{BASE_DOMAIN}: Unknown username")
            + packets.user_id(-1)
        )

    if using_tourney_client and not (
        user_info["priv"] & Privileges.DONATOR and user_info["priv"] & Privileges.NORMAL
    ):
        # trying to use tourney client with insufficient privileges.
        return "no", packets.user_id(-1)

    # get our bcrypt cache.
    bcrypt_cache = glob.cache["bcrypt"]
    pw_bcrypt = user_info["pw_bcrypt"].encode()
    user_info["pw_bcrypt"] = pw_bcrypt

    # check credentials against db. algorithms like these are intentionally
    # designed to be slow; we'll cache the results to speed up subsequent logins.
    if pw_bcrypt in bcrypt_cache:  # ~0.01 ms
        if pw_md5 != bcrypt_cache[pw_bcrypt]:
            return "no", (
                packets.notification(f"{BASE_DOMAIN}: Incorrect password")
                + packets.user_id(-1)
            )
    else:  # ~200ms
        if not bcrypt.checkpw(pw_md5, pw_bcrypt):
            return "no", (
                packets.notification(f"{BASE_DOMAIN}: Incorrect password")
                + packets.user_id(-1)
            )

        bcrypt_cache[pw_bcrypt] = pw_md5

    """ login credentials verified """

    await db_conn.execute(
        "INSERT INTO ingame_logins "
        "(userid, ip, osu_ver, osu_stream, datetime) "
        "VALUES (:userid, :ip, :osu_ver, :osu_stream, NOW())",
        {
            "userid": user_info["id"],
            "ip": str(ip),
            "osu_ver": osu_ver_date,
            "osu_stream": osu_ver_stream,
        },
    )

    await db_conn.execute(
        "INSERT INTO client_hashes "
        "(userid, osupath, adapters, uninstall_id,"
        " disk_serial, latest_time, occurrences) "
        "VALUES (:userid, :osupath, :adapters, :uninstall, :disk, NOW(), 1) "
        "ON DUPLICATE KEY UPDATE "
        "occurrences = occurrences + 1, "
        "latest_time = NOW() ",
        {
            "userid": user_info["id"],
            "osupath": osu_path_md5,
            "adapters": adapters_md5,
            "uninstall": uninstall_md5,
            "disk": disk_sig_md5,
        },
    )

    # TODO: store adapters individually

    if is_wine:
        hw_checks = "h.uninstall_id = :uninstall"
        hw_args = {"uninstall": uninstall_md5}
    else:
        hw_checks = "h.adapters = :adapters OR h.uninstall_id = :uninstall OR h.disk_serial = :disk"
        hw_args = {
            "adapters": adapters_md5,
            "uninstall": uninstall_md5,
            "disk": disk_sig_md5,
        }

    hw_matches = await db_conn.fetch_all(
        "SELECT u.name, u.priv, h.occurrences "
        "FROM client_hashes h "
        "INNER JOIN users u ON h.userid = u.id "
        "WHERE h.userid != %s AND "
        f"({hw_checks})",
        hw_args | {"userid": user_info["id"]},
    )

    if hw_matches:
        # we have other accounts with matching hashes
        if user_info["priv"] & Privileges.VERIFIED:
            # TODO: this is a normal, registered & verified player.
            ...
        else:
            # this player is not verified yet, this is their first
            # time connecting in-game and submitting their hwid set.
            # we will not allow any banned matches; if there are any,
            # then ask the user to contact staff and resolve manually.
            if not all(
                [hw_match["priv"] & Privileges.NORMAL for hw_match in hw_matches],
            ):
                return "no", (
                    packets.notification(
                        "Please contact staff directly to create an account.",
                    )
                    + packets.user_id(-1)
                )

    """ All checks passed, player is safe to login """

    # get clan & clan priv if we're in a clan
    if user_info["clan_id"] != 0:
        clan = glob.clans.get(id=user_info.pop("clan_id"))
        clan_priv = ClanPrivileges(user_info.pop("clan_priv"))
    else:
        del user_info["clan_id"]
        del user_info["clan_priv"]
        clan = clan_priv = None

    db_country = user_info.pop("country")

    if not ip.is_private:
        if glob.geoloc_db is not None:
            # good, dev has downloaded a geoloc db from maxmind,
            # so we can do a local db lookup. (typically ~1-5ms)
            # https://www.maxmind.com/en/home
            user_info["geoloc"] = app.services.fetch_geoloc_db(ip)
        else:
            # bad, we must do an external db lookup using
            # a public api. (depends, `ping ip-api.com`)
            user_info["geoloc"] = await app.services.fetch_geoloc_web(ip)

        if db_country == "xx":
            # bugfix for old gulag versions when
            # country wasn't stored on registration.
            log(f"Fixing {username}'s country.", Ansi.LGREEN)

            await db_conn.execute(
                "UPDATE users SET country = :country WHERE id = :userid",
                {
                    "country": user_info["geoloc"]["country"]["acronym"],
                    "userid": user_info["id"],
                },
            )

    p = Player(
        **user_info,  # {id, name, priv, pw_bcrypt, silence_end, api_key, geoloc?}
        utc_offset=utc_offset,
        osu_ver=osu_ver_date,
        pm_private=pm_private,
        login_time=login_time,
        clan=clan,
        clan_priv=clan_priv,
        tourney_client=using_tourney_client,
    )

    data = bytearray(packets.protocol_version(19))
    data += packets.user_id(p.id)

    # *real* client privileges are sent with this packet,
    # then the user's apparent privileges are sent in the
    # userPresence packets to other players. we'll send
    # supporter along with the user's privileges here,
    # but not in userPresence (so that only donators
    # show up with the yellow name in-game, but everyone
    # gets osu!direct & other in-game perks).
    data += packets.bancho_privileges(p.bancho_priv | ClientPrivileges.SUPPORTER)

    data += WELCOME_NOTIFICATION

    # send all appropriate channel info to our player.
    # the osu! client will attempt to join the channels.
    for c in glob.channels:
        if (
            not c.auto_join
            or not c.can_read(p.priv)
            or c._name == "#lobby"  # (can't be in mp lobby @ login)
        ):
            continue

        # send chan info to all players who can see
        # the channel (to update their playercounts)
        chan_info_packet = packets.channel_info(c._name, c.topic, len(c.players))

        data += chan_info_packet

        for o in glob.players:
            if c.can_read(o.priv):
                o.enqueue(chan_info_packet)

    # tells osu! to reorder channels based on config.
    data += packets.channel_info_end()

    # fetch some of the player's
    # information from sql to be cached.
    await p.achievements_from_sql(db_conn)
    await p.stats_from_sql_full(db_conn)
    await p.relationships_from_sql(db_conn)

    # TODO: fetch p.recent_scores from sql

    data += packets.main_menu_icon()
    data += packets.friends_list(*p.friends)
    data += packets.silence_end(p.remaining_silence)

    # update our new player's stats, and broadcast them.
    user_data = packets.user_presence(p) + packets.user_stats(p)

    data += user_data

    if not p.restricted:
        # player is unrestricted, two way data
        for o in glob.players:
            # enqueue us to them
            o.enqueue(user_data)

            # enqueue them to us.
            if not o.restricted:
                data += packets.user_presence(o)
                data += packets.user_stats(o)

        # the player may have been sent mail while offline,
        # enqueue any messages from their respective authors.
        mail_sent_to = set()  # ids

        async for msg in db_conn.iterate(
            "SELECT m.`msg`, m.`time`, m.`from_id`, "
            "(SELECT name FROM users WHERE id = m.`from_id`) AS `from`, "
            "(SELECT name FROM users WHERE id = m.`to_id`) AS `to` "
            "FROM `mail` m WHERE m.`to_id` = :userid AND m.`read` = 0",
            {"userid": p.id},
        ):
            if msg["from"] not in mail_sent_to:
                data += packets.send_message(
                    sender=msg["from"],
                    msg="Unread messages",
                    recipient=msg["to"],
                    sender_id=msg["from_id"],
                )
                mail_sent_to.add(msg["from"])

            msg_time = datetime.fromtimestamp(msg["time"])
            msg_ts = f'[{msg_time:%a %b %d @ %H:%M%p}] {msg["msg"]}'

            data += packets.send_message(
                sender=msg["from"],
                msg=msg_ts,
                recipient=msg["to"],
                sender_id=msg["from_id"],
            )

        if not p.priv & Privileges.VERIFIED:
            # this is the player's first login, verify their
            # account & send info about the server/its usage.
            await p.add_privs(Privileges.VERIFIED)

            if p.id == 3:
                # this is the first player registering on
                # the server, grant them full privileges.
                await p.add_privs(
                    Privileges.STAFF
                    | Privileges.NOMINATOR
                    | Privileges.WHITELISTED
                    | Privileges.TOURNAMENT
                    | Privileges.DONATOR
                    | Privileges.ALUMNI,
                )

            data += packets.send_message(
                sender=glob.bot.name,
                msg=WELCOME_MSG,
                recipient=p.name,
                sender_id=glob.bot.id,
            )

    else:
        # player is restricted, one way data
        for o in glob.players.unrestricted:
            # enqueue them to us.
            data += packets.user_presence(o)
            data += packets.user_stats(o)

        data += packets.account_restricted()
        data += packets.send_message(
            sender=glob.bot.name,
            msg=RESTRICTED_MSG,
            recipient=p.name,
            sender_id=glob.bot.id,
        )

    # TODO: some sort of admin panel for staff members?

    # add `p` to the global player list,
    # making them officially logged in.
    glob.players.append(p)

    if glob.datadog:
        if not p.restricted:
            glob.datadog.increment("gulag.online_players")

        time_taken = time.time() - login_time
        glob.datadog.histogram("gulag.login_time", time_taken)

    user_os = "unix (wine)" if is_wine else "win32"
    country_code = p.geoloc["country"]["acronym"].upper()

    log(
        f"{p} logged in from {country_code} using {osu_ver_str} on {user_os}",
        Ansi.LCYAN,
    )

    p.update_latest_activity()
    return p.token, bytes(data)


@register(ClientPackets.START_SPECTATING)
class StartSpectating(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.target_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not (new_host := glob.players.get(id=self.target_id)):
            log(f"{p} tried to spectate nonexistant id {self.target_id}.", Ansi.LYELLOW)
            return

        if current_host := p.spectating:
            if current_host == new_host:
                # host hasn't changed, they didn't have
                # the map but have downloaded it.

                if not p.stealth:
                    # NOTE: `p` would have already received the other
                    # fellow spectators, so no need to resend them.
                    new_host.enqueue(packets.spectator_joined(p.id))

                    p_joined = packets.fellow_spectator_joined(p.id)
                    for spec in new_host.spectators:
                        if spec is not p:
                            spec.enqueue(p_joined)

                return

            current_host.remove_spectator(p)

        new_host.add_spectator(p)


@register(ClientPackets.STOP_SPECTATING)
class StopSpectating(BasePacket):
    async def handle(self, p: Player) -> None:
        host = p.spectating

        if not host:
            log(f"{p} tried to stop spectating when they're not..?", Ansi.LRED)
            return

        host.remove_spectator(p)


@register(ClientPackets.SPECTATE_FRAMES)
class SpectateFrames(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.frame_bundle = reader.read_replayframe_bundle()

    async def handle(self, p: Player) -> None:
        # packing this manually is about ~3x faster
        # data = packets.spectateFrames(self.frame_bundle.raw_data)
        data = (
            struct.pack("<HxI", 15, len(self.frame_bundle.raw_data))
            + self.frame_bundle.raw_data
        )

        # enqueue the data
        # to all spectators.
        for t in p.spectators:
            t.enqueue(data)


@register(ClientPackets.CANT_SPECTATE)
class CantSpectate(BasePacket):
    async def handle(self, p: Player) -> None:
        if not p.spectating:
            log(f"{p} sent can't spectate while not spectating?", Ansi.LRED)
            return

        if not p.stealth:
            data = packets.spectator_cant_spectate(p.id)

            host = p.spectating
            host.enqueue(data)

            for t in host.spectators:
                t.enqueue(data)


@register(ClientPackets.SEND_PRIVATE_MESSAGE)
class SendPrivateMessage(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.msg = reader.read_message()

    async def handle(self, p: Player) -> None:
        if p.silenced:
            if glob.app.debug:
                log(f"{p} tried to send a dm while silenced.", Ansi.LYELLOW)
            return

        # remove leading/trailing whitespace
        msg = self.msg.text.strip()

        if not msg:
            return

        t_name = self.msg.recipient

        # allow this to get from sql - players can receive
        # messages offline, due to the mail system. B)
        if not (t := await glob.players.from_cache_or_sql(name=t_name)):
            if glob.app.debug:
                log(f"{p} tried to write to non-existent user {t_name}.", Ansi.LYELLOW)
            return

        if p.id in t.blocks:
            p.enqueue(packets.user_dm_blocked(t_name))

            if glob.app.debug:
                log(f"{p} tried to message {t}, but they have them blocked.")
            return

        if t.pm_private and p.id not in t.friends:
            p.enqueue(packets.user_dm_blocked(t_name))

            if glob.app.debug:
                log(f"{p} tried to message {t}, but they are blocking dms.")
            return

        if t.silenced:
            # if target is silenced, inform player.
            p.enqueue(packets.target_silenced(t_name))

            if glob.app.debug:
                log(f"{p} tried to message {t}, but they are silenced.")
            return

        # limit message length to 2k chars
        # perhaps this could be dangerous with !py..?
        if len(msg) > 2000:
            msg = f"{msg[:2000]}... (truncated)"
            p.enqueue(
                packets.notification(
                    "Your message was truncated\n" "(exceeded 2000 characters).",
                ),
            )

        if t.status.action == Action.Afk and t.away_msg:
            # send away message if target is afk and has one set.
            p.send(t.away_msg, sender=t)

        if t is not glob.bot:
            # target is not bot, send the message normally if online
            if t.online:
                t.send(msg, sender=p)
            else:
                # inform user they're offline, but
                # will receive the mail @ next login.
                p.enqueue(
                    packets.notification(
                        f"{t.name} is currently offline, but will "
                        "receive your messsage on their next login.",
                    ),
                )

            # insert mail into db, marked as unread.
            await app.services.database.execute(
                "INSERT INTO `mail` "
                "(`from_id`, `to_id`, `msg`, `time`) "
                "VALUES (:from, :to, :msg, UNIX_TIMESTAMP())",
                {"from": p.id, "to": t.id, "msg": msg},
            )
        else:
            # messaging the bot, check for commands & /np.
            if msg.startswith(glob.config.command_prefix):
                cmd = await commands.process_commands(p, t, msg)
            else:
                cmd = None

            if cmd:
                # command triggered, send response if any.
                if cmd["resp"] is not None:
                    p.send(cmd["resp"], sender=t)
            else:
                # no commands triggered.
                if r_match := regexes.NOW_PLAYING.match(msg):
                    # user is /np'ing a map.
                    # save it to their player instance
                    # so we can use this elsewhere owo..
                    bmap = await Beatmap.from_bid(int(r_match["bid"]))

                    if bmap:
                        # parse mode_vn int from regex
                        if r_match["mode_vn"] is not None:
                            mode_vn = {"Taiko": 1, "CatchTheBeat": 2, "osu!mania": 3}[
                                r_match["mode_vn"]
                            ]
                        else:
                            # use player mode if not specified
                            mode_vn = p.status.mode.as_vanilla

                        p.last_np = {
                            "bmap": bmap,
                            "mode_vn": mode_vn,
                            "timeout": time.time() + 300,  # /np's last 5mins
                        }

                        # calculate generic pp values from their /np

                        osu_file_path = BEATMAPS_PATH / f"{bmap.id}.osu"
                        if not await ensure_local_osu_file(
                            osu_file_path,
                            bmap.id,
                            bmap.md5,
                        ):
                            resp_msg = (
                                "Mapfile could not be found; "
                                "this incident has been reported."
                            )
                        else:
                            # calculate pp for common generic values
                            pp_calc_st = time.time_ns()

                            if mode_vn in (0, 1, 2):  # osu, taiko, catch
                                if r_match["mods"] is not None:
                                    # [1:] to remove leading whitespace
                                    mods_str = r_match["mods"][1:]
                                    mods = Mods.from_np(mods_str, mode_vn)
                                else:
                                    mods = None

                                pp_values = []  # [(acc, pp), ...]

                                if mode_vn == 0:
                                    with OppaiWrapper("oppai-ng/liboppai.so") as ezpp:
                                        if mods is not None:
                                            ezpp.set_mods(int(mods))

                                        for acc in glob.config.pp_cached_accs:
                                            ezpp.set_accuracy_percent(acc)

                                            ezpp.calculate(osu_file_path)

                                            pp_values.append((acc, ezpp.get_pp()))
                                else:
                                    beatmap = PeaceMap(osu_file_path)
                                    peace = PeaceCalculator()

                                    if mods is not None:
                                        peace.set_mods(int(mods))

                                    peace.set_mode(mode_vn)

                                    for acc in glob.config.pp_cached_accs:
                                        peace.set_acc(acc)

                                        calc = peace.calculate(beatmap)

                                        pp_values.append((acc, calc.pp))

                                resp_msg = " | ".join(
                                    [f"{acc}%: {pp:,.2f}pp" for acc, pp in pp_values],
                                )
                            else:  # mania
                                if r_match["mods"] is not None:
                                    # [1:] to remove leading whitespace
                                    mods_str = r_match["mods"][1:]
                                    mods = Mods.from_np(mods_str, mode_vn)
                                else:
                                    mods = None

                                beatmap = PeaceMap(osu_file_path)
                                peace = PeaceCalculator()

                                if mods is not None:
                                    peace.set_mods(int(mods))

                                peace.set_mode(mode_vn)

                                pp_values = []

                                for score in glob.config.pp_cached_scores:
                                    peace.set_score(int(score))

                                    calc = peace.calculate(beatmap)

                                    pp_values.append((score, calc.pp))

                                resp_msg = " | ".join(
                                    [
                                        f"{int(score // 1000)}k: {pp:,.2f}pp"
                                        for score, pp in pp_values
                                    ],
                                )

                            elapsed = time.time_ns() - pp_calc_st
                            resp_msg += f" | Elapsed: {magnitude_fmt_time(elapsed)}"
                    else:
                        resp_msg = "Could not find map."

                        # time out their previous /np
                        p.last_np["timeout"] = 0.0

                    p.send(resp_msg, sender=t)

        p.update_latest_activity()
        log(f"{p} @ {t}: {msg}", Ansi.LCYAN, file=".data/logs/chat.log")


@register(ClientPackets.PART_LOBBY)
class LobbyPart(BasePacket):
    async def handle(self, p: Player) -> None:
        p.in_lobby = False


@register(ClientPackets.JOIN_LOBBY)
class LobbyJoin(BasePacket):
    async def handle(self, p: Player) -> None:
        p.in_lobby = True

        for m in glob.matches:
            if m is not None:
                p.enqueue(packets.new_match(m))


@register(ClientPackets.CREATE_MATCH)
class MatchCreate(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match = reader.read_match()

    async def handle(self, p: Player) -> None:
        # TODO: match validation..?
        if p.restricted:
            p.enqueue(
                packets.match_join_fail()
                + packets.notification(
                    "Multiplayer is not available while restricted.",
                ),
            )
            return

        if p.silenced:
            p.enqueue(
                packets.match_join_fail()
                + packets.notification("Multiplayer is not available while silenced."),
            )
            return

        if not glob.matches.append(self.match):
            # failed to create match (match slots full).
            p.send_bot("Failed to create match (no slots available).")
            p.enqueue(packets.match_join_fail())
            return

        # create the channel and add it
        # to the global channel list as
        # an instanced channel.
        chan = Channel(
            name=f"#multi_{self.match.id}",
            topic=f"MID {self.match.id}'s multiplayer channel.",
            auto_join=False,
            instance=True,
        )

        glob.channels.append(chan)
        self.match.chat = chan

        p.update_latest_activity()
        p.join_match(self.match, self.match.passwd)

        self.match.chat.send_bot(f"Match created by {p.name}.")
        log(f"{p} created a new multiplayer match.")


async def execute_menu_option(p: Player, key: int) -> None:
    if key not in p.current_menu.options:
        return

    # this is one of their menu options, execute it.
    cmd, data = p.current_menu.options[key]

    if glob.config.debug:
        print(f"\x1b[0;95m{cmd!r}\x1b[0m {data}")

    if cmd == MenuCommands.Reset:
        # go back to the main menu
        p.current_menu = p.previous_menus[0]
        p.previous_menus.clear()
    elif cmd == MenuCommands.Back:
        # return one menu back
        p.current_menu = p.previous_menus.pop()
        p.send_current_menu()
    elif cmd == MenuCommands.Advance:
        # advance to a new menu
        assert isinstance(data, Menu)
        p.previous_menus.append(p.current_menu)
        p.current_menu = data
        p.send_current_menu()
    elif cmd == MenuCommands.Execute:
        # execute a function on the current menu
        assert isinstance(data, MenuFunction)
        await data.callback(p)


@register(ClientPackets.JOIN_MATCH)
class MatchJoin(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match_id = reader.read_i32()
        self.match_passwd = reader.read_string()

    async def handle(self, p: Player) -> None:
        is_menu_request = self.match_id >= glob.config.max_multi_matches

        if is_menu_request or self.match_id < 0:
            if is_menu_request:
                # NOTE: this function is unrelated to mp.
                await execute_menu_option(p, self.match_id)

            p.enqueue(packets.match_join_fail())
            return

        if not (m := glob.matches[self.match_id]):
            log(f"{p} tried to join a non-existant mp lobby?")
            p.enqueue(packets.match_join_fail())
            return

        if p.restricted:
            p.enqueue(
                packets.match_join_fail()
                + packets.notification(
                    "Multiplayer is not available while restricted.",
                ),
            )
            return

        if p.silenced:
            p.enqueue(
                packets.match_join_fail()
                + packets.notification("Multiplayer is not available while silenced."),
            )
            return

        p.update_latest_activity()
        p.join_match(m, self.match_passwd)


@register(ClientPackets.PART_MATCH)
class MatchPart(BasePacket):
    async def handle(self, p: Player) -> None:
        p.update_latest_activity()
        p.leave_match()


@register(ClientPackets.MATCH_CHANGE_SLOT)
class MatchChangeSlot(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.slot_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        # read new slot ID
        if not 0 <= self.slot_id < 16:
            return

        if m.slots[self.slot_id].status != SlotStatus.open:
            log(f"{p} tried to move into non-open slot.", Ansi.LYELLOW)
            return

        # swap with current slot.
        slot = m.get_slot(p)
        assert slot is not None

        m.slots[self.slot_id].copy_from(slot)
        slot.reset()

        m.enqueue_state()  # technically not needed for host?


@register(ClientPackets.MATCH_READY)
class MatchReady(BasePacket):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        slot = m.get_slot(p)
        assert slot is not None

        slot.status = SlotStatus.ready
        m.enqueue_state(lobby=False)


@register(ClientPackets.MATCH_LOCK)
class MatchLock(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.slot_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        if p is not m.host:
            log(f"{p} attempted to lock match as non-host.", Ansi.LYELLOW)
            return

        # read new slot ID
        if not 0 <= self.slot_id < 16:
            return

        slot = m.slots[self.slot_id]

        if slot.status == SlotStatus.locked:
            slot.status = SlotStatus.open
        else:
            if slot.player is m.host:
                # don't allow the match host to kick
                # themselves by clicking their crown
                return

            if slot.player:
                # uggggggh i hate trusting the osu! client
                # man why is it designed like this
                # TODO: probably going to end up changing
                ...  # slot.reset()

            slot.status = SlotStatus.locked

        m.enqueue_state()


@register(ClientPackets.MATCH_CHANGE_SETTINGS)
class MatchChangeSettings(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.new = reader.read_match()

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        if p is not m.host:
            log(f"{p} attempted to change settings as non-host.", Ansi.LYELLOW)
            return

        if self.new.freemods != m.freemods:
            # freemods status has been changed.
            m.freemods = self.new.freemods

            if self.new.freemods:
                # match mods -> active slot mods.
                for s in m.slots:
                    if s.status & SlotStatus.has_player:
                        # the slot takes any non-speed
                        # changing mods from the match.
                        s.mods = m.mods & ~SPEED_CHANGING_MODS

                # keep only speed-changing mods.
                m.mods &= SPEED_CHANGING_MODS
            else:
                # host mods -> match mods.
                host = m.get_host_slot()  # should always exist
                assert host is not None

                # the match keeps any speed-changing mods,
                # and also takes any mods the host has enabled.
                m.mods &= SPEED_CHANGING_MODS
                m.mods |= host.mods

                for s in m.slots:
                    if s.status & SlotStatus.has_player:
                        s.mods = Mods.NOMOD

        if self.new.map_id == -1:
            # map being changed, unready players.
            m.unready_players(expected=SlotStatus.ready)
            m.prev_map_id = m.map_id

            m.map_id = -1
            m.map_md5 = ""
            m.map_name = ""
        elif m.map_id == -1:
            if m.prev_map_id != self.new.map_id:
                # new map has been chosen, send to match chat.
                m.chat.send_bot(f"Selected: {self.new.map_embed}.")

            # use our serverside version if we have it, but
            # still allow for users to pick unknown maps.
            bmap = await Beatmap.from_md5(self.new.map_md5)

            if bmap:
                m.map_id = bmap.id
                m.map_md5 = bmap.md5
                m.map_name = bmap.full
                m.mode = bmap.mode
            else:
                m.map_id = self.new.map_id
                m.map_md5 = self.new.map_md5
                m.map_name = self.new.map_name
                m.mode = self.new.mode

        if m.team_type != self.new.team_type:
            # if theres currently a scrim going on, only allow
            # team type to change by using the !mp teams command.
            if m.is_scrimming:
                _team = ("head-to-head", "tag-coop", "team-vs", "tag-team-vs")[
                    self.new.team_type
                ]

                msg = (
                    "Changing team type while scrimming will reset "
                    "the overall score - to do so, please use the "
                    f"!mp teams {_team} command."
                )
                m.chat.send_bot(msg)
            else:
                # find the new appropriate default team.
                # defaults are (ffa: neutral, teams: red).
                if self.new.team_type in (
                    MatchTeamTypes.head_to_head,
                    MatchTeamTypes.tag_coop,
                ):
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


@register(ClientPackets.MATCH_START)
class MatchStart(BasePacket):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        if p is not m.host:
            log(f"{p} attempted to start match as non-host.", Ansi.LYELLOW)
            return

        m.start()


@register(ClientPackets.MATCH_SCORE_UPDATE)
class MatchScoreUpdate(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.play_data = reader.read_raw()  # TODO: probably not necessary

    async def handle(self, p: Player) -> None:
        # this runs very frequently in matches,
        # so it's written to run pretty quick.

        if not (m := p.match):
            return

        # if scorev2 is enabled, read an extra 8 bytes.
        buf = bytearray(b"0\x00\x00")
        buf += len(self.play_data).to_bytes(4, "little")
        buf += self.play_data
        buf[11] = m.get_slot_id(p)

        m.enqueue(bytes(buf), lobby=False)


@register(ClientPackets.MATCH_COMPLETE)
class MatchComplete(BasePacket):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        slot = m.get_slot(p)
        assert slot is not None

        slot.status = SlotStatus.complete

        # check if there are any players that haven't finished.
        if any([s.status == SlotStatus.playing for s in m.slots]):
            return

        # find any players just sitting in the multi room
        # that have not been playing the map; they don't
        # need to know all the players have completed, only
        # the ones who are playing (just new match info).
        not_playing = [
            s.player.id
            for s in m.slots
            if s.status & SlotStatus.has_player and s.status != SlotStatus.complete
        ]

        was_playing = [
            s for s in m.slots if s.player and s.player.id not in not_playing
        ]

        m.unready_players(expected=SlotStatus.complete)

        m.in_progress = False
        m.enqueue(packets.match_complete(), lobby=False, immune=not_playing)
        m.enqueue_state()

        if m.is_scrimming:
            # determine winner, update match points & inform players.
            asyncio.create_task(m.update_matchpoints(was_playing))


@register(ClientPackets.MATCH_CHANGE_MODS)
class MatchChangeMods(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.mods = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        if m.freemods:
            if p is m.host:
                # allow host to set speed-changing mods.
                m.mods = Mods(self.mods & SPEED_CHANGING_MODS)

            # set slot mods
            slot = m.get_slot(p)
            assert slot is not None

            slot.mods = Mods(self.mods & ~SPEED_CHANGING_MODS)
        else:
            if p is not m.host:
                log(f"{p} attempted to change mods as non-host.", Ansi.LYELLOW)
                return

            # not freemods, set match mods.
            m.mods = Mods(self.mods)

        m.enqueue_state()


def is_playing(slot: Slot) -> bool:
    return slot.status == SlotStatus.playing and not slot.loaded


@register(ClientPackets.MATCH_LOAD_COMPLETE)
class MatchLoadComplete(BasePacket):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        # our player has loaded in and is ready to play.
        slot = m.get_slot(p)
        assert slot is not None

        slot.loaded = True

        # check if all players are loaded,
        # if so, tell all players to begin.
        if not any(map(is_playing, m.slots)):
            m.enqueue(packets.match_all_players_loaded(), lobby=False)


@register(ClientPackets.MATCH_NO_BEATMAP)
class MatchNoBeatmap(BasePacket):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        slot = m.get_slot(p)
        assert slot is not None

        slot.status = SlotStatus.no_map
        m.enqueue_state(lobby=False)


@register(ClientPackets.MATCH_NOT_READY)
class MatchNotReady(BasePacket):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        slot = m.get_slot(p)
        assert slot is not None

        slot.status = SlotStatus.not_ready
        m.enqueue_state(lobby=False)


@register(ClientPackets.MATCH_FAILED)
class MatchFailed(BasePacket):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        # find the player's slot id, and enqueue that
        # they've failed to all other players in the match.
        slot_id = m.get_slot_id(p)
        assert slot_id is not None

        m.enqueue(packets.match_player_failed(slot_id), lobby=False)


@register(ClientPackets.MATCH_HAS_BEATMAP)
class MatchHasBeatmap(BasePacket):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        slot = m.get_slot(p)
        assert slot is not None

        slot.status = SlotStatus.not_ready
        m.enqueue_state(lobby=False)


@register(ClientPackets.MATCH_SKIP_REQUEST)
class MatchSkipRequest(BasePacket):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        slot = m.get_slot(p)
        assert slot is not None

        slot.skipped = True
        m.enqueue(packets.match_player_skipped(p.id))

        for slot in m.slots:
            if slot.status == SlotStatus.playing and not slot.skipped:
                return

        # all users have skipped, enqueue a skip.
        m.enqueue(packets.match_skip(), lobby=False)


@register(ClientPackets.CHANNEL_JOIN, restricted=True)
class ChannelJoin(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.name = reader.read_string()

    async def handle(self, p: Player) -> None:
        if self.name in IGNORED_CHANNELS:
            return

        c = glob.channels[self.name]

        if not c or not p.join_channel(c):
            log(f"{p} failed to join {self.name}.", Ansi.LYELLOW)
            return


@register(ClientPackets.MATCH_TRANSFER_HOST)
class MatchTransferHost(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.slot_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        if p is not m.host:
            log(f"{p} attempted to transfer host as non-host.", Ansi.LYELLOW)
            return

        # read new slot ID
        if not 0 <= self.slot_id < 16:
            return

        if not (t := m[self.slot_id].player):
            log(f"{p} tried to transfer host to an empty slot?")
            return

        m.host = t
        m.host.enqueue(packets.match_transfer_host())
        m.enqueue_state()


@register(ClientPackets.TOURNAMENT_MATCH_INFO_REQUEST)
class TourneyMatchInfoRequest(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not 0 <= self.match_id < 64:
            return  # invalid match id

        if not p.priv & Privileges.DONATOR:
            return  # insufficient privs

        if not (m := glob.matches[self.match_id]):
            return  # match not found

        p.enqueue(packets.update_match(m, send_pw=False))


@register(ClientPackets.TOURNAMENT_JOIN_MATCH_CHANNEL)
class TourneyMatchJoinChannel(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not 0 <= self.match_id < 64:
            return  # invalid match id

        if not p.priv & Privileges.DONATOR:
            return  # insufficient privs

        if not (m := glob.matches[self.match_id]):
            return  # match not found

        for s in m.slots:
            if s.player is not None:
                if p.id == s.player.id:
                    return  # playing in the match

        # attempt to join match chan
        if p.join_channel(m.chat):
            m.tourney_clients.add(p.id)


@register(ClientPackets.TOURNAMENT_LEAVE_MATCH_CHANNEL)
class TourneyMatchLeaveChannel(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not 0 <= self.match_id < 64:
            return  # invalid match id

        if not p.priv & Privileges.DONATOR:
            return  # insufficient privs

        if not (m := glob.matches[self.match_id]):
            return  # match not found

        # attempt to join match chan
        p.leave_channel(m.chat)
        m.tourney_clients.remove(p.id)


@register(ClientPackets.FRIEND_ADD)
class FriendAdd(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.user_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not (t := glob.players.get(id=self.user_id)):
            log(f"{p} tried to add a user who is not online! ({self.user_id})")
            return

        if t is glob.bot:
            return

        if t.id in p.blocks:
            p.blocks.remove(t.id)

        p.update_latest_activity()
        await p.add_friend(t)


@register(ClientPackets.FRIEND_REMOVE)
class FriendRemove(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.user_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not (t := glob.players.get(id=self.user_id)):
            log(f"{p} tried to remove a user who is not online! ({self.user_id})")
            return

        if t is glob.bot:
            return

        p.update_latest_activity()
        await p.remove_friend(t)


@register(ClientPackets.MATCH_CHANGE_TEAM)
class MatchChangeTeam(BasePacket):
    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        # toggle team
        slot = m.get_slot(p)
        assert slot is not None

        if slot.team == MatchTeams.blue:
            slot.team = MatchTeams.red
        else:
            slot.team = MatchTeams.blue

        m.enqueue_state(lobby=False)


@register(ClientPackets.CHANNEL_PART, restricted=True)
class ChannelPart(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.name = reader.read_string()

    async def handle(self, p: Player) -> None:
        if self.name in IGNORED_CHANNELS:
            return

        c = glob.channels[self.name]

        if not c:
            log(f"{p} failed to leave {self.name}.", Ansi.LYELLOW)
            return

        if p not in c:
            # user not in chan
            return

        # leave the chan server-side.
        p.leave_channel(c)


@register(ClientPackets.RECEIVE_UPDATES, restricted=True)
class ReceiveUpdates(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.value = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not 0 <= self.value < 3:
            log(f"{p} tried to set his presence filter to {self.value}?")
            return

        p.pres_filter = PresenceFilter(self.value)


@register(ClientPackets.SET_AWAY_MESSAGE)
class SetAwayMessage(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.msg = reader.read_message()

    async def handle(self, p: Player) -> None:
        p.away_msg = self.msg.text


@register(ClientPackets.USER_STATS_REQUEST, restricted=True)
class StatsRequest(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.user_ids = reader.read_i32_list_i16l()

    async def handle(self, p: Player) -> None:
        unrestrcted_ids = [p.id for p in glob.players.unrestricted]
        is_online = lambda o: o in unrestrcted_ids and o != p.id

        for online in filter(is_online, self.user_ids):
            if t := glob.players.get(id=online):
                p.enqueue(packets.user_stats(t))


@register(ClientPackets.MATCH_INVITE)
class MatchInvite(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.user_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not p.match:
            return

        if not (t := glob.players.get(id=self.user_id)):
            log(f"{p} tried to invite a user who is not online! ({self.user_id})")
            return

        if t is glob.bot:
            p.send_bot("I'm too busy!")
            return

        t.enqueue(packets.match_invite(p, t.name))
        p.update_latest_activity()

        log(f"{p} invited {t} to their match.")


@register(ClientPackets.MATCH_CHANGE_PASSWORD)
class MatchChangePassword(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match = reader.read_match()

    async def handle(self, p: Player) -> None:
        if not (m := p.match):
            return

        if p is not m.host:
            log(f"{p} attempted to change pw as non-host.", Ansi.LYELLOW)
            return

        m.passwd = self.match.passwd
        m.enqueue_state()


@register(ClientPackets.USER_PRESENCE_REQUEST)
class UserPresenceRequest(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.user_ids = reader.read_i32_list_i16l()

    async def handle(self, p: Player) -> None:
        for pid in self.user_ids:
            if t := glob.players.get(id=pid):
                p.enqueue(packets.user_presence(t))


@register(ClientPackets.USER_PRESENCE_REQUEST_ALL)
class UserPresenceRequestAll(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        # TODO: should probably ratelimit with this (300k s)
        self.ingame_time = reader.read_i32()

    async def handle(self, p: Player) -> None:
        # NOTE: this packet is only used when there
        # are >256 players visible to the client.

        p.enqueue(b"".join(map(packets.user_presence, glob.players.unrestricted)))


@register(ClientPackets.TOGGLE_BLOCK_NON_FRIEND_DMS)
class ToggleBlockingDMs(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.value = reader.read_i32()

    async def handle(self, p: Player) -> None:
        p.pm_private = self.value == 1

        p.update_latest_activity()
