""" cho: handle cho packets from the osu! client """

from __future__ import annotations

import asyncio
import re
import struct
import time
from collections import defaultdict
from collections.abc import Callable
from collections.abc import Mapping
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Literal
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
from app import builtin_bot
from app import commands
from app._typing import IPAddress
from app.constants import regexes
from app.constants.gamemodes import GameMode
from app.constants.mods import SPEED_CHANGING_MODS
from app.constants.mods import Mods
from app.constants.multiplayer import MatchTeams
from app.constants.multiplayer import MatchTeamTypes
from app.constants.multiplayer import MatchWinConditions
from app.constants.multiplayer import SlotStatus
from app.constants.osu_client_details import ClientDetails
from app.constants.osu_client_details import OsuStream
from app.constants.osu_client_details import OsuVersion
from app.constants.privileges import ClanPrivileges
from app.constants.privileges import ClientPrivileges
from app.constants.privileges import Privileges
from app.constants.privileges import get_client_privileges
from app.logging import Ansi
from app.logging import log
from app.logging import magnitude_fmt_time
from app.objects.beatmap import Beatmap
from app.objects.beatmap import ensure_osu_file_is_available
from app.objects.match import MAX_MATCH_NAME_LENGTH
from app.objects.player import Action
from app.objects.player import Player
from app.objects.player import PresenceFilter
from app.packets import BanchoPacketReader
from app.packets import BasePacket
from app.packets import ClientPackets
from app.packets import LoginFailureReason
from app.repositories import channel_memberships as channel_memberships_repo
from app.repositories import channels as channels_repo
from app.repositories import client_hashes as client_hashes_repo
from app.repositories import ingame_logins as logins_repo
from app.repositories import mail as mail_repo
from app.repositories import multiplayer_matches as matches_repo
from app.repositories import multiplayer_slots as match_slots_repo
from app.repositories import osu_sessions as osu_sessions_repo
from app.repositories import relationships as relationships_repo
from app.repositories import stats as stats_repo
from app.repositories import users as users_repo
from app.repositories.multiplayer_slots import MatchSlot
from app.repositories.relationships import RelationshipType
from app.state import services
from app.usecases import osu_sessions as osu_sessions_usecases
from app.usecases import users as users_usecases
from app.usecases.performance import ScoreParams
from app.usecases.users import has_verified_account
from app.usecases.users import is_restricted
from app.usecases.users import is_silenced

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

FIRST_USER_ID = 3

router = APIRouter(tags=["Bancho API"])


@router.get("/")
async def bancho_http_handler() -> Response:
    """Handle a request from a web browser."""
    new_line = "\n"

    matches = [m for m in app.state.sessions.matches if m is not None]
    players = [p for p in await osu_sessions_repo.fetch_all() if not p["is_bot_client"]]

    packets = app.state.packets["all"]

    return HTMLResponse(
        f"""
<!DOCTYPE html>
<body style="font-family: monospace; white-space: pre-wrap;">Running bancho.py v{app.settings.VERSION}

<a href="online">{len(players)} online players</a>
<a href="matches">{len(matches)} matches</a>

<b>packets handled ({len(packets)})</b>
{new_line.join([f"{packet.name} ({packet.value})" for packet in packets])}

<a href="https://github.com/osuAkatsuki/bancho.py">Source code</a>
</body>
</html>""",
    )


@router.get("/online")
async def bancho_view_online_users() -> Response:
    """see who's online"""
    new_line = "\n"

    all_osu_sessions = await osu_sessions_repo.fetch_all()

    players: list[osu_sessions_repo.OsuSession] = []
    bots: list[osu_sessions_repo.OsuSession] = []
    for p in all_osu_sessions:
        if p["is_bot_client"]:
            bots.append(p)
        else:
            players.append(p)

    id_max_length = len(str(max(p["user_id"] for p in all_osu_sessions)))

    return HTMLResponse(
        f"""
<!DOCTYPE html>
<body style="font-family: monospace;  white-space: pre-wrap;"><a href="/">back</a>
users:
{new_line.join([f"({p['user_id']:>{id_max_length}}): {app.utils.make_safe_name(p['name'])}" for p in players])}
bots:
{new_line.join(f"({p['user_id']:>{id_max_length}}): {app.utils.make_safe_name(p['name'])}" for p in bots)}
</body>
</html>""",
    )


@router.get("/matches")
async def bancho_view_matches() -> Response:
    """ongoing matches"""
    new_line = "\n"

    ON_GOING = "ongoing"
    IDLE = "idle"
    max_status_length = len(max(ON_GOING, IDLE))

    BEATMAP = "beatmap"
    HOST = "host"
    max_properties_length = max(len(BEATMAP), len(HOST))

    matches = [m for m in app.state.sessions.matches if m is not None]

    match_id_max_length = (
        len(str(max(match.id for match in matches))) if len(matches) else 0
    )

    return HTMLResponse(
        f"""
<!DOCTYPE html>
<body style="font-family: monospace;  white-space: pre-wrap;"><a href="/">back</a>
matches:
{new_line.join(
    f'''{(ON_GOING if m.in_progress else IDLE):<{max_status_length}} ({m.id:>{match_id_max_length}}): {m.name}
-- '''
    + f"{new_line}-- ".join([
        f'{BEATMAP:<{max_properties_length}}: {m.map_name}',
        f'{HOST:<{max_properties_length}}: <{m.host.id}> {m.host.safe_name}'
    ]) for m in matches
)}
</body>
</html>""",
    )


@router.post("/")
async def bancho_handler(
    request: Request,
    osu_token: str | None = Header(None),
    user_agent: Literal["osu!"] = Header(...),
) -> Response:
    ip = app.state.services.ip_resolver.get_ip(request.headers)

    if osu_token is None:
        # the client is performing a login
        async with app.state.services.database.connection() as db_conn:
            login_data = await handle_osu_login_request(
                request.headers,
                await request.body(),
                ip,
                db_conn,
            )

        return Response(
            content=login_data["response_body"],
            headers={"cho-token": login_data["osu_token"]},
        )

    # get the player from the specified osu token.
    osu_session = await osu_sessions_repo.fetch_one(session_id=osu_token)

    if not osu_session:
        # chances are, we just restarted the server
        # tell their client to reconnect immediately.
        return Response(
            content=(
                app.packets.notification("Server has restarted.")
                + app.packets.restart_server(0)  # ms until reconnection
            ),
        )

    if osu_session["priv"] & Privileges.UNRESTRICTED == 0:
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
            await packet.handle(osu_session)

    maybe_session = await osu_sessions_repo.partial_update(
        session_id=osu_session["session_id"],
        last_recv_time=int(time.time()),
    )
    assert maybe_session is not None
    osu_session = maybe_session

    response_data = await osu_sessions_repo.read_full_packet_queue(
        session_id=osu_session["session_id"],
    )
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
    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
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

    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        # update the user's status.
        maybe_session = await osu_sessions_repo.partial_update(
            session_id=osu_session["session_id"],
            status=osu_sessions_repo.Status(
                action=osu_sessions_repo.Action(self.action),
                info_text=self.info_text,
                map_md5=self.map_md5,
                mods=Mods(self.mods),
                mode=GameMode(self.mode),
                map_id=self.map_id,
            ),
        )
        assert maybe_session is not None
        osu_session = maybe_session

        # broadcast it to all online players.
        if not osu_session["priv"] & Privileges.UNRESTRICTED == 0:
            user_stats = await stats_repo.fetch_one(
                player_id=osu_session["user_id"],
                mode=int(osu_session["status"]["mode"]),
            )
            assert user_stats is not None

            global_rank = await stats_repo.get_global_rank(
                user_id=osu_session["user_id"],
                mode=osu_session["status"]["mode"],
            )

            await osu_sessions_repo.broadcast_osu_data(
                data=app.packets.user_stats(
                    user_id=osu_session["user_id"],
                    action=int(osu_session["status"]["action"]),
                    info_text=osu_session["status"]["info_text"],
                    map_md5=osu_session["status"]["map_md5"],
                    mods=int(osu_session["status"]["mods"]),
                    mode=int(osu_session["status"]["mode"]),
                    map_id=osu_session["status"]["map_id"],
                    ranked_score=user_stats["rscore"],
                    accuracy=user_stats["acc"],
                    plays=user_stats["plays"],
                    total_score=user_stats["tscore"],
                    global_rank=global_rank,
                    pp=user_stats["pp"],
                ),
            )


IGNORED_CHANNELS = ["#highlight", "#userlog"]


