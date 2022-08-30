""" cho: handle cho packets from the osu! client """
from __future__ import annotations

import asyncio
import re
import struct
import time
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Callable
from typing import Literal
from typing import Optional
from typing import TypedDict

import bcrypt
import databases.core
from fastapi import APIRouter
from fastapi import Response
from fastapi.param_functions import Header
from fastapi.requests import Request
from fastapi.responses import HTMLResponse

import app.packets
import app.settings
import app.state
import app.usecases.performance
import app.utils
from app import commands
from app._typing import IPAddress
from app.constants import regexes
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.mods import SPEED_CHANGING_MODS
from app.constants.privileges import ClanPrivileges
from app.constants.privileges import ClientPrivileges
from app.constants.privileges import Privileges
from app.logging import Ansi
from app.logging import log
from app.logging import magnitude_fmt_time
from app.objects.beatmap import Beatmap
from app.objects.beatmap import ensure_local_osu_file
from app.objects.channel import Channel
from app.objects.match import Match
from app.objects.match import MatchTeams
from app.objects.match import MatchTeamTypes
from app.objects.match import Slot
from app.objects.match import SlotStatus
from app.objects.menu import Menu
from app.objects.menu import MenuCommands
from app.objects.menu import MenuFunction
from app.objects.player import Action
from app.objects.player import ClientDetails
from app.objects.player import OsuStream
from app.objects.player import OsuVersion
from app.objects.player import Player
from app.objects.player import PresenceFilter
from app.packets import BanchoPacketReader
from app.packets import BasePacket
from app.packets import ClientPackets
from app.state import services
from app.usecases.performance import ScoreDifficultyParams

OSU_API_V2_CHANGELOG_URL = "https://osu.ppy.sh/api/v2/changelog"

BEATMAPS_PATH = Path.cwd() / ".data/osu"

BASE_DOMAIN = app.settings.DOMAIN

# TODO: dear god
NOW_PLAYING_RGX = re.compile(
    r"^\x01ACTION is (?:playing|editing|watching|listening to) "
    rf"\[https://osu\.(?:{re.escape(BASE_DOMAIN)}|ppy\.sh)/beatmapsets/(?P<sid>\d{{1,10}})#/?(?:osu|taiko|fruits|mania)?/(?P<bid>\d{{1,10}})/? .+\]"
    r"(?: <(?P<mode_vn>Taiko|CatchTheBeat|osu!mania)>)?"
    r"(?P<mods>(?: (?:-|\+|~|\|)\w+(?:~|\|)?)+)?\x01$",
)

router = APIRouter(tags=["Bancho API"])


@router.get("/")
async def bancho_http_handler():
    """Handle a request from a web browser."""
    packets = app.state.packets["all"]

    return HTMLResponse(
        b"<!DOCTYPE html>"
        + "<br>".join(
            (
                f"Running bancho.py v{app.settings.VERSION}",
                f"Players online: {len(app.state.sessions.players) - 1}",
                '<a href="https://github.com/osuAkatsuki/bancho.py">Source code</a>',
                "",
                f"<b>packets handled ({len(packets)})</b>",
                "<br>".join([f"{p.name} ({p.value})" for p in packets]),
            ),
        ).encode(),
    )


@router.post("/")
async def bancho_handler(
    request: Request,
    osu_token: Optional[str] = Header(None),
    user_agent: Literal["osu!"] = Header(...),
):
    ip = app.state.services.ip_resolver.get_ip(request.headers)

    if osu_token is None:
        # the client is performing a login
        async with app.state.services.database.connection() as db_conn:
            login_data = await login(await request.body(), ip, db_conn)

        return Response(
            content=login_data["response_body"],
            headers={"cho-token": login_data["osu_token"]},
        )

    # get the player from the specified osu token.
    player = app.state.sessions.players.get(token=osu_token)

    if not player:
        # chances are, we just restarted the server
        # tell their client to reconnect immediately.
        return Response(
            content=(
                app.packets.notification("Server has restarted.")
                + app.packets.restart_server(0)  # ms until reconnection
            ),
        )

    if player.restricted:
        # restricted users may only use certain packet handlers.
        packet_map = app.state.packets["restricted"]
    else:
        packet_map = app.state.packets["all"]

    # bancho connections can be comprised of multiple packets;
    # our reader is designed to iterate through them individually,
    # allowing logic to be implemented around the actual handler.
    # NOTE: any unhandled packets will be ignored internally.

    with memoryview(await request.body()) as body_view:
        for packet in BanchoPacketReader(body_view, packet_map):
            await packet.handle(player)

    player.last_recv_time = time.time()

    response_data = player.dequeue()
    return Response(content=response_data)