@register(ClientPackets.SEND_PUBLIC_MESSAGE)
class SendMessage(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.msg = reader.read_message()

    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        if is_silenced(osu_session["silence_end"]):
            log(
                f"User {osu_session['name']} sent a message while silenced.",
                Ansi.LYELLOW,
            )
            return

        # remove leading/trailing whitespace
        msg = self.msg.text.strip()

        if not msg:
            return

        recipient = self.msg.recipient

        if recipient in IGNORED_CHANNELS:
            return
        elif recipient == "#spectator":
            if osu_session["spectating_session_id"]:
                # we are spectating someone
                spectator_host = await osu_sessions_repo.fetch_one(
                    session_id=osu_session["spectating_session_id"],
                )
                assert spectator_host is not None
                spec_channel_user_id = spectator_host["user_id"]
            elif osu_session["spectator_session_ids"]:
                # we are being spectated
                spec_channel_user_id = osu_session["user_id"]
            else:
                log("Could not resolve spectator channel user id.", Ansi.LRED)
                return

            t_chan = app.state.sessions.channels.get_by_name(
                f"#spec_{spec_channel_user_id}",
            )
        elif recipient == "#multiplayer":
            if not osu_session["match_id"]:
                # they're not in a match?
                return

            t_chan = app.state.sessions.channels.get_by_name(
                f"#multi_{osu_session['match_id']}",
            )
        else:
            t_chan = app.state.sessions.channels.get_by_name(recipient)

        if not t_chan:
            log(
                f"User {osu_session['user_id']} wrote to non-existent {recipient}.",
                Ansi.LYELLOW,
            )
            return

        if osu_session["user_id"] not in {p.id for p in t_chan.players}:
            log(
                f"User {osu_session['user_id']} wrote to {recipient} without being in it.",
            )
            return

        if not t_chan.can_write(osu_session["priv"]):
            log(
                f"User {osu_session['user_id']} wrote to {recipient} with insufficient privileges.",
            )
            return

        # limit message length to 2k chars
        # perhaps this could be dangerous with !py..?
        if len(msg) > 2000:
            msg = f"{msg[:2000]}... (truncated)"
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=osu_session["session_id"],
                data=app.packets.notification(
                    "Your message was truncated\n(exceeded 2000 characters).",
                ),
            )

        if msg.startswith(app.settings.COMMAND_PREFIX):
            cmd = await commands.process_commands(osu_session, t_chan, msg)
        else:
            cmd = None

        if cmd:
            # a command was triggered.
            if not cmd["hidden"]:
                channel_memberships = await channel_memberships_repo.fetch_all(
                    channel_name=t_chan.name,
                )
                await osu_sessions_repo.multicast_osu_data(
                    target_session_ids={p["session_id"] for p in channel_memberships},
                    data=app.packets.send_message(
                        sender=osu_session["name"],
                        msg=msg,
                        recipient=t_chan.name,
                        sender_id=osu_session["user_id"],
                    ),
                )

                if cmd["resp"] is not None:

                    t_chan.send_bot(cmd["resp"])
            else:
                all_osu_sessions = await osu_sessions_repo.fetch_all()
                staff_session_ids = {
                    p["session_id"]
                    for p in all_osu_sessions
                    if p["priv"] & Privileges.STAFF > 0
                }
                await osu_sessions_repo.multicast_osu_data(
                    target_session_ids=staff_session_ids - {osu_session["session_id"]},
                    data=app.packets.send_message(
                        sender=osu_session["name"],
                        msg=msg,
                        recipient=t_chan.name,
                        sender_id=osu_session["user_id"],
                    ),
                )
                if cmd["resp"] is not None:
                    for session_id in staff_session_ids | {osu_session["session_id"]}:
                        await osu_sessions_repo.unicast_osu_data(
                            target_session_id=session_id,
                            data=app.packets.send_message(
                                sender=app.state.sessions.bot.name,
                                msg=cmd["resp"],
                                recipient=t_chan.name,
                                sender_id=app.state.sessions.bot.id,
                            ),
                        )

        else:
            # no commands were triggered

            # check if the user is /np'ing a map.
            # even though this is a public channel,
            # we'll update the player's last np stored.
            r_match = NOW_PLAYING_RGX.match(msg)
            if r_match:
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
                        mode_vn = osu_session["status"]["mode"].as_vanilla

                    # parse the mods from regex
                    mods = None
                    if r_match["mods"] is not None:
                        mods = Mods.from_np(r_match["mods"][1:], mode_vn)

                    osu_session["last_np"] = {
                        "beatmap_id": bmap.id,
                        "mods": mods,
                        "mode_vn": mode_vn,
                        "timeout": time.time() + 300,  # /np's last 5mins
                    }
                else:
                    # time out their previous /np
                    osu_session["last_np"] = None

            channel_memberships = await channel_memberships_repo.fetch_all(
                channel_name=t_chan.name,
            )

            await osu_sessions_repo.multicast_osu_data(
                target_session_ids={p["session_id"] for p in channel_memberships},
                data=app.packets.send_message(
                    sender=osu_session["name"],
                    msg=msg,
                    recipient=t_chan.name,
                    sender_id=osu_session["user_id"],
                ),
            )

        maybe_session = await users_repo.partial_update(
            id=osu_session["user_id"],
            latest_activity=int(time.time()),
        )
        assert maybe_session is not None
        osu_session = maybe_session

        log(
            f"User {osu_session['user_id']} @ {t_chan}: {msg}",
            Ansi.LCYAN,
            file=".data/logs/chat.log",
        )


@register(ClientPackets.LOGOUT, restricted=True)
class Logout(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        reader.read_i32()  # reserved

    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        if (time.time() - osu_session["login_time"]) < 1:
            # osu! has a weird tendency to log out immediately after login.
            # i've tested the times and they're generally 300-800ms, so
            # we'll block any logout request within 1 second from login.
            return

        await osu_sessions_usecases.logout(osu_session)

        await users_repo.partial_update(
            id=osu_session["user_id"],
            latest_activity=int(time.time()),
        )


@register(ClientPackets.REQUEST_STATUS_UPDATE, restricted=True)
class StatsUpdateRequest(BasePacket):
    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        user_stats = await stats_repo.fetch_one(
            player_id=osu_session["user_id"],
            mode=int(osu_session["status"]["mode"]),
        )
        assert user_stats is not None

        global_rank = await stats_repo.get_global_rank(
            user_id=osu_session["user_id"],
            mode=osu_session["status"]["mode"],
        )

        await osu_sessions_repo.unicast_osu_data(
            target_session_id=osu_session["session_id"],
            data=app.packets.user_stats(
                user_id=osu_session["user_id"],
                action=int(osu_session["status"]["action"]),
                info_text=osu_session["status"]["info_text"],
                map_md5=osu_session["status"]["map_md5"],
                mods=int(osu_session["status"]["mods"]),
                mode=int(osu_session["status"]["mode"]),
                map_id=osu_session["status"]["map_id"],
                ranked_score=user_stats["rscore"],
                accuracy=user_stats["acc"],
                plays=user_stats["plays"],
                total_score=user_stats["tscore"],
                global_rank=global_rank,
                pp=user_stats["pp"],
            ),
        )


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


def parse_osu_version_string(osu_version_string: str) -> OsuVersion | None:
    match = regexes.OSU_VERSION.match(osu_version_string)
    if match is None:
        return None

    osu_version = OsuVersion(
        date=date(
            year=int(match["date"][0:4]),
            month=int(match["date"][4:6]),
            day=int(match["date"][6:8]),
        ),
        revision=int(match["revision"]) if match["revision"] else None,
        stream=OsuStream(match["stream"] or "stable"),
    )
    return osu_version


async def get_allowed_client_versions(osu_stream: OsuStream) -> set[date] | None:
    """
    Return a list of acceptable client versions for the given stream.

    This is used to determine whether a client is too old to connect to the server.

    Returns None if the connection to the osu! api fails.
    """
    osu_stream_str = osu_stream.value
    if osu_stream in (OsuStream.STABLE, OsuStream.BETA):
        osu_stream_str += "40"  # i wonder why this exists

    response = await services.http_client.get(
        OSU_API_V2_CHANGELOG_URL,
        params={"stream": osu_stream_str},
    )
    if not response.is_success:
        return None

    allowed_client_versions: set[date] = set()
    for build in response.json()["builds"]:
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

    return allowed_client_versions


def parse_adapters_string(adapters_string: str) -> tuple[list[str], bool]:
    running_under_wine = adapters_string == "runningunderwine"
    adapters = adapters_string[:-1].split(".")
    return adapters, running_under_wine


async def authenticate(
    username: str,
    untrusted_password: bytes,
) -> users_repo.User | None:
    user_info = await users_repo.fetch_one(
        name=username,
        fetch_all_fields=True,
    )
    if user_info is None:
        return None

    trusted_hashword = user_info["pw_bcrypt"].encode()

    # in-memory bcrypt lookup cache for performance
    if trusted_hashword in app.state.cache.bcrypt:  # ~0.01 ms
        if untrusted_password != app.state.cache.bcrypt[trusted_hashword]:
            return None
    else:  # ~200ms
        if not bcrypt.checkpw(untrusted_password, trusted_hashword):
            return None

        app.state.cache.bcrypt[trusted_hashword] = untrusted_password

    return user_info


async def handle_osu_login_request(
    headers: Mapping[str, str],
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

    osu_version = parse_osu_version_string(login_data["osu_version"])
    if osu_version is None:
        return {
            "osu_token": "invalid-request",
            "response_body": (
                app.packets.login_reply(LoginFailureReason.AUTHORIZATION_FAILED)
                + app.packets.notification("Please restart your osu! and try again.")
            ),
        }

    if app.settings.DISALLOW_OLD_CLIENTS:
        allowed_client_versions = await get_allowed_client_versions(
            osu_version.stream,
        )
        # in the case where the osu! api fails, we'll allow the client to connect
        if (
            allowed_client_versions is not None
            and osu_version.date not in allowed_client_versions
        ):
            return {
                "osu_token": "client-too-old",
                "response_body": (
                    app.packets.version_update()
                    + app.packets.login_reply(LoginFailureReason.OLD_CLIENT)
                ),
            }

    adapters, running_under_wine = parse_adapters_string(login_data["adapters_str"])
    if not (running_under_wine or any(adapters)):
        return {
            "osu_token": "empty-adapters",
            "response_body": (
                app.packets.login_reply(LoginFailureReason.AUTHORIZATION_FAILED)
                + app.packets.notification("Please restart your osu! and try again.")
            ),
        }

    ## parsing successful

    login_time = time.time()

    # disallow multiple sessions from a single user
    # with the exception of tourney spectator clients
    if osu_version.stream is not OsuStream.TOURNEY:
        existing_osu_session = await osu_sessions_repo.fetch_main_user_session(
            username=login_data["username"],
        )
        if existing_osu_session is not None:
            # check if the existing session is still active
            if (login_time - existing_osu_session["last_recv_time"]) < 10:
                return {
                    "osu_token": "session-already-exists",
                    "response_body": (
                        app.packets.login_reply(LoginFailureReason.AUTHORIZATION_FAILED)
                        + app.packets.notification(
                            "You already have an active session.",
                        )
                    ),
                }
            else:
                # the existing session is not active; allow this login to replace it
                await osu_sessions_usecases.logout(existing_osu_session)

    user_info = await authenticate(login_data["username"], login_data["password_md5"])
    if user_info is None:
        return {
            "osu_token": "incorrect-credentials",
            "response_body": (
                app.packets.notification(f"{BASE_DOMAIN}: Incorrect credentials")
                + app.packets.login_reply(LoginFailureReason.AUTHORIZATION_FAILED)
            ),
        }

    if osu_version.stream is OsuStream.TOURNEY and not (
        user_info["priv"] & Privileges.DONATOR
        and user_info["priv"] & Privileges.UNRESTRICTED
    ):
        # trying to use tourney client with insufficient privileges.
        return {
            "osu_token": "no",
            "response_body": app.packets.login_reply(
                LoginFailureReason.AUTHORIZATION_FAILED,
            ),
        }

    """ login credentials verified """

    await logins_repo.create(
        user_id=user_info["id"],
        ip=str(ip),
        osu_ver=osu_version.date,
        osu_stream=osu_version.stream,
    )

    await client_hashes_repo.create(
        userid=user_info["id"],
        osupath=login_data["osu_path_md5"],
        adapters=login_data["adapters_md5"],
        uninstall_id=login_data["uninstall_md5"],
        disk_serial=login_data["disk_signature_md5"],
    )

    # TODO: store adapters individually

    hw_matches = await client_hashes_repo.fetch_any_hardware_matches_for_user(
        userid=user_info["id"],
        running_under_wine=running_under_wine,
        adapters=login_data["adapters_md5"],
        uninstall_id=login_data["uninstall_md5"],
        disk_serial=login_data["disk_signature_md5"],
    )

    if hw_matches:
        # we have other accounts with matching hashes
        if has_verified_account(user_info["priv"]):
            # there are hwid matches for this *existing* account that's being authorized.
            # this may be a multi-accounting situation; we'll allow it for now.

            # TODO: what would be the ideal behaviour here?
            # logging for sure, would we ever want to restrict?
            ...
        else:
            # there are hwid matches for this *new* account that's being authorized.
            if any(is_restricted(hw_match["priv"]) for hw_match in hw_matches):
                # some of the existing users are restricted; do not authorize the login.
                return {
                    "osu_token": "contact-staff",
                    "response_body": (
                        app.packets.notification(
                            "Please contact staff directly to create an account.",
                        )
                        + app.packets.login_reply(
                            LoginFailureReason.AUTHORIZATION_FAILED,
                        )
                    ),
                }

    """ All checks passed, player is safe to login """

    # get clan & clan priv if we're in a clan
    clan_id: int | None = None
    clan_priv: ClanPrivileges | None = None
    if user_info["clan_id"] != 0:
        clan_id = user_info["clan_id"]
        clan_priv = ClanPrivileges(user_info["clan_priv"])

    db_country = user_info["country"]

    geoloc = await app.state.services.fetch_geoloc(ip, headers)

    if geoloc is None:
        return {
            "osu_token": "login-failed",
            "response_body": (
                app.packets.notification(
                    f"{BASE_DOMAIN}: Login failed. Please contact an admin.",
                )
                + app.packets.login_reply(LoginFailureReason.AUTHORIZATION_FAILED)
            ),
        }

    if db_country == "xx":
        # bugfix for old bancho.py versions when
        # country wasn't stored on registration.
        log(f"Fixing {login_data['username']}'s country.", Ansi.LGREEN)

        maybe_user = await users_repo.partial_update(
            id=user_info["id"],
            country=geoloc["country"]["acronym"],
        )
        assert maybe_user is not None
        user_info = maybe_user

    client_details = ClientDetails(
        osu_version=osu_version,
        osu_path_md5=login_data["osu_path_md5"],
        adapters_md5=login_data["adapters_md5"],
        uninstall_md5=login_data["uninstall_md5"],
        disk_signature_md5=login_data["disk_signature_md5"],
        adapters=adapters,
        ip=ip,
    )

    # add `p` to the global player list,
    # making them officially logged in.
    osu_session = await osu_sessions_repo.create(
        user_id=user_info["id"],
        name=user_info["name"],
        priv=Privileges(user_info["priv"]),
        pw_bcrypt=user_info["pw_bcrypt"].encode(),
        session_id=Player.generate_token(),
        clan_id=clan_id,
        clan_priv=clan_priv,
        geoloc=geoloc,
        utc_offset=login_data["utc_offset"],
        pm_private=login_data["pm_private"],
        silence_end=user_info["silence_end"],
        donor_end=user_info["donor_end"],
        client_details=client_details,
        login_time=login_time,
        last_recv_time=login_time,
        is_bot_client=False,
        is_tourney_client=osu_version.stream is OsuStream.TOURNEY,
        api_key=user_info["api_key"],
    )

    # we'll need the rest of the osu sessions online a couple of times.
    all_other_osu_sessions = await osu_sessions_repo.fetch_all()

    packet_data_for_user = bytearray(app.packets.protocol_version(19))
    packet_data_for_user += app.packets.login_reply(osu_session["user_id"])

    # *real* client privileges are sent with this packet,
    # then the user's apparent privileges are sent in the
    # userPresence packets to other players. we'll send
    # supporter along with the user's privileges here,
    # but not in userPresence (so that only donators
    # show up with the yellow name in-game, but everyone
    # gets osu!direct & other in-game perks).
    packet_data_for_user += app.packets.bancho_privileges(
        get_client_privileges(osu_session["priv"]) | ClientPrivileges.SUPPORTER,
    )

    packet_data_for_user += WELCOME_NOTIFICATION

    # send all appropriate channel info to our player.
    # the osu! client will attempt to join the channels.
    auto_join_channels = await channels_repo.fetch_many(
        auto_join=True,
        page=None,
        page_size=None,
    )
    for channel in auto_join_channels:
        user_can_read_channel = (
            not channel["read_priv"] or osu_session["priv"] & channel["read_priv"] != 0
        )
        if (
            not user_can_read_channel
            or channel["name"] == "#lobby"  # (can't be in mp lobby @ login)
        ):
            continue

        # send chan info to all players who can see
        # the channel (to update their playercounts)
        channel_memberships = await channel_memberships_repo.fetch_all(
            channel_name=channel["name"],
        )
        chan_info_packet = app.packets.channel_info(
            channel["name"],
            channel["topic"],
            len(channel_memberships),
        )

        packet_data_for_user += chan_info_packet

        for other_session in all_other_osu_sessions:
            other_osu_session_can_read_channel = (
                not channel["read_priv"]
                or other_session["priv"] & channel["read_priv"] != 0
            )
            if other_osu_session_can_read_channel:
                await osu_sessions_repo.unicast_osu_data(
                    target_session_id=other_session["session_id"],
                    data=chan_info_packet,
                )

    # tells osu! to reorder channels based on config.
    packet_data_for_user += app.packets.channel_info_end()

    # TODO: fetch player.recent_scores from sql

    packet_data_for_user += app.packets.main_menu_icon(
        icon_url=app.settings.MENU_ICON_URL,
        onclick_url=app.settings.MENU_ONCLICK_URL,
    )

    user_friends = await relationships_repo.fetch_related_users(
        user_id=user_info["id"],
        relationship_type=RelationshipType.FRIEND,
    )
    packet_data_for_user += app.packets.friends_list([r["user2"] for r in user_friends])
    packet_data_for_user += app.packets.silence_end(
        max(0, int(user_info["silence_end"] - time.time())),
    )

    global_rank = await stats_repo.get_global_rank(
        user_id=user_info["id"],
        mode=osu_session["status"]["mode"],
    )

    user_stats = await stats_repo.fetch_one(
        player_id=user_info["id"],
        mode=osu_session["status"]["mode"],
    )
    assert user_stats is not None

    # there are a couple of packets we want to send to all osu sessions.
    # notably, the newly authorized user's presence & stats.
    packet_data_for_broadcast = app.packets.user_presence(
        user_id=user_info["id"],
        name=user_info["name"],
        utc_offset=login_data["utc_offset"],
        country_code=osu_session["geoloc"]["country"]["numeric"],
        bancho_privileges=get_client_privileges(user_info["priv"]),
        mode=osu_session["status"]["mode"],
        latitude=int(osu_session["geoloc"]["longitude"]),
        longitude=int(osu_session["geoloc"]["latitude"]),
        global_rank=global_rank,
    )
    packet_data_for_broadcast += app.packets.user_stats(
        user_id=osu_session["user_id"],
        action=int(osu_session["status"]["action"]),
        info_text=osu_session["status"]["info_text"],
        map_md5=osu_session["status"]["map_md5"],
        mods=int(osu_session["status"]["mods"]),
        mode=int(osu_session["status"]["mode"]),
        map_id=osu_session["status"]["map_id"],
        ranked_score=user_stats["rscore"],
        accuracy=user_stats["acc"],
        plays=user_stats["plays"],
        total_score=user_stats["tscore"],
        global_rank=global_rank,
        pp=user_stats["pp"],
    )

    packet_data_for_user += packet_data_for_broadcast

    for other_session in all_other_osu_sessions:
        if is_restricted(other_session["priv"]):
            continue

        # enqueue their information to us
        if other_session["user_id"] == builtin_bot.BOT_USER_ID:
            packet_data_for_user += builtin_bot.bot_user_presence()
            packet_data_for_user += builtin_bot.bot_user_stats()
        else:
            other_user_stats = await stats_repo.fetch_one(
                player_id=other_session["user_id"],
                mode=other_session["status"]["mode"],
            )
            other_user_global_rank = await stats_repo.get_global_rank(
                user_id=other_session["user_id"],
                mode=other_session["status"]["mode"],
            )
            assert other_user_stats is not None

            packet_data_for_user += app.packets.user_presence(
                user_id=other_session["user_id"],
                name=other_session["name"],
                utc_offset=other_session["utc_offset"],
                country_code=osu_session["geoloc"]["country"]["numeric"],
                bancho_privileges=get_client_privileges(other_session["priv"]),
                mode=other_session["status"]["mode"],
                latitude=int(osu_session["geoloc"]["longitude"]),
                longitude=int(osu_session["geoloc"]["latitude"]),
                global_rank=other_user_global_rank,
            )
            packet_data_for_user += app.packets.user_stats(
                user_id=other_session["user_id"],
                action=int(other_session["status"]["action"]),
                info_text=other_session["status"]["info_text"],
                map_md5=other_session["status"]["map_md5"],
                mods=int(other_session["status"]["mods"]),
                mode=int(other_session["status"]["mode"]),
                map_id=other_session["status"]["map_id"],
                ranked_score=other_user_stats["rscore"],
                accuracy=other_user_stats["acc"],
                plays=other_user_stats["plays"],
                total_score=other_user_stats["tscore"],
                global_rank=other_user_global_rank,
                pp=other_user_stats["pp"],
            )

        # enqueue our information to them
        if not is_restricted(user_info["priv"]):
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=other_session["session_id"],
                data=packet_data_for_broadcast,
            )

    # the player may have been sent mail while offline,
    # enqueue any messages from their respective authors.
    mail_rows = await mail_repo.fetch_all_mail_to_user(
        user_id=osu_session["user_id"],
        unread_only=True,
    )
    mail_received_from: set[int] = set()
    for msg in mail_rows:
        # Add "Unread messages" header as the first message
        # for any given sender, to make it clear that the
        # messages are coming from the mail system.
        if msg["from_id"] not in mail_received_from:
            packet_data_for_user += app.packets.send_message(
                sender=msg["from_name"],
                msg="Unread messages",
                recipient=msg["to_name"],
                sender_id=msg["from_id"],
            )
            mail_received_from.add(msg["from_id"])

        msg_time = datetime.fromtimestamp(msg["time"])
        packet_data_for_user += app.packets.send_message(
            sender=msg["from_name"],
            msg=f'[{msg_time:%a %b %d @ %H:%M%p}] {msg["msg"]}',
            recipient=msg["to_name"],
            sender_id=msg["from_id"],
        )

    if not has_verified_account(osu_session["priv"]):
        # this is the player's first login, verify their
        # account & send info about the server/its usage.
        await users_usecases.add_privileges(
            user_id=osu_session["user_id"],
            privileges_to_add=Privileges.VERIFIED,
        )

        if osu_session["user_id"] == FIRST_USER_ID:
            # this is the first player registering on
            # the server, grant them full privileges.
            privileges_to_add = (
                Privileges.STAFF
                | Privileges.NOMINATOR
                | Privileges.WHITELISTED
                | Privileges.TOURNEY_MANAGER
                | Privileges.DONATOR
                | Privileges.ALUMNI
            )
            await users_usecases.add_privileges(
                user_id=osu_session["user_id"],
                privileges_to_add=privileges_to_add,
            )
            osu_session["priv"] |= privileges_to_add
            user_info["priv"] |= privileges_to_add

        packet_data_for_user += app.packets.send_message(
            sender=app.state.sessions.bot.name,
            msg=WELCOME_MSG,
            recipient=osu_session["name"],
            sender_id=app.state.sessions.bot.id,
        )

    if is_restricted(user_info["priv"]):
        packet_data_for_user += app.packets.account_restricted()
        packet_data_for_user += app.packets.send_message(
            sender=builtin_bot.BOT_USER_NAME,
            msg=RESTRICTED_MSG,
            recipient=user_info["name"],
            sender_id=builtin_bot.BOT_USER_ID,
        )

    if app.state.services.datadog:
        if not is_restricted(user_info["priv"]):
            app.state.services.datadog.increment("bancho.online_players")

        time_taken = time.time() - login_time
        app.state.services.datadog.histogram("bancho.login_time", time_taken)

    user_os = "unix (wine)" if running_under_wine else "win32"
    country_code = osu_session["geoloc"]["country"]["acronym"].upper()

    log(
        f"User {osu_session['user_id']} logged in from {country_code} using {login_data['osu_version']} on {user_os}",
        Ansi.LCYAN,
    )

    maybe_user = await users_repo.partial_update(
        id=osu_session["user_id"],
        latest_activity=int(time.time()),
    )
    assert maybe_user is not None
    user_info = maybe_user

    return {
        "osu_token": osu_session["session_id"],
        "response_body": bytes(packet_data_for_user),
    }


@register(ClientPackets.START_SPECTATING)
class StartSpectating(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.target_id = reader.read_i32()

    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        new_host_session = await osu_sessions_repo.fetch_main_user_session(
            user_id=self.target_id,
        )
        if new_host_session is None:
            log(
                f"User {osu_session['user_id']} tried to spectate nonexistant id {self.target_id}.",
                Ansi.LYELLOW,
            )
            return

        if osu_session["spectating_session_id"] is not None:
            current_host_session = await osu_sessions_repo.fetch_one(
                session_id=osu_session["spectating_session_id"],
            )
            assert current_host_session is not None
            if current_host_session["user_id"] == new_host_session["user_id"]:
                # this happens when a user is spectating someone,
                # doesn't have the map, then downloads it
                # (it reconnects the spectator session)
                await osu_sessions_repo.unicast_osu_data(
                    target_session_id=new_host_session["session_id"],
                    data=app.packets.spectator_joined(osu_session["user_id"]),
                )
                await osu_sessions_repo.multicast_osu_data(
                    target_session_ids=new_host_session["spectator_session_ids"],
                    data=app.packets.fellow_spectator_joined(osu_session["user_id"]),
                )

                return

            error = await users_usecases.remove_spectator(
                host_session_id=current_host_session["session_id"],
                spectator_session_id=osu_session["session_id"],
            )
            if error is not None:
                log(f"Error removing spectator: {error}", Ansi.LRED)
                return

        error = await users_usecases.add_spectator(
            host_session_id=new_host_session["session_id"],
            spectator_session_id=osu_session["session_id"],
        )
        if error is not None:
            log(f"Error adding spectator: {error}", Ansi.LRED)
            return


@register(ClientPackets.STOP_SPECTATING)
class StopSpectating(BasePacket):
    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        host_session_id = osu_session["spectating_session_id"]
        if host_session_id is None:
            log(
                f"User {osu_session['user_id']} tried to stop spectating when we have no record of them spectating anyone",
                Ansi.LRED,
            )
            return

        error = await users_usecases.remove_spectator(
            host_session_id=host_session_id,
            spectator_session_id=osu_session["session_id"],
        )
        if error is not None:
            log(f"Error removing spectator: {error}", Ansi.LRED)
            return


@register(ClientPackets.SPECTATE_FRAMES)
class SpectateFrames(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.frame_bundle = reader.read_replayframe_bundle()

    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        # TODO: perform validations on the parsed frame bundle
        # to ensure it's not being tamperated with or weaponized.

        # NOTE: this is given a fastpath here for efficiency due to the
        # sheer rate of usage of these packets in spectator mode.
        # data_for_spectators = (
        #     app.packets.spectateFrames(self.frame_bundle.raw_data)
        # )
        data_for_spectators = (
            struct.pack("<HxI", 15, len(self.frame_bundle.raw_data))
            + self.frame_bundle.raw_data
        )

        await osu_sessions_repo.multicast_osu_data(
            target_session_ids=osu_session["spectator_session_ids"],
            data=data_for_spectators,
        )


@register(ClientPackets.CANT_SPECTATE)
class CantSpectate(BasePacket):
    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        if not osu_session["spectating_session_id"]:
            log(
                f"User {osu_session['user_id']} sent that they can't spectate but we have no record of them spectating anyone.",
                Ansi.LRED,
            )
            return

        host = await osu_sessions_repo.fetch_one(
            session_id=osu_session["spectating_session_id"],
        )
        assert host is not None

        data = app.packets.spectator_cant_spectate(osu_session["user_id"])

        await osu_sessions_repo.unicast_osu_data(
            target_session_id=host["session_id"],
            data=data,
        )
        await osu_sessions_repo.multicast_osu_data(
            target_session_ids=host["spectator_session_ids"],
            data=data,
        )


@register(ClientPackets.SEND_PRIVATE_MESSAGE)
class SendPrivateMessage(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.msg = reader.read_message()

    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        if is_silenced(osu_session["silence_end"]):
            if app.settings.DEBUG:
                log(
                    f"User {osu_session['user_id']} tried to send a dm while silenced.",
                    Ansi.LYELLOW,
                )
            return

        # remove leading/trailing whitespace
        msg = self.msg.text.strip()

        if not msg:
            return

        target_name = self.msg.recipient

        # allow this to get from sql - players can receive
        # messages offline, due to the mail system. B)
        target_session = await osu_sessions_repo.fetch_main_user_session(
            username=target_name,
        )
        if target_session is None:
            # Target user is offline or non-existent
            return

        if osu_session["user_id"] in target_session["blocked_ids"]:
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=osu_session["session_id"],
                data=app.packets.user_dm_blocked(target_name),
            )

            if app.settings.DEBUG:
                log(
                    f"User {osu_session['user_id']} tried to message {target_session['user_id']}, but they have them blocked.",
                )
            return

        if (
            target_session["pm_private"]
            and osu_session["user_id"] not in target_session["friend_ids"]
        ):
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=osu_session["session_id"],
                data=app.packets.user_dm_blocked(target_name),
            )

            if app.settings.DEBUG:
                log(
                    f"User {osu_session['user_id']} tried to message {target_session['user_id']}, but they are blocking dms.",
                )
            return

        if is_silenced(target_session["silence_end"]):
            # if target is silenced, inform player.
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=osu_session["session_id"],
                data=app.packets.target_silenced(target_name),
            )

            if app.settings.DEBUG:
                log(
                    f"User {osu_session['user_id']} tried to message {target_session['user_id']}, but they are silenced.",
                )
            return

        # limit message length to 2k chars
        # perhaps this could be dangerous with !py..?
        if len(msg) > 2000:
            msg = f"{msg[:2000]}... (truncated)"
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=osu_session["session_id"],
                data=app.packets.notification(
                    "Your message was truncated\n(exceeded 2000 characters).",
                ),
            )

        if (
            target_session["status"]["action"] is Action.Afk
            and target_session["away_msg"]
        ):
            # send away message if target is afk and has one set.
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=osu_session["session_id"],
                data=app.packets.send_message(
                    sender=target_session["name"],
                    msg=target_session["away_msg"],
                    recipient=osu_session["name"],
                    sender_id=target_session["user_id"],
                ),
            )

        if target_session is not app.state.sessions.bot:
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=target_session["session_id"],
                data=app.packets.send_message(
                    sender=osu_session["name"],
                    msg=msg,
                    recipient=target_session["name"],
                    sender_id=osu_session["user_id"],
                ),
            )

            # insert mail into db, marked as unread.
            await mail_repo.create(
                from_id=osu_session["user_id"],
                to_id=target_session["user_id"],
                msg=msg,
            )
        else:
            # messaging the bot, check for commands & /np.
            if msg.startswith(app.settings.COMMAND_PREFIX):
                cmd = await commands.process_commands(
                    osu_session,
                    target_session,
                    msg,
                )
            else:
                cmd = None

            if cmd:
                # command triggered, send response if any.
                if cmd["resp"] is not None:
                    await osu_sessions_repo.unicast_osu_data(
                        target_session_id=osu_session["session_id"],
                        data=app.packets.send_message(
                            sender=target_session["name"],
                            msg=cmd["resp"],
                            recipient=osu_session["name"],
                            sender_id=target_session["user_id"],
                        ),
                    )
            else:
                # no commands triggered.
                r_match = NOW_PLAYING_RGX.match(msg)
                if r_match:
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
                            mode_vn = osu_session["status"]["mode"].as_vanilla

                        # parse the mods from regex
                        mods = None
                        if r_match["mods"] is not None:
                            mods = Mods.from_np(r_match["mods"][1:], mode_vn)

                        maybe_session = await osu_sessions_repo.partial_update(
                            session_id=osu_session["session_id"],
                            last_np={
                                "beatmap_id": bmap.id,
                                "mode_vn": mode_vn,
                                "mods": mods,
                                "timeout": time.time() + 300,  # /np's last 5mins
                            },
                        )
                        assert maybe_session is not None
                        osu_session = maybe_session

                        # calculate generic pp values from their /np

                        osu_file_available = await ensure_osu_file_is_available(
                            bmap.id,
                            expected_md5=bmap.md5,
                        )
                        if not osu_file_available:
                            resp_msg = (
                                "Mapfile could not be found; "
                                "this incident has been reported."
                            )
                        else:
                            # calculate pp for common generic values
                            pp_calc_st = time.time_ns()

                            mods = None
                            if r_match["mods"] is not None:
                                # [1:] to remove leading whitespace
                                mods_str = r_match["mods"][1:]
                                mods = Mods.from_np(mods_str, mode_vn)

                            scores = [
                                ScoreParams(
                                    mode=mode_vn,
                                    mods=int(mods) if mods else None,
                                    acc=acc,
                                )
                                for acc in app.settings.PP_CACHED_ACCURACIES
                            ]

                            results = app.usecases.performance.calculate_performances(
                                osu_file_path=str(BEATMAPS_PATH / f"{bmap.id}.osu"),
                                scores=scores,
                            )

                            resp_msg = " | ".join(
                                f"{acc}%: {result['performance']['pp']:,.2f}pp"
                                for acc, result in zip(
                                    app.settings.PP_CACHED_ACCURACIES,
                                    results,
                                )
                            )

                            elapsed = time.time_ns() - pp_calc_st
                            resp_msg += f" | Elapsed: {magnitude_fmt_time(elapsed)}"
                    else:
                        resp_msg = "Could not find map."

                        # time out their previous /np
                        maybe_session = await osu_sessions_repo.partial_update(
                            session_id=osu_session["session_id"],
                            last_np=None,
                        )
                        assert maybe_session is not None
                        osu_session = maybe_session

                    await osu_sessions_repo.unicast_osu_data(
                        target_session_id=osu_session["session_id"],
                        data=app.packets.send_message(
                            sender=target_session["name"],
                            msg=resp_msg,
                            recipient=osu_session["name"],
                            sender_id=target_session["user_id"],
                        ),
                    )

        await users_repo.partial_update(
            id=osu_session["user_id"],
            latest_activity=int(time.time()),
        )

        log(
            f"{osu_session['user_id']} @ {target_session['user_id']}: {msg}",
            Ansi.LCYAN,
            file=".data/logs/chat.log",
        )