""" Packet logic """


def register(
    packet: ClientPackets,
    restricted: bool = False,
) -> Callable[[type[BasePacket]], type[BasePacket]]:
    """Register a handler in `app.state.packets`."""

    def wrapper(cls: type[BasePacket]) -> type[BasePacket]:
        app.state.packets["all"][packet] = cls

        if restricted:
            app.state.packets["restricted"][packet] = cls

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
        if self.mods & Mods.RELAX:
            if self.mode == 3:  # rx!mania doesn't exist
                self.mods &= ~Mods.RELAX
            else:
                self.mode += 4
        elif self.mods & Mods.AUTOPILOT:
            if self.mode in (1, 2, 3):  # ap!catch, taiko and mania don't exist
                self.mods &= ~Mods.AUTOPILOT
            else:
                self.mode += 8

        self.map_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        # update the user's status.
        p.status.action = Action(self.action)
        p.status.info_text = self.info_text
        p.status.map_md5 = self.map_md5
        p.status.mods = Mods(self.mods)
        p.status.mode = GameMode(self.mode)
        p.status.map_id = self.map_id

        # broadcast it to all online players.
        if not p.restricted:
            app.state.sessions.players.enqueue(app.packets.user_stats(p))


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

            t_chan = app.state.sessions.channels[f"#spec_{spec_id}"]
        elif recipient == "#multiplayer":
            if not p.match:
                # they're not in a match?
                return

            t_chan = p.match.chat
        else:
            t_chan = app.state.sessions.channels[recipient]

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
                app.packets.notification(
                    "Your message was truncated\n(exceeded 2000 characters).",
                ),
            )

        if msg.startswith(app.settings.COMMAND_PREFIX):
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
                staff = app.state.sessions.players.staff
                t_chan.send_selective(msg=msg, sender=p, recipients=staff - {p})
                if cmd["resp"] is not None:
                    t_chan.send_selective(
                        msg=cmd["resp"],
                        sender=app.state.sessions.bot,
                        recipients=staff | {p},
                    )

        else:
            # no commands were triggered

            # check if the user is /np'ing a map.
            # even though this is a public channel,
            # we'll update the player's last np stored.
            if r_match := NOW_PLAYING_RGX.match(msg):
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

        p.update_latest_activity_soon()
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

        p.update_latest_activity_soon()


@register(ClientPackets.REQUEST_STATUS_UPDATE, restricted=True)
class StatsUpdateRequest(BasePacket):
    async def handle(self, p: Player) -> None:
        p.enqueue(app.packets.user_stats(p))


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

WELCOME_NOTIFICATION = app.packets.notification(
    f"Welcome back to {BASE_DOMAIN}!\nRunning bancho.py v{app.settings.VERSION}.",
)

OFFLINE_NOTIFICATION = app.packets.notification(
    "The server is currently running in offline mode; "
    "some features will be unavailable.",
)


class LoginResponse(TypedDict):
    osu_token: str
    response_body: bytes


class LoginData(TypedDict):
    username: str
    password_md5: bytes
    osu_version: str
    utc_offset: int
    display_city: bool
    pm_private: bool
    osu_path_md5: str
    adapters_str: str
    adapters_md5: str
    uninstall_md5: str
    disk_signature_md5: str


def parse_login_data(data: bytes) -> LoginData:
    """Parse data from the body of a login request."""
    (
        username,
        password_md5,
        remainder,
    ) = data.decode().split("\n", maxsplit=2)

    (
        osu_version,
        utc_offset,
        display_city,
        client_hashes,
        pm_private,
    ) = remainder.split("|", maxsplit=4)

    (
        osu_path_md5,
        adapters_str,
        adapters_md5,
        uninstall_md5,
        disk_signature_md5,
    ) = client_hashes[:-1].split(":", maxsplit=4)

    return {
        "username": username,
        "password_md5": password_md5.encode(),
        "osu_version": osu_version,
        "utc_offset": int(utc_offset),
        "display_city": display_city == "1",
        "pm_private": pm_private == "1",
        "osu_path_md5": osu_path_md5,
        "adapters_str": adapters_str,
        "adapters_md5": adapters_md5,
        "uninstall_md5": uninstall_md5,
        "disk_signature_md5": disk_signature_md5,
    }