@register(ClientPackets.PART_LOBBY)
class LobbyPart(BasePacket):
    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        maybe_session = await osu_sessions_repo.partial_update(
            session_id=osu_session["session_id"],
            in_lobby=False,
        )
        assert maybe_session is not None
        osu_session = maybe_session


@register(ClientPackets.JOIN_LOBBY)
class LobbyJoin(BasePacket):
    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        maybe_session = await osu_sessions_repo.partial_update(
            session_id=osu_session["session_id"],
            in_lobby=True,
        )
        assert maybe_session is not None
        osu_session = maybe_session

        for match in app.state.sessions.matches:
            if match is None:
                continue

            try:
                await osu_sessions_repo.unicast_osu_data(
                    target_session_id=osu_session["session_id"],
                    data=app.packets.new_match(
                        match_id=match.id,
                        in_progress=match.in_progress,
                        mods=match.mods,
                        name=match.name,
                        passwd=match.passwd,
                        map_name=match.map_name,
                        map_id=match.map_id,
                        map_md5=match.map_md5,
                        slot_statuses=[s.status for s in match.slots],
                        slot_teams=[s.team for s in match.slots],
                        slot_user_ids=[
                            s.player.id if s.player else None for s in match.slots
                        ],
                        host_id=match.host_id,
                        mode=match.mode,
                        win_condition=match.win_condition,
                        team_type=match.team_type,
                        freemods=match.freemods,
                        slot_mods=[s.mods for s in match.slots],
                        seed=match.seed,
                        include_plaintext_password_in_data=False,
                    ),
                )
            except ValueError:
                log(
                    f"Failed to send match {match.id} to player joining lobby; likely due to missing host",
                    Ansi.LYELLOW,
                )
                stacktrace = app.utils.get_appropriate_stacktrace()
                await app.state.services.log_strange_occurrence(stacktrace)
                continue


def validate_match_data(
    untrusted_match_data: app.packets.MultiplayerMatch,
    expected_host_id: int,
) -> bool:
    return all(
        (
            untrusted_match_data.host_id == expected_host_id,
            len(untrusted_match_data.name) <= MAX_MATCH_NAME_LENGTH,
        ),
    )


@register(ClientPackets.CREATE_MATCH)
class MatchCreate(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match_data = reader.read_match()

    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        if not validate_match_data(
            self.match_data,
            expected_host_id=osu_session["user_id"],
        ):
            log(
                f"User {osu_session['user_id']} tried to create a match with invalid data.",
                Ansi.LYELLOW,
            )
            return

        if is_restricted(osu_session["priv"]):
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=osu_session["session_id"],
                data=app.packets.match_join_fail()
                + app.packets.notification(
                    "Multiplayer is not available while restricted.",
                ),
            )
            return

        if is_silenced(osu_session["silence_end"]):
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=osu_session["session_id"],
                data=app.packets.match_join_fail()
                + app.packets.notification(
                    "Multiplayer is not available while silenced.",
                ),
            )
            return

        match_id = await matches_repo.reserve_new_match_id()

        multiplayer_channel = await channels_repo.create(
            name=f"#multi_{match_id}",
            topic=f"MID {match_id}'s multiplayer channel.",
            read_priv=Privileges.UNRESTRICTED,
            write_priv=Privileges.UNRESTRICTED,
            auto_join=False,
            instance=True,
        )

        match = await matches_repo.create(
            match_id=match_id,
            name=self.match_data.name,
            password=self.match_data.password.removesuffix("//private"),
            has_public_history=not self.match_data.password.endswith("//private"),
            map_name=self.match_data.map_name,
            map_id=self.match_data.map_id,
            map_md5=self.match_data.map_md5,
            host_id=self.match_data.host_id,
            mode=GameMode(self.match_data.mode),
            mods=Mods(self.match_data.mods),
            win_condition=MatchWinConditions(self.match_data.win_condition),
            team_type=MatchTeamTypes(self.match_data.team_type),
            freemods=self.match_data.freemods,
            seed=self.match_data.seed,
            in_progress=False,
            starting=None,
            tourney_pool_id=None,
            is_scrimming=False,
            team_match_points=defaultdict(int),
            ffa_match_points=defaultdict(int),
            bans=set(),
            winning_pts=0,
            use_pp_scoring=False,
            tourney_client_user_ids=set(),
            referees=set(),
        )

        error = await users_usecases.join_multiplayer_match(
            session_id=osu_session["session_id"],
            multiplayer_match_id=match_id,
            untrusted_password=self.match_data.password,
        )
        if error is not None:
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=osu_session["session_id"],
                data=app.packets.match_join_fail(),
            )
            return

        match_slots = await match_slots_repo.fetch_all_for_match(
            match_id=match["match_id"],
        )
        slot_statuses: list[int] = []
        slot_teams: list[int] = []
        slot_user_ids: list[int | None] = []
        slot_mods: list[int] = []
        for slot_id in range(16):
            slot = match_slots.get(str(slot_id))
            if slot is not None:
                slot_statuses.append(slot["status"].value)
                slot_teams.append(slot["team"].value)
                slot_user_ids.append(slot["user_id"])
                slot_mods.append(slot["mods"].value)
            else:
                slot_statuses.append(SlotStatus.OPEN.value)
                slot_teams.append(MatchTeams.NEUTRAL.value)
                slot_user_ids.append(None)
                slot_mods.append(Mods.NOMOD.value)

        await osu_sessions_repo.unicast_osu_data(
            target_session_id=osu_session["session_id"],
            data=app.packets.match_join_success(
                match_id=match["match_id"],
                in_progress=match["in_progress"],
                mods=match["mods"],
                name=match["name"],
                passwd=match["password"],
                map_name=match["map_name"],
                map_id=match["map_id"],
                map_md5=match["map_md5"],
                slot_statuses=slot_statuses,
                slot_teams=slot_teams,
                slot_user_ids=slot_user_ids,
                host_id=match["host_id"],
                mode=match["mode"],
                win_condition=match["win_condition"],
                team_type=match["team_type"],
                freemods=match["freemods"],
                slot_mods=slot_mods,
                seed=match["seed"],
                include_plaintext_password_in_data=True,
            ),
        )

        # enqueue match state to all new users in the match & #lobby
        lobby_channel_memberships = await channel_memberships_repo.fetch_all(
            channel_name="#lobby",
        )
        await osu_sessions_repo.multicast_osu_data(
            target_session_ids=(
                {m["session_id"] for m in lobby_channel_memberships}
                | {osu_session["session_id"]}
            ),
            data=app.packets.update_match(
                match_id=match["match_id"],
                in_progress=match["in_progress"],
                mods=match["mods"],
                name=match["name"],
                passwd=match["password"],
                map_name=match["map_name"],
                map_id=match["map_id"],
                map_md5=match["map_md5"],
                slot_statuses=slot_statuses,
                slot_teams=slot_teams,
                slot_user_ids=slot_user_ids,
                host_id=match["host_id"],
                mode=match["mode"],
                win_condition=match["win_condition"],
                team_type=match["team_type"],
                freemods=match["freemods"],
                slot_mods=slot_mods,
                seed=match["seed"],
                include_plaintext_password_in_data=False,
            ),
        )

        await osu_sessions_repo.unicast_osu_data(
            target_session_id=osu_session["session_id"],
            data=app.packets.send_message(
                sender=builtin_bot.BOT_USER_NAME,
                msg="Match created.",  # TODO: mp links
                recipient=osu_session["name"],
                sender_id=builtin_bot.BOT_USER_ID,
            ),
        )

        # update user's latest activity
        await users_repo.partial_update(
            id=osu_session["user_id"],
            latest_activity=int(time.time()),
        )

        log(f"User {osu_session['user_id']} created a new multiplayer match.")