async def login(
    body: bytes,
    ip: IPAddress,
    db_conn: databases.core.Connection,
) -> LoginResponse:
    """\
    Login has no specific packet, but happens when the osu!
    client sends a request without an 'osu-token' header.

    Request format:
      username\npasswd_md5\nosu_version|utc_offset|display_city|client_hashes|pm_private\n

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

    # parse login data
    login_data = parse_login_data(body)

    # perform some validation & further parsing on the data

    match = regexes.OSU_VERSION.match(login_data["osu_version"])
    if match is None:
        return {
            "osu_token": "invalid-request",
            "response_body": b"",
        }

    osu_version = OsuVersion(
        date=date(
            year=int(match["date"][0:4]),
            month=int(match["date"][4:6]),
            day=int(match["date"][6:8]),
        ),
        revision=int(match["revision"]) if match["revision"] else None,
        stream=OsuStream(match["stream"] or "stable"),
    )

    if app.settings.DISALLOW_OLD_CLIENTS:
        osu_client_stream = osu_version.stream.value
        if osu_client_stream in ("stable", "beta"):
            osu_client_stream += "40"  # TODO: why?

        allowed_client_versions = set()

        async with services.http_client.get(
            OSU_API_V2_CHANGELOG_URL,
            params={"stream": osu_client_stream},
        ) as resp:
            for build in (await resp.json())["builds"]:
                version = date(
                    int(build["version"][0:4]),
                    int(build["version"][4:6]),
                    int(build["version"][6:8]),
                )
                allowed_client_versions.add(version)

                if any(entry["major"] for entry in build["changelog_entries"]):
                    # this build is a major iteration to the client
                    # don't allow anything older than this
                    break

        if osu_version.date not in allowed_client_versions:
            return {
                "osu_token": "client-too-old",
                "response_body": (
                    app.packets.version_update_forced() + app.packets.user_id(-2)
                ),
            }

    running_under_wine = login_data["adapters_str"] == "runningunderwine"
    adapters = [a for a in login_data["adapters_str"][:-1].split(".")]

    if not (running_under_wine or any(adapters)):
        return {
            "osu_token": "empty-adapters",
            "response_body": (
                app.packets.user_id(-1)
                + app.packets.notification("Please restart your osu! and try again.")
            ),
        }

    ## parsing successful

    login_time = time.time()

    # TODO: improve tournament client support
    if p := app.state.sessions.players.get(name=login_data["username"]):
        # player is already logged in - allow this only for tournament clients

        if not (osu_version.stream == "tourney" or p.tourney_client):
            # neither session is a tournament client, disallow

            if (login_time - p.last_recv_time) > 10:
                # let this session overrule the existing one
                # (this is made to help prevent user ghosting)
                p.logout()
            else:
                # current session is still active, disallow
                return {
                    "osu_token": "user-ghosted",
                    "response_body": (
                        app.packets.user_id(-1)
                        + app.packets.notification("User already logged in.")
                    ),
                }

    user_info = await db_conn.fetch_one(
        "SELECT id, name, priv, pw_bcrypt, country, "
        "silence_end, clan_id, clan_priv, api_key "
        "FROM users WHERE safe_name = :name",
        {"name": app.utils.make_safe_name(login_data["username"])},
    )

    if user_info is None:
        # no account by this name exists.
        return {
            "osu_token": "unknown-username",
            "response_body": (
                app.packets.notification(f"{BASE_DOMAIN}: Unknown username")
                + app.packets.user_id(-1)
            ),
        }

    user_info = dict(user_info)  # make a mutable copy

    if osu_version.stream == "tourney" and not (
        user_info["priv"] & Privileges.DONATOR
        and user_info["priv"] & Privileges.UNRESTRICTED
    ):
        # trying to use tourney client with insufficient privileges.
        return {
            "osu_token": "no",
            "response_body": app.packets.user_id(-1),
        }

    # get our bcrypt cache
    bcrypt_cache = app.state.cache.bcrypt
    pw_bcrypt = user_info["pw_bcrypt"].encode()
    user_info["pw_bcrypt"] = pw_bcrypt

    # check credentials against db. algorithms like these are intentionally
    # designed to be slow; we'll cache the results to speed up subsequent logins.
    if pw_bcrypt in bcrypt_cache:  # ~0.01 ms
        if login_data["password_md5"] != bcrypt_cache[pw_bcrypt]:
            return {
                "osu_token": "incorrect-password",
                "response_body": (
                    app.packets.notification(f"{BASE_DOMAIN}: Incorrect password")
                    + app.packets.user_id(-1)
                ),
            }
    else:  # ~200ms
        if not bcrypt.checkpw(login_data["password_md5"], pw_bcrypt):
            return {
                "osu_token": "incorrect-password",
                "response_body": (
                    app.packets.notification(f"{BASE_DOMAIN}: Incorrect password")
                    + app.packets.user_id(-1)
                ),
            }

        bcrypt_cache[pw_bcrypt] = login_data["password_md5"]

    """ login credentials verified """

    await db_conn.execute(
        "INSERT INTO ingame_logins "
        "(userid, ip, osu_ver, osu_stream, datetime) "
        "VALUES (:id, :ip, :osu_ver, :osu_stream, NOW())",
        {
            "id": user_info["id"],
            "ip": str(ip),
            "osu_ver": osu_version.date,
            "osu_stream": osu_version.stream,
        },
    )

    await db_conn.execute(
        "INSERT INTO client_hashes "
        "(userid, osupath, adapters, uninstall_id,"
        " disk_serial, latest_time, occurrences) "
        "VALUES (:id, :osupath, :adapters, :uninstall, :disk_serial, NOW(), 1) "
        "ON DUPLICATE KEY UPDATE "
        "occurrences = occurrences + 1, "
        "latest_time = NOW() ",
        {
            "id": user_info["id"],
            "osupath": login_data["osu_path_md5"],
            "adapters": login_data["adapters_md5"],
            "uninstall": login_data["uninstall_md5"],
            "disk_serial": login_data["disk_signature_md5"],
        },
    )

    # TODO: store adapters individually

    if running_under_wine:
        hw_checks = "h.uninstall_id = :uninstall"
        hw_args = {"uninstall": login_data["uninstall_md5"]}
    else:
        hw_checks = "h.adapters = :adapters OR h.uninstall_id = :uninstall OR h.disk_serial = :disk_serial"
        hw_args = {
            "adapters": login_data["adapters_md5"],
            "uninstall": login_data["uninstall_md5"],
            "disk_serial": login_data["disk_signature_md5"],
        }

    hw_matches = await db_conn.fetch_all(
        "SELECT u.name, u.priv, h.occurrences "
        "FROM client_hashes h "
        "INNER JOIN users u ON h.userid = u.id "
        "WHERE h.userid != :user_id AND "
        f"({hw_checks})",
        {"user_id": user_info["id"], **hw_args},
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
                [hw_match["priv"] & Privileges.UNRESTRICTED for hw_match in hw_matches],
            ):
                return {
                    "osu_token": "contact-staff",
                    "response_body": (
                        app.packets.notification(
                            "Please contact staff directly to create an account.",
                        )
                        + app.packets.user_id(-1)
                    ),
                }

    """ All checks passed, player is safe to login """

    # get clan & clan priv if we're in a clan
    if user_info["clan_id"] != 0:
        clan = app.state.sessions.clans.get(id=user_info.pop("clan_id"))
        clan_priv = ClanPrivileges(user_info.pop("clan_priv"))
    else:
        del user_info["clan_id"]
        del user_info["clan_priv"]
        clan = clan_priv = None

    db_country = user_info.pop("country")

    if not ip.is_private:
        if app.state.services.geoloc_db is not None:
            # good, dev has downloaded a geoloc db from maxmind,
            # so we can do a local db lookup. (typically ~1-5ms)
            # https://www.maxmind.com/en/home
            user_info["geoloc"] = app.state.services.fetch_geoloc_db(ip)
        else:
            # bad, we must do an external db lookup using
            # a public api. (depends, `ping ip-api.com`)
            user_info["geoloc"] = await app.state.services.fetch_geoloc_web(ip)

        if db_country == "xx":
            # bugfix for old bancho.py versions when
            # country wasn't stored on registration.
            log(f"Fixing {login_data['username']}'s country.", Ansi.LGREEN)

            await db_conn.execute(
                "UPDATE users SET country = :country WHERE id = :user_id",
                {
                    "country": user_info["geoloc"]["country"]["acronym"],
                    "user_id": user_info["id"],
                },
            )

    client_details = ClientDetails(
        osu_version=osu_version,
        osu_path_md5=login_data["osu_path_md5"],
        adapters_md5=login_data["adapters_md5"],
        uninstall_md5=login_data["uninstall_md5"],
        disk_signature_md5=login_data["disk_signature_md5"],
        adapters=adapters,
        ip=ip,
    )

    p = Player(
        **user_info,  # {id, name, priv, pw_bcrypt, silence_end, api_key, geoloc?}
        utc_offset=login_data["utc_offset"],
        pm_private=login_data["pm_private"],
        login_time=login_time,
        clan=clan,
        clan_priv=clan_priv,
        tourney_client=osu_version.stream == "tourney",
        client_details=client_details,
    )

    data = bytearray(app.packets.protocol_version(19))
    data += app.packets.user_id(p.id)

    # *real* client privileges are sent with this packet,
    # then the user's apparent privileges are sent in the
    # userPresence packets to other players. we'll send
    # supporter along with the user's privileges here,
    # but not in userPresence (so that only donators
    # show up with the yellow name in-game, but everyone
    # gets osu!direct & other in-game perks).
    data += app.packets.bancho_privileges(p.bancho_priv | ClientPrivileges.SUPPORTER)

    data += WELCOME_NOTIFICATION

    # send all appropriate channel info to our player.
    # the osu! client will attempt to join the channels.
    for c in app.state.sessions.channels:
        if (
            not c.auto_join
            or not c.can_read(p.priv)
            or c._name == "#lobby"  # (can't be in mp lobby @ login)
        ):
            continue

        # send chan info to all players who can see
        # the channel (to update their playercounts)
        chan_info_packet = app.packets.channel_info(c._name, c.topic, len(c.players))

        data += chan_info_packet

        for o in app.state.sessions.players:
            if c.can_read(o.priv):
                o.enqueue(chan_info_packet)

    # tells osu! to reorder channels based on config.
    data += app.packets.channel_info_end()

    # fetch some of the player's
    # information from sql to be cached.
    await p.achievements_from_sql(db_conn)
    await p.stats_from_sql_full(db_conn)
    await p.relationships_from_sql(db_conn)

    # TODO: fetch p.recent_scores from sql

    data += app.packets.main_menu_icon(
        icon_url=app.settings.MENU_ICON_URL,
        onclick_url=app.settings.MENU_ONCLICK_URL,
    )
    data += app.packets.friends_list(p.friends)
    data += app.packets.silence_end(p.remaining_silence)

    # update our new player's stats, and broadcast them.
    user_data = app.packets.user_presence(p) + app.packets.user_stats(p)

    data += user_data

    if not p.restricted:
        # player is unrestricted, two way data
        for o in app.state.sessions.players:
            # enqueue us to them
            o.enqueue(user_data)

            # enqueue them to us.
            if not o.restricted:
                if o is app.state.sessions.bot:
                    # optimization for bot since it's
                    # the most frequently requested user
                    data += app.packets.bot_presence(o)
                    data += app.packets.bot_stats(o)
                else:
                    data += app.packets.user_presence(o)
                    data += app.packets.user_stats(o)

        # the player may have been sent mail while offline,
        # enqueue any messages from their respective authors.
        mail_rows = await db_conn.fetch_all(
            "SELECT m.`msg`, m.`time`, m.`from_id`, "
            "(SELECT name FROM users WHERE id = m.`from_id`) AS `from`, "
            "(SELECT name FROM users WHERE id = m.`to_id`) AS `to` "
            "FROM `mail` m WHERE m.`to_id` = :to AND m.`read` = 0",
            {"to": p.id},
        )

        if mail_rows:
            sent_to = set()  # ids

            for msg in mail_rows:
                if msg["from"] not in sent_to:
                    data += app.packets.send_message(
                        sender=msg["from"],
                        msg="Unread messages",
                        recipient=msg["to"],
                        sender_id=msg["from_id"],
                    )
                    sent_to.add(msg["from"])

                msg_time = datetime.fromtimestamp(msg["time"])

                data += app.packets.send_message(
                    sender=msg["from"],
                    msg=f'[{msg_time:%a %b %d @ %H:%M%p}] {msg["msg"]}',
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
                    | Privileges.TOURNEY_MANAGER
                    | Privileges.DONATOR
                    | Privileges.ALUMNI,
                )

            data += app.packets.send_message(
                sender=app.state.sessions.bot.name,
                msg=WELCOME_MSG,
                recipient=p.name,
                sender_id=app.state.sessions.bot.id,
            )

    else:
        # player is restricted, one way data
        for o in app.state.sessions.players.unrestricted:
            # enqueue them to us.
            if o is app.state.sessions.bot:
                # optimization for bot since it's
                # the most frequently requested user
                data += app.packets.bot_presence(o)
                data += app.packets.bot_stats(o)
            else:
                data += app.packets.user_presence(o)
                data += app.packets.user_stats(o)

        data += app.packets.account_restricted()
        data += app.packets.send_message(
            sender=app.state.sessions.bot.name,
            msg=RESTRICTED_MSG,
            recipient=p.name,
            sender_id=app.state.sessions.bot.id,
        )

    # TODO: some sort of admin panel for staff members?

    # add `p` to the global player list,
    # making them officially logged in.
    app.state.sessions.players.append(p)

    if app.state.services.datadog:
        if not p.restricted:
            app.state.services.datadog.increment("bancho.online_players")

        time_taken = time.time() - login_time
        app.state.services.datadog.histogram("bancho.login_time", time_taken)

    user_os = "unix (wine)" if running_under_wine else "win32"
    country_code = p.geoloc["country"]["acronym"].upper()

    log(
        f"{p} logged in from {country_code} using {login_data['osu_version']} on {user_os}",
        Ansi.LCYAN,
    )

    p.update_latest_activity_soon()

    return {"osu_token": p.token, "response_body": bytes(data)}


@register(ClientPackets.START_SPECTATING)
class StartSpectating(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.target_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not (new_host := app.state.sessions.players.get(id=self.target_id)):
            log(f"{p} tried to spectate nonexistant id {self.target_id}.", Ansi.LYELLOW)
            return

        if current_host := p.spectating:
            if current_host == new_host:
                # host hasn't changed, they didn't have
                # the map but have downloaded it.

                if not p.stealth:
                    # NOTE: `p` would have already received the other
                    # fellow spectators, so no need to resend them.
                    new_host.enqueue(app.packets.spectator_joined(p.id))

                    p_joined = app.packets.fellow_spectator_joined(p.id)
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
        # TODO: perform validations on the parsed frame bundle
        # to ensure it's not being tamperated with or weaponized.

        # NOTE: this is given a fastpath here for efficiency due to the
        # sheer rate of usage of these packets in spectator mode.

        # data = app.packets.spectateFrames(self.frame_bundle.raw_data)
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
            data = app.packets.spectator_cant_spectate(p.id)

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
            if app.settings.DEBUG:
                log(f"{p} tried to send a dm while silenced.", Ansi.LYELLOW)
            return

        # remove leading/trailing whitespace
        msg = self.msg.text.strip()

        if not msg:
            return

        t_name = self.msg.recipient

        # allow this to get from sql - players can receive
        # messages offline, due to the mail system. B)
        if not (t := await app.state.sessions.players.from_cache_or_sql(name=t_name)):
            if app.settings.DEBUG:
                log(f"{p} tried to write to non-existent user {t_name}.", Ansi.LYELLOW)
            return

        if p.id in t.blocks:
            p.enqueue(app.packets.user_dm_blocked(t_name))

            if app.settings.DEBUG:
                log(f"{p} tried to message {t}, but they have them blocked.")
            return

        if t.pm_private and p.id not in t.friends:
            p.enqueue(app.packets.user_dm_blocked(t_name))

            if app.settings.DEBUG:
                log(f"{p} tried to message {t}, but they are blocking dms.")
            return

        if t.silenced:
            # if target is silenced, inform player.
            p.enqueue(app.packets.target_silenced(t_name))

            if app.settings.DEBUG:
                log(f"{p} tried to message {t}, but they are silenced.")
            return

        # limit message length to 2k chars
        # perhaps this could be dangerous with !py..?
        if len(msg) > 2000:
            msg = f"{msg[:2000]}... (truncated)"
            p.enqueue(
                app.packets.notification(
                    "Your message was truncated\n(exceeded 2000 characters).",
                ),
            )

        if t.status.action == Action.Afk and t.away_msg:
            # send away message if target is afk and has one set.
            p.send(t.away_msg, sender=t)

        if t is not app.state.sessions.bot:
            # target is not bot, send the message normally if online
            if t.online:
                t.send(msg, sender=p)
            else:
                # inform user they're offline, but
                # will receive the mail @ next login.
                p.enqueue(
                    app.packets.notification(
                        f"{t.name} is currently offline, but will "
                        "receive your messsage on their next login.",
                    ),
                )

            # insert mail into db, marked as unread.
            await app.state.services.database.execute(
                "INSERT INTO `mail` "
                "(`from_id`, `to_id`, `msg`, `time`) "
                "VALUES (:from, :to, :msg, UNIX_TIMESTAMP())",
                {"from": p.id, "to": t.id, "msg": msg},
            )
        else:
            # messaging the bot, check for commands & /np.
            if msg.startswith(app.settings.COMMAND_PREFIX):
                cmd = await commands.process_commands(p, t, msg)
            else:
                cmd = None

            if cmd:
                # command triggered, send response if any.
                if cmd["resp"] is not None:
                    p.send(cmd["resp"], sender=t)
            else:
                # no commands triggered.
                if r_match := NOW_PLAYING_RGX.match(msg):
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

                            if r_match["mods"] is not None:
                                # [1:] to remove leading whitespace
                                mods_str = r_match["mods"][1:]
                                mods = Mods.from_np(mods_str, mode_vn)
                            else:
                                mods = None

                            if mode_vn in (0, 1, 2):
                                scores: list[ScoreDifficultyParams] = [
                                    {"acc": acc}
                                    for acc in app.settings.PP_CACHED_ACCURACIES
                                ]
                            else:  # mode_vn == 3
                                scores: list[ScoreDifficultyParams] = [
                                    {"score": score}
                                    for score in app.settings.PP_CACHED_SCORES
                                ]

                            results = app.usecases.performance.calculate_performances(
                                osu_file_path=str(osu_file_path),
                                mode=mode_vn,
                                mods=int(mods) if mods is not None else None,
                                scores=scores,
                            )

                            if mode_vn in (0, 1, 2):
                                resp_msg = " | ".join(
                                    f"{acc}%: {result['performance']:,.2f}pp"
                                    for acc, result in zip(
                                        app.settings.PP_CACHED_ACCURACIES,
                                        results,
                                    )
                                )
                            else:  # mode_vn == 3
                                resp_msg = " | ".join(
                                    f"{score // 1000:.0f}k: {result['performance']:,.2f}pp"
                                    for score, result in zip(
                                        app.settings.PP_CACHED_SCORES,
                                        results,
                                    )
                                )

                            elapsed = time.time_ns() - pp_calc_st
                            resp_msg += f" | Elapsed: {magnitude_fmt_time(elapsed)}"
                    else:
                        resp_msg = "Could not find map."

                        # time out their previous /np
                        p.last_np["timeout"] = 0.0

                    p.send(resp_msg, sender=t)

        p.update_latest_activity_soon()
        log(f"{p} @ {t}: {msg}", Ansi.LCYAN, file=".data/logs/chat.log")


@register(ClientPackets.PART_LOBBY)
class LobbyPart(BasePacket):
    async def handle(self, p: Player) -> None:
        p.in_lobby = False


@register(ClientPackets.JOIN_LOBBY)
class LobbyJoin(BasePacket):
    async def handle(self, p: Player) -> None:
        p.in_lobby = True

        for m in app.state.sessions.matches:
            if m is not None:
                p.enqueue(app.packets.new_match(m))


@register(ClientPackets.CREATE_MATCH)
class MatchCreate(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match = Match.from_parsed_match(reader.read_match())

    async def handle(self, p: Player) -> None:
        # TODO: match validation..?
        if p.restricted:
            p.enqueue(
                app.packets.match_join_fail()
                + app.packets.notification(
                    "Multiplayer is not available while restricted.",
                ),
            )
            return

        if p.silenced:
            p.enqueue(
                app.packets.match_join_fail()
                + app.packets.notification(
                    "Multiplayer is not available while silenced.",
                ),
            )
            return

        if not app.state.sessions.matches.append(self.match):
            # failed to create match (match slots full).
            p.send_bot("Failed to create match (no slots available).")
            p.enqueue(app.packets.match_join_fail())
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

        app.state.sessions.channels.append(chan)
        self.match.chat = chan

        p.update_latest_activity_soon()
        p.join_match(self.match, self.match.passwd)

        self.match.chat.send_bot(f"Match created by {p.name}.")
        log(f"{p} created a new multiplayer match.")


async def execute_menu_option(p: Player, key: int) -> None:
    if key not in p.current_menu.options:
        return

    # this is one of their menu options, execute it.
    cmd, data = p.current_menu.options[key]

    if app.settings.DEBUG:
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
        is_menu_request = self.match_id >= 64  # max multi matches

        if is_menu_request or self.match_id < 0:
            if is_menu_request:
                # NOTE: this function is unrelated to mp.
                await execute_menu_option(p, self.match_id)

            p.enqueue(app.packets.match_join_fail())
            return

        if not (m := app.state.sessions.matches[self.match_id]):
            log(f"{p} tried to join a non-existant mp lobby?")
            p.enqueue(app.packets.match_join_fail())
            return

        if p.restricted:
            p.enqueue(
                app.packets.match_join_fail()
                + app.packets.notification(
                    "Multiplayer is not available while restricted.",
                ),
            )
            return

        if p.silenced:
            p.enqueue(
                app.packets.match_join_fail()
                + app.packets.notification(
                    "Multiplayer is not available while silenced.",
                ),
            )
            return

        p.update_latest_activity_soon()
        p.join_match(m, self.match_passwd)


@register(ClientPackets.PART_MATCH)
class MatchPart(BasePacket):
    async def handle(self, p: Player) -> None:
        p.update_latest_activity_soon()
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
        self.new = Match.from_parsed_match(reader.read_match())

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
                m.map_name = bmap.full_name
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
        m.enqueue(app.packets.match_complete(), lobby=False, immune=not_playing)
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
            m.enqueue(app.packets.match_all_players_loaded(), lobby=False)


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

        m.enqueue(app.packets.match_player_failed(slot_id), lobby=False)


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
        m.enqueue(app.packets.match_player_skipped(p.id))

        for slot in m.slots:
            if slot.status == SlotStatus.playing and not slot.skipped:
                return

        # all users have skipped, enqueue a skip.
        m.enqueue(app.packets.match_skip(), lobby=False)


@register(ClientPackets.CHANNEL_JOIN, restricted=True)
class ChannelJoin(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.name = reader.read_string()

    async def handle(self, p: Player) -> None:
        if self.name in IGNORED_CHANNELS:
            return

        c = app.state.sessions.channels[self.name]

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

        m.host_id = t.id
        m.host.enqueue(app.packets.match_transfer_host())
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

        if not (m := app.state.sessions.matches[self.match_id]):
            return  # match not found

        p.enqueue(app.packets.update_match(m, send_pw=False))


@register(ClientPackets.TOURNAMENT_JOIN_MATCH_CHANNEL)
class TourneyMatchJoinChannel(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not 0 <= self.match_id < 64:
            return  # invalid match id

        if not p.priv & Privileges.DONATOR:
            return  # insufficient privs

        if not (m := app.state.sessions.matches[self.match_id]):
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

        if not (m := app.state.sessions.matches[self.match_id]):
            return  # match not found

        # attempt to join match chan
        p.leave_channel(m.chat)
        m.tourney_clients.remove(p.id)


@register(ClientPackets.FRIEND_ADD)
class FriendAdd(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.user_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not (t := app.state.sessions.players.get(id=self.user_id)):
            log(f"{p} tried to add a user who is not online! ({self.user_id})")
            return

        if t is app.state.sessions.bot:
            return

        if t.id in p.blocks:
            p.blocks.remove(t.id)

        p.update_latest_activity_soon()
        await p.add_friend(t)


@register(ClientPackets.FRIEND_REMOVE)
class FriendRemove(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.user_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not (t := app.state.sessions.players.get(id=self.user_id)):
            log(f"{p} tried to remove a user who is not online! ({self.user_id})")
            return

        if t is app.state.sessions.bot:
            return

        p.update_latest_activity_soon()
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

        c = app.state.sessions.channels[self.name]

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
        unrestrcted_ids = [p.id for p in app.state.sessions.players.unrestricted]
        is_online = lambda o: o in unrestrcted_ids and o != p.id

        for online in filter(is_online, self.user_ids):
            if t := app.state.sessions.players.get(id=online):
                if t is app.state.sessions.bot:
                    # optimization for bot since it's
                    # the most frequently requested user
                    packet = app.packets.bot_stats(t)
                else:
                    packet = app.packets.user_stats(t)

                p.enqueue(packet)


@register(ClientPackets.MATCH_INVITE)
class MatchInvite(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.user_id = reader.read_i32()

    async def handle(self, p: Player) -> None:
        if not p.match:
            return

        if not (t := app.state.sessions.players.get(id=self.user_id)):
            log(f"{p} tried to invite a user who is not online! ({self.user_id})")
            return

        if t is app.state.sessions.bot:
            p.send_bot("I'm too busy!")
            return

        t.enqueue(app.packets.match_invite(p, t.name))
        p.update_latest_activity_soon()

        log(f"{p} invited {t} to their match.")


@register(ClientPackets.MATCH_CHANGE_PASSWORD)
class MatchChangePassword(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match = Match.from_parsed_match(reader.read_match())

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
            if t := app.state.sessions.players.get(id=pid):
                if t is app.state.sessions.bot:
                    # optimization for bot since it's
                    # the most frequently requested user
                    packet = app.packets.bot_presence(t)
                else:
                    packet = app.packets.user_presence(t)

                p.enqueue(packet)


@register(ClientPackets.USER_PRESENCE_REQUEST_ALL)
class UserPresenceRequestAll(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        # TODO: should probably ratelimit with this (300k s)
        self.ingame_time = reader.read_i32()

    async def handle(self, p: Player) -> None:
        # NOTE: this packet is only used when there
        # are >256 players visible to the client.

        buffer = bytearray()

        for player in app.state.sessions.players.unrestricted:
            buffer += app.packets.user_presence(player)

        p.enqueue(bytes(buffer))


@register(ClientPackets.TOGGLE_BLOCK_NON_FRIEND_DMS)
class ToggleBlockingDMs(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.value = reader.read_i32()

    async def handle(self, p: Player) -> None:
        p.pm_private = self.value == 1

        p.update_latest_activity_soon()