@register(ClientPackets.JOIN_MATCH)
class MatchJoin(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match_id = reader.read_i32()
        self.match_passwd = reader.read_string()

    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        match = await matches_repo.fetch_one(match_id=self.match_id)
        if match is None:
            log(f"{osu_session} tried to join a non-existant mp lobby?")
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=osu_session["session_id"],
                data=app.packets.match_join_fail(),
            )
            return

        if is_restricted(osu_session["priv"]):
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=osu_session["session_id"],
                data=(
                    app.packets.match_join_fail()
                    + app.packets.notification(
                        "Multiplayer is not available while restricted.",
                    )
                ),
            )
            return

        if is_silenced(osu_session["silence_end"]):
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=osu_session["session_id"],
                data=(
                    app.packets.match_join_fail()
                    + app.packets.notification(
                        "Multiplayer is not available while silenced.",
                    )
                ),
            )
            return

        error = await users_usecases.join_multiplayer_match(
            session_id=osu_session["session_id"],
            multiplayer_match_id=self.match_id,
            untrusted_password=self.match_passwd,
        )
        if error is not None:
            await osu_sessions_repo.unicast_osu_data(
                target_session_id=osu_session["session_id"],
                data=app.packets.match_join_fail(),
            )
            return

        await users_repo.partial_update(
            id=osu_session["user_id"],
            latest_activity=int(time.time()),
        )


@register(ClientPackets.PART_MATCH)
class MatchPart(BasePacket):
    async def handle(self, osu_session: osu_sessions_repo.OsuSession) -> None:
        if osu_session["match_id"] is None:
            log(
                f"{osu_session} tried to leave a match when they're not in one.",
                Ansi.LYELLOW,
            )
            return

        error = await users_usecases.leave_multiplayer_match(
            session_id=osu_session["session_id"],
            multiplayer_match_id=osu_session["match_id"],
        )
        if error is not None:
            log(f"Error leaving match: {error}", Ansi.LRED)
            return

        await users_repo.partial_update(
            id=osu_session["user_id"],
            latest_activity=int(time.time()),
        )


@register(ClientPackets.MATCH_CHANGE_SLOT)
class MatchChangeSlot(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.slot_id = reader.read_i32()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        # read new slot ID
        if not 0 <= self.slot_id < 16:
            return

        if player.match.slots[self.slot_id].status != SlotStatus.open:
            log(f"{player} tried to move into non-open slot.", Ansi.LYELLOW)
            return

        # swap with current slot.
        slot = player.match.get_slot(player)
        assert slot is not None

        player.match.slots[self.slot_id].copy_from(slot)
        slot.reset()

        player.match.enqueue_state()  # technically not needed for host?


@register(ClientPackets.MATCH_READY)
class MatchReady(BasePacket):
    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        slot = player.match.get_slot(player)
        assert slot is not None

        slot.status = SlotStatus.ready
        player.match.enqueue_state(lobby=False)


@register(ClientPackets.MATCH_LOCK)
class MatchLock(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.slot_id = reader.read_i32()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        if player is not player.match.host:
            log(f"{player} attempted to lock match as non-host.", Ansi.LYELLOW)
            return

        # read new slot ID
        if not 0 <= self.slot_id < 16:
            return

        slot = player.match.slots[self.slot_id]

        if slot.status == SlotStatus.locked:
            slot.status = SlotStatus.open
        else:
            if slot.player is player.match.host:
                # don't allow the match host to kick
                # themselves by clicking their crown
                return

            if slot.player:
                # uggggggh i hate trusting the osu! client
                # man why is it designed like this
                # TODO: probably going to end up changing
                ...  # slot.reset()

            slot.status = SlotStatus.locked

        player.match.enqueue_state()


@register(ClientPackets.MATCH_CHANGE_SETTINGS)
class MatchChangeSettings(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match_data = reader.read_match()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if not validate_match_data(self.match_data, expected_host_id=player.id):
            log(
                f"{player} tried to change match settings with invalid data.",
                Ansi.LYELLOW,
            )
            return

        if player.match is None:
            return

        if player is not player.match.host:
            log(f"{player} attempted to change settings as non-host.", Ansi.LYELLOW)
            return

        if self.match_data.freemods != player.match.freemods:
            # freemods status has been changed.
            player.match.freemods = self.match_data.freemods

            if self.match_data.freemods:
                # match mods -> active slot mods.
                for slot in player.match.slots:
                    if slot.player is not None:
                        # the slot takes any non-speed
                        # changing mods from the match.
                        slot.mods = player.match.mods & ~SPEED_CHANGING_MODS

                # keep only speed-changing mods.
                player.match.mods &= SPEED_CHANGING_MODS
            else:
                # host mods -> match mods.
                host = player.match.get_host_slot()  # should always exist
                assert host is not None

                # the match keeps any speed-changing mods,
                # and also takes any mods the host has enabled.
                player.match.mods &= SPEED_CHANGING_MODS
                player.match.mods |= host.mods

                for slot in player.match.slots:
                    if slot.player is not None:
                        slot.mods = Mods.NOMOD

        if self.match_data.map_id == -1:
            # map being changed, unready players.
            player.match.unready_players(expected=SlotStatus.ready)
            player.match.prev_map_id = player.match.map_id

            player.match.map_id = -1
            player.match.map_md5 = ""
            player.match.map_name = ""
        elif player.match.map_id == -1:
            if player.match.prev_map_id != self.match_data.map_id:
                # new map has been chosen, send to match chat.
                map_url = (
                    f"https://osu.{app.settings.DOMAIN}/b/{self.match_data.map_id}"
                )
                map_embed = f"[{map_url} {self.match_data.map_name}]"
                player.match.chat.send_bot(f"Selected: {map_embed}.")

            # use our serverside version if we have it, but
            # still allow for users to pick unknown maps.
            bmap = await Beatmap.from_md5(self.match_data.map_md5)

            if bmap:
                player.match.map_id = bmap.id
                player.match.map_md5 = bmap.md5
                player.match.map_name = bmap.full_name
                player.match.mode = GameMode(player.match.host.status.mode.as_vanilla)
            else:
                player.match.map_id = self.match_data.map_id
                player.match.map_md5 = self.match_data.map_md5
                player.match.map_name = self.match_data.map_name
                player.match.mode = GameMode(self.match_data.mode)

        if player.match.team_type != self.match_data.team_type:
            # if theres currently a scrim going on, only allow
            # team type to change by using the !mp teams command.
            if player.match.is_scrimming:
                _team = ("head-to-head", "tag-coop", "team-vs", "tag-team-vs")[
                    self.match_data.team_type
                ]

                msg = (
                    "Changing team type while scrimming will reset "
                    "the overall score - to do so, please use the "
                    f"!mp teams {_team} command."
                )
                player.match.chat.send_bot(msg)
            else:
                # find the new appropriate default team.
                # defaults are (ffa: neutral, teams: red).
                if self.match_data.team_type in (
                    MatchTeamTypes.HEAD_TO_HEAD,
                    MatchTeamTypes.TAG_CO_OP,
                ):
                    new_t = MatchTeams.NEUTRAL
                else:
                    new_t = MatchTeams.RED

                # change each active slots team to
                # fit the correspoding team type.
                for slot in player.match.slots:
                    if slot.player is not None:
                        slot.team = new_t

                # change the matches'.
                player.match.team_type = MatchTeamTypes(self.match_data.team_type)

        if player.match.win_condition != self.match_data.win_condition:
            # win condition changing; if `use_pp_scoring`
            # is enabled, disable it. always use new cond.
            if player.match.use_pp_scoring:
                player.match.use_pp_scoring = False

            player.match.win_condition = MatchWinConditions(
                self.match_data.win_condition,
            )

        player.match.name = self.match_data.name

        player.match.enqueue_state()


@register(ClientPackets.MATCH_START)
class MatchStart(BasePacket):
    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        if player is not player.match.host:
            log(f"{player} attempted to start match as non-host.", Ansi.LYELLOW)
            return

        player.match.start()


@register(ClientPackets.MATCH_SCORE_UPDATE)
class MatchScoreUpdate(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.play_data = reader.read_raw()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        # this runs very frequently in matches,
        # so it's written to run pretty quick.

        if player.match is None:
            return

        slot_id = player.match.get_slot_id(player)
        assert slot_id is not None

        # if scorev2 is enabled, read an extra 8 bytes.
        buf = bytearray(b"0\x00\x00")
        buf += len(self.play_data).to_bytes(4, "little")
        buf += self.play_data
        buf[11] = slot_id

        player.match.enqueue(bytes(buf), lobby=False)


@register(ClientPackets.MATCH_COMPLETE)
class MatchComplete(BasePacket):
    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        slot = player.match.get_slot(player)
        assert slot is not None

        slot.status = SlotStatus.complete

        # check if there are any players that haven't finished.
        if any([s.status == SlotStatus.playing for s in player.match.slots]):
            return

        # find any players just sitting in the multi room
        # that have not been playing the map; they don't
        # need to know all the players have completed, only
        # the ones who are playing (just new match info).
        not_playing = [
            s.player.id
            for s in player.match.slots
            if s.player is not None and s.status != SlotStatus.complete
        ]

        was_playing = [
            s for s in player.match.slots if s.player and s.player.id not in not_playing
        ]

        player.match.unready_players(expected=SlotStatus.complete)
        player.match.reset_players_loaded_status()

        player.match.in_progress = False
        player.match.enqueue(
            app.packets.match_complete(),
            lobby=False,
            immune=not_playing,
        )
        player.match.enqueue_state()

        if player.match.is_scrimming:
            # determine winner, update match points & inform players.
            asyncio.create_task(player.match.update_matchpoints(was_playing))


@register(ClientPackets.MATCH_CHANGE_MODS)
class MatchChangeMods(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.mods = reader.read_i32()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        if player.match.freemods:
            if player is player.match.host:
                # allow host to set speed-changing mods.
                player.match.mods = Mods(self.mods & SPEED_CHANGING_MODS)

            # set slot mods
            slot = player.match.get_slot(player)
            assert slot is not None

            slot.mods = Mods(self.mods & ~SPEED_CHANGING_MODS)
        else:
            if player is not player.match.host:
                log(f"{player} attempted to change mods as non-host.", Ansi.LYELLOW)
                return

            # not freemods, set match mods.
            player.match.mods = Mods(self.mods)

        player.match.enqueue_state()


def is_playing(slot: Slot) -> bool:
    return slot.status == SlotStatus.playing and not slot.loaded


@register(ClientPackets.MATCH_LOAD_COMPLETE)
class MatchLoadComplete(BasePacket):
    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        # our player has loaded in and is ready to play.
        slot = player.match.get_slot(player)
        assert slot is not None

        slot.loaded = True

        # check if all players are loaded,
        # if so, tell all players to begin.
        if not any(map(is_playing, player.match.slots)):
            player.match.enqueue(app.packets.match_all_players_loaded(), lobby=False)


@register(ClientPackets.MATCH_NO_BEATMAP)
class MatchNoBeatmap(BasePacket):
    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        slot = player.match.get_slot(player)
        assert slot is not None

        slot.status = SlotStatus.no_map
        player.match.enqueue_state(lobby=False)


@register(ClientPackets.MATCH_NOT_READY)
class MatchNotReady(BasePacket):
    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        slot = player.match.get_slot(player)
        assert slot is not None

        slot.status = SlotStatus.not_ready
        player.match.enqueue_state(lobby=False)


@register(ClientPackets.MATCH_FAILED)
class MatchFailed(BasePacket):
    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        # find the player's slot id, and enqueue that
        # they've failed to all other players in the match.
        slot_id = player.match.get_slot_id(player)
        assert slot_id is not None

        player.match.enqueue(app.packets.match_player_failed(slot_id), lobby=False)


@register(ClientPackets.MATCH_HAS_BEATMAP)
class MatchHasBeatmap(BasePacket):
    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        slot = player.match.get_slot(player)
        assert slot is not None

        slot.status = SlotStatus.not_ready
        player.match.enqueue_state(lobby=False)


@register(ClientPackets.MATCH_SKIP_REQUEST)
class MatchSkipRequest(BasePacket):
    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        slot = player.match.get_slot(player)
        assert slot is not None

        slot.skipped = True
        player.match.enqueue(app.packets.match_player_skipped(player.id))

        for slot in player.match.slots:
            if slot.status == SlotStatus.playing and not slot.skipped:
                return

        # all users have skipped, enqueue a skip.
        player.match.enqueue(app.packets.match_skip(), lobby=False)


@register(ClientPackets.CHANNEL_JOIN, restricted=True)
class ChannelJoin(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.name = reader.read_string()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if self.name in IGNORED_CHANNELS:
            return

        channel = app.state.sessions.channels.get_by_name(self.name)

        if not channel or not player.join_channel(channel):
            log(f"{player} failed to join {self.name}.", Ansi.LYELLOW)
            return


@register(ClientPackets.MATCH_TRANSFER_HOST)
class MatchTransferHost(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.slot_id = reader.read_i32()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        if player is not player.match.host:
            log(f"{player} attempted to transfer host as non-host.", Ansi.LYELLOW)
            return

        # read new slot ID
        if not 0 <= self.slot_id < 16:
            return

        target = player.match.slots[self.slot_id].player
        if not target:
            log(f"{player} tried to transfer host to an empty slot?")
            return

        player.match.host_id = target.id
        player.match.host.enqueue(app.packets.match_transfer_host())
        player.match.enqueue_state()


@register(ClientPackets.TOURNAMENT_MATCH_INFO_REQUEST)
class TourneyMatchInfoRequest(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match_id = reader.read_i32()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if not 0 <= self.match_id < 64:
            return  # invalid match id

        if not player.priv & Privileges.DONATOR:
            return  # insufficient privs

        match = app.state.sessions.matches[self.match_id]
        if not match:
            return  # match not found

        player.enqueue(app.packets.update_match(match, send_pw=False))


@register(ClientPackets.TOURNAMENT_JOIN_MATCH_CHANNEL)
class TourneyMatchJoinChannel(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match_id = reader.read_i32()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if not 0 <= self.match_id < 64:
            return  # invalid match id

        if not player.priv & Privileges.DONATOR:
            return  # insufficient privs

        match = app.state.sessions.matches[self.match_id]
        if not match:
            return  # match not found

        for slot in match.slots:
            if slot.player is not None:
                if player.id == slot.player.id:
                    return  # playing in the match

        # attempt to join match chan
        if player.join_channel(match.chat_channel_id):
            match.tourney_clients.add(player.id)


@register(ClientPackets.TOURNAMENT_LEAVE_MATCH_CHANNEL)
class TourneyMatchLeaveChannel(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match_id = reader.read_i32()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if not 0 <= self.match_id < 64:
            return  # invalid match id

        if not player.priv & Privileges.DONATOR:
            return  # insufficient privs

        match = app.state.sessions.matches[self.match_id]
        if not match:
            return  # match not found

        # attempt to join match chan
        player.leave_channel(match.chat_channel_id)
        match.tourney_clients.remove(player.id)


@register(ClientPackets.FRIEND_ADD)
class FriendAdd(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.user_id = reader.read_i32()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        target = app.state.sessions.players.get(id=self.user_id)
        if not target:
            log(f"{player} tried to add a user who is not online! ({self.user_id})")
            return

        if target is app.state.sessions.bot:
            return

        if target.id in player.blocks:
            player.blocks.remove(target.id)

        player.update_latest_activity_soon()
        await player.add_friend(target)


@register(ClientPackets.FRIEND_REMOVE)
class FriendRemove(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.user_id = reader.read_i32()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        target = app.state.sessions.players.get(id=self.user_id)
        if not target:
            log(f"{player} tried to remove a user who is not online! ({self.user_id})")
            return

        if target is app.state.sessions.bot:
            return

        player.update_latest_activity_soon()
        await player.remove_friend(target)


@register(ClientPackets.MATCH_CHANGE_TEAM)
class MatchChangeTeam(BasePacket):
    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if player.match is None:
            return

        # toggle team
        slot = player.match.get_slot(player)
        assert slot is not None

        if slot.team == MatchTeams.BLUE:
            slot.team = MatchTeams.RED
        else:
            slot.team = MatchTeams.BLUE

        player.match.enqueue_state(lobby=False)


@register(ClientPackets.CHANNEL_PART, restricted=True)
class ChannelPart(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.name = reader.read_string()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if self.name in IGNORED_CHANNELS:
            return

        channel = app.state.sessions.channels.get_by_name(self.name)

        if not channel:
            log(f"{player} failed to leave {self.name}.", Ansi.LYELLOW)
            return

        if player not in channel:
            # user not in chan
            return

        # leave the chan server-side.
        player.leave_channel(channel)


@register(ClientPackets.RECEIVE_UPDATES, restricted=True)
class ReceiveUpdates(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.value = reader.read_i32()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if not 0 <= self.value < 3:
            log(f"{player} tried to set his presence filter to {self.value}?")
            return

        player.pres_filter = PresenceFilter(self.value)


@register(ClientPackets.SET_AWAY_MESSAGE)
class SetAwayMessage(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.msg = reader.read_message()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        player.away_msg = self.msg.text


@register(ClientPackets.USER_STATS_REQUEST, restricted=True)
class StatsRequest(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.user_ids = reader.read_i32_list_i16l()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        unrestrcted_ids = [p.id for p in app.state.sessions.players.unrestricted]
        is_online = lambda o: o in unrestrcted_ids and o != player.id

        for online in filter(is_online, self.user_ids):
            target = app.state.sessions.players.get(id=online)
            if target:
                if target is app.state.sessions.bot:
                    # optimization for bot since it's
                    # the most frequently requested user
                    packet = app.packets.bot_stats(target)
                else:
                    packet = app.packets.user_stats(target)

                player.enqueue(packet)


@register(ClientPackets.MATCH_INVITE)
class MatchInvite(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.user_id = reader.read_i32()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if not player.match:
            return

        target = app.state.sessions.players.get(id=self.user_id)
        if not target:
            log(f"{player} tried to invite a user who is not online! ({self.user_id})")
            return

        if target is app.state.sessions.bot:
            player.send_bot("I'm too busy!")
            return

        target.enqueue(app.packets.match_invite(player, target.name))
        player.update_latest_activity_soon()

        log(f"{player} invited {target} to their match.")


@register(ClientPackets.MATCH_CHANGE_PASSWORD)
class MatchChangePassword(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.match_data = reader.read_match()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        if not validate_match_data(self.match_data, expected_host_id=player.id):
            log(
                f"{player} tried to change match password with invalid data.",
                Ansi.LYELLOW,
            )
            return

        if player.match is None:
            return

        if player is not player.match.host:
            log(f"{player} attempted to change pw as non-host.", Ansi.LYELLOW)
            return

        player.match.passwd = self.match_data.password
        player.match.enqueue_state()


@register(ClientPackets.USER_PRESENCE_REQUEST)
class UserPresenceRequest(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.user_ids = reader.read_i32_list_i16l()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        for pid in self.user_ids:
            target = app.state.sessions.players.get(id=pid)
            if target:
                if target is app.state.sessions.bot:
                    # optimization for bot since it's
                    # the most frequently requested user
                    packet = app.packets.bot_presence(target)
                else:
                    packet = app.packets.dead_user_presence(target)

                player.enqueue(packet)


@register(ClientPackets.USER_PRESENCE_REQUEST_ALL)
class UserPresenceRequestAll(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.ingame_time = reader.read_i32()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        # NOTE: this packet is only used when there
        # are >256 players visible to the client.

        buffer = bytearray()

        for player in app.state.sessions.players.unrestricted:
            buffer += app.packets.dead_user_presence(player)

        player.enqueue(bytes(buffer))


@register(ClientPackets.TOGGLE_BLOCK_NON_FRIEND_DMS)
class ToggleBlockingDMs(BasePacket):
    def __init__(self, reader: BanchoPacketReader) -> None:
        self.value = reader.read_i32()

    async def handle(self, player: osu_sessions_repo.OsuSession) -> None:
        player.pm_private = self.value == 1

        player.update_latest_activity_soon()
