from __future__ import annotations

import copy
import importlib
import os
import pprint
import random
import secrets
import signal
import struct
import time
import traceback
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from pathlib import Path
from time import perf_counter_ns as clock_ns
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Mapping
from typing import NamedTuple
from typing import NoReturn
from typing import Optional
from typing import Sequence
from typing import TYPE_CHECKING
from typing import TypedDict
from typing import TypeVar
from typing import Union

import psutil
import timeago
from pytimeparse.timeparse import timeparse

import app.logging
import app.packets
import app.settings
import app.state
import app.usecases.performance
import app.utils
from app.constants import regexes
from app.constants.gamemodes import GameMode
from app.constants.gamemodes import GAMEMODE_REPR_LIST
from app.constants.mods import Mods
from app.constants.mods import SPEED_CHANGING_MODS
from app.constants.privileges import ClanPrivileges
from app.constants.privileges import Privileges
from app.objects.beatmap import Beatmap
from app.objects.beatmap import ensure_local_osu_file
from app.objects.beatmap import RankedStatus
from app.objects.clan import Clan
from app.objects.match import MapPool
from app.objects.match import Match
from app.objects.match import MatchTeams
from app.objects.match import MatchTeamTypes
from app.objects.match import MatchWinConditions
from app.objects.match import SlotStatus
from app.objects.player import Player
from app.objects.score import SubmissionStatus
from app.repositories import clans as clans_repo
from app.repositories import maps as maps_repo
from app.repositories import players as players_repo
from app.usecases.performance import ScoreParams
from app.utils import seconds_readable

if TYPE_CHECKING:
    from app.objects.channel import Channel


BEATMAPS_PATH = Path.cwd() / ".data/osu"


@dataclass
class Context:
    player: Player
    trigger: str
    args: Sequence[str]

    recipient: Union[Channel, Player]


Callback = Callable[[Context], Awaitable[Optional[str]]]


class Command(NamedTuple):
    triggers: list[str]
    callback: Callback
    priv: Privileges
    hidden: bool
    doc: Optional[str]


class CommandSet:
    def __init__(self, trigger: str, doc: str) -> None:
        self.trigger = trigger
        self.doc = doc

        self.commands: list[Command] = []

    def add(
        self,
        priv: Privileges,
        aliases: list[str] = [],
        hidden: bool = False,
    ) -> Callable[[Callback], Callback]:
        def wrapper(f: Callback) -> Callback:
            self.commands.append(
                Command(
                    # NOTE: this method assumes that functions without any
                    # triggers will be named like '{self.trigger}_{trigger}'.
                    triggers=(
                        [f.__name__.removeprefix(f"{self.trigger}_").strip()] + aliases
                    ),
                    callback=f,
                    priv=priv,
                    hidden=hidden,
                    doc=f.__doc__,
                ),
            )

            return f

        return wrapper


# TODO: refactor help commands into some base ver
#       since they're all the same anyway lol.

mp_commands = CommandSet("mp", "Multiplayer commands.")
pool_commands = CommandSet("pool", "Mappool commands.")
clan_commands = CommandSet("clan", "Clan commands.")

regular_commands = []
command_sets = [
    mp_commands,
    pool_commands,
    clan_commands,
]


def command(
    priv: Privileges,
    aliases: list[str] = [],
    hidden: bool = False,
) -> Callable[[Callback], Callback]:
    def wrapper(f: Callback) -> Callback:
        regular_commands.append(
            Command(
                callback=f,
                priv=priv,
                hidden=hidden,
                triggers=[f.__name__.strip("_")] + aliases,
                doc=f.__doc__,
            ),
        )

        return f

    return wrapper


""" User commands
# The commands below are not considered dangerous,
# and are granted to any unbanned players.
"""


@command(Privileges.UNRESTRICTED, aliases=["", "h"], hidden=True)
async def _help(ctx: Context) -> Optional[str]:
    """Show all documented commands the player can access."""
    prefix = app.settings.COMMAND_PREFIX
    l = ["Individual commands", "-----------"]

    for cmd in regular_commands:
        if not cmd.doc or ctx.player.priv & cmd.priv != cmd.priv:
            # no doc, or insufficient permissions.
            continue

        l.append(f"{prefix}{cmd.triggers[0]}: {cmd.doc}")

    l.append("")  # newline
    l.extend(["Command sets", "-----------"])

    for cmd_set in command_sets:
        l.append(f"{prefix}{cmd_set.trigger}: {cmd_set.doc}")

    return "\n".join(l)


@command(Privileges.UNRESTRICTED)
async def roll(ctx: Context) -> Optional[str]:
    """Roll an n-sided die where n is the number you write (100 default)."""
    if ctx.args and ctx.args[0].isdecimal():
        max_roll = min(int(ctx.args[0]), 0x7FFF)
    else:
        max_roll = 100

    if max_roll == 0:
        return "Roll what?"

    points = random.randrange(0, max_roll)
    return f"{ctx.player.name} rolls {points} points!"


@command(Privileges.UNRESTRICTED, hidden=True)
async def block(ctx: Context) -> Optional[str]:
    """Block another user from communicating with you."""
    target = await app.state.sessions.players.from_cache_or_sql(name=" ".join(ctx.args))

    if not target:
        return "User not found."

    if target is app.state.sessions.bot or target is ctx.player:
        return "What?"

    if target.id in ctx.player.blocks:
        return f"{target.name} already blocked!"

    if target.id in ctx.player.friends:
        ctx.player.friends.remove(target.id)

    await ctx.player.add_block(target)
    return f"Added {target.name} to blocked users."


@command(Privileges.UNRESTRICTED, hidden=True)
async def unblock(ctx: Context) -> Optional[str]:
    """Unblock another user from communicating with you."""
    target = await app.state.sessions.players.from_cache_or_sql(name=" ".join(ctx.args))

    if not target:
        return "User not found."

    if target is app.state.sessions.bot or target is ctx.player:
        return "What?"

    if target.id not in ctx.player.blocks:
        return f"{target.name} not blocked!"

    await ctx.player.remove_block(target)
    return f"Removed {target.name} from blocked users."


@command(Privileges.UNRESTRICTED)
async def reconnect(ctx: Context) -> Optional[str]:
    """Disconnect and reconnect a given player (or self) to the server."""
    if ctx.args:
        # !reconnect <player>
        if not ctx.player.priv & Privileges.ADMINISTRATOR:
            return None  # requires admin

        target = app.state.sessions.players.get(name=" ".join(ctx.args))
        if not target:
            return "Player not found"
    else:
        # !reconnect
        target = ctx.player

    target.logout()

    return None


@command(Privileges.SUPPORTER)
async def changename(ctx: Context) -> Optional[str]:
    """Change your username."""
    name = " ".join(ctx.args).strip()

    if not regexes.USERNAME.match(name):
        return "Must be 2-15 characters in length."

    if "_" in name and " " in name:
        return 'May contain "_" and " ", but not both.'

    if name in app.settings.DISALLOWED_NAMES:
        return "Disallowed username; pick another."

    if await players_repo.fetch_one(name=name):
        return "Username already taken by another player."

    # all checks passed, update their name
    await players_repo.update(ctx.player.id, name=name)

    ctx.player.enqueue(
        app.packets.notification(f"Your username has been changed to {name}!"),
    )
    ctx.player.logout()

    return None


@command(Privileges.UNRESTRICTED, aliases=["bloodcat", "beatconnect", "chimu", "q"])
async def maplink(ctx: Context) -> Optional[str]:
    """Return a download link to the user's current map (situation dependant)."""
    bmap = None

    # priority: multiplayer -> spectator -> last np
    match = ctx.player.match
    spectating = ctx.player.spectating

    if match and match.map_id:
        bmap = await Beatmap.from_md5(match.map_md5)
    elif spectating and spectating.status.map_id:
        bmap = await Beatmap.from_md5(spectating.status.map_md5)
    elif ctx.player.last_np is not None and time.time() < ctx.player.last_np["timeout"]:
        bmap = ctx.player.last_np["bmap"]

    if bmap is None:
        return "No map found!"

    # gatari.pw & nerina.pw are pretty much the only
    # reliable mirrors I know of? perhaps beatconnect
    return f"[https://osu.gatari.pw/d/{bmap.set_id} {bmap.full_name}]"


@command(Privileges.UNRESTRICTED, aliases=["last", "r"])
async def recent(ctx: Context) -> Optional[str]:
    """Show information about a player's most recent score."""
    if ctx.args:
        target = app.state.sessions.players.get(name=" ".join(ctx.args))
        if not target:
            return "Player not found."
    else:
        target = ctx.player

    score = target.recent_score
    if not score:
        return "No scores found (only saves per play session)."

    if score.bmap is None:
        return "We don't have a beatmap on file for your recent score."

    l = [f"[{score.mode!r}] {score.bmap.embed}", f"{score.acc:.2f}%"]

    if score.mods:
        l.insert(1, f"+{score.mods!r}")

    l = [" ".join(l)]

    if score.passed:
        rank = score.rank if score.status == SubmissionStatus.BEST else "NA"
        l.append(f"PASS {{{score.pp:.2f}pp #{rank}}}")
    else:
        # XXX: prior to v3.2.0, bancho.py didn't parse total_length from
        # the osu!api, and thus this can do some zerodivision moments.
        # this can probably be removed in the future, or better yet
        # replaced with a better system to fix the maps.
        if score.bmap.total_length != 0:
            completion = score.time_elapsed / (score.bmap.total_length * 1000)
            l.append(f"FAIL {{{completion * 100:.2f}% complete}})")
        else:
            l.append("FAIL")

    return " | ".join(l)


TOP_SCORE_FMTSTR = (
    "{idx}. ({pp:.2f}pp) [https://osu.{domain}/beatmapsets/{map_set_id}/{map_id} "
    "{artist} - {title} [{version}]]"
)


@command(Privileges.UNRESTRICTED, hidden=True)
async def top(ctx: Context) -> Optional[str]:
    """Show information about a player's top 10 scores."""
    # !top <mode> (player)
    args_len = len(ctx.args)
    if args_len not in (1, 2):
        return "Invalid syntax: !top <mode> (player)"

    if ctx.args[0] not in GAMEMODE_REPR_LIST:
        return f'Valid gamemodes: {", ".join(GAMEMODE_REPR_LIST)}.'

    if ctx.args[0] in (
        "rx!mania",
        "ap!taiko",
        "ap!catch",
        "ap!mania",
    ):
        return "Impossible gamemode combination."

    if args_len == 2:
        if not regexes.USERNAME.match(ctx.args[1]):
            return "Invalid username."

        # specific player provided
        player = app.state.sessions.players.get(name=ctx.args[1])
        if not player:
            return "Player not found."
    else:
        # no player provided, use self
        player = ctx.player

    # !top rx!std
    mode = GAMEMODE_REPR_LIST.index(ctx.args[0])

    scores = await app.state.services.database.fetch_all(
        "SELECT s.pp, b.artist, b.title, b.version, b.set_id map_set_id, b.id map_id "
        "FROM scores s "
        "LEFT JOIN maps b ON b.md5 = s.map_md5 "
        "WHERE s.userid = :user_id "
        "AND s.mode = :mode "
        "AND s.status = 2 "
        "AND b.status in (2, 3) "
        "ORDER BY s.pp DESC LIMIT 10",
        {"user_id": player.id, "mode": mode},
    )

    if not scores:
        return "No scores"

    return "\n".join(
        [f"Top 10 scores for {player.embed} ({ctx.args[0]})."]
        + [
            TOP_SCORE_FMTSTR.format(idx=idx + 1, domain=app.settings.DOMAIN, **s)
            for idx, s in enumerate(scores)
        ],
    )


# TODO: !compare (compare to previous !last/!top post's map)


class ParsingError(str):
    ...


def parse__with__command_args(
    mode: int,
    args: Sequence[str],
) -> Union[Mapping[str, Any], ParsingError]:
    """Parse arguments for the !with command."""

    # tried to balance complexity vs correctness for this function
    # TODO: it can surely be cleaned up further - need to rethink it?

    if not args or len(args) > 4:
        return ParsingError("Invalid syntax: !with <acc/nmiss/combo/mods ...>")

    # !with 95% 1m 429x hddt
    acc = mods = combo = nmiss = None

    # parse acc, misses, combo and mods from arguments.
    # tried to balance complexity vs correctness here
    for arg in (str.lower(arg) for arg in args):
        # mandatory suffix, combo & nmiss
        if combo is None and arg.endswith("x") and arg[:-1].isdecimal():
            combo = int(arg[:-1])
            # if combo > bmap.max_combo:
            #    return "Invalid combo."
        elif nmiss is None and arg.endswith("m") and arg[:-1].isdecimal():
            nmiss = int(arg[:-1])
            # TODO: store nobjects?
            # if nmiss > bmap.combo:
            #    return "Invalid misscount."
        else:
            # optional prefix/suffix, mods & accuracy
            arg_stripped = arg.removeprefix("+").removesuffix("%")
            if mods is None and arg_stripped.isalpha() and len(arg_stripped) % 2 == 0:
                mods = Mods.from_modstr(arg_stripped)
                mods = mods.filter_invalid_combos(mode)
            elif acc is None and arg_stripped.replace(".", "", 1).isdecimal():
                acc = float(arg_stripped)
                if not 0 <= acc <= 100:
                    return ParsingError("Invalid accuracy.")
            else:
                return ParsingError(f"Unknown argument: {arg}")

    return {
        "acc": acc,
        "mods": mods,
        "combo": combo,
        "nmiss": nmiss,
    }


@command(Privileges.UNRESTRICTED, aliases=["w"], hidden=True)
async def _with(ctx: Context) -> Optional[str]:
    """Specify custom accuracy & mod combinations with `/np`."""
    if ctx.recipient is not app.state.sessions.bot:
        return "This command can only be used in DM with bot."

    if ctx.player.last_np is None or time.time() >= ctx.player.last_np["timeout"]:
        return "Please /np a map first!"

    bmap: Beatmap = ctx.player.last_np["bmap"]

    osu_file_path = BEATMAPS_PATH / f"{bmap.id}.osu"
    if not await ensure_local_osu_file(osu_file_path, bmap.id, bmap.md5):
        return "Mapfile could not be found; this incident has been reported."

    mode_vn = ctx.player.last_np["mode_vn"]

    command_args = parse__with__command_args(mode_vn, ctx.args)
    if isinstance(command_args, ParsingError):
        return str(command_args)

    msg_fields = []

    score_args = ScoreParams(mode=mode_vn)

    mods = command_args["mods"]
    if mods is not None:
        score_args.mods = mods
        msg_fields.append(f"{mods!r}")

    nmiss = command_args["nmiss"]
    if nmiss:
        score_args.nmiss = nmiss
        msg_fields.append(f"{nmiss}m")

    combo = command_args["combo"]
    if combo is not None:
        score_args.combo = combo
        msg_fields.append(f"{combo}x")

    acc = command_args["acc"]
    if acc is not None:
        score_args.acc = acc
        msg_fields.append(f"{acc:.2f}%")

    result = app.usecases.performance.calculate_performances(
        osu_file_path=str(osu_file_path),
        scores=[score_args],  # calculate one score
    )

    return "{msg}: {performance:.2f}pp ({star_rating:.2f}*)".format(
        msg=" ".join(msg_fields), **result[0]  # (first score result)
    )


@command(Privileges.UNRESTRICTED, aliases=["req"])
async def request(ctx: Context) -> Optional[str]:
    """Request a beatmap for nomination."""
    if ctx.args:
        return "Invalid syntax: !request"

    if ctx.player.last_np is None or time.time() >= ctx.player.last_np["timeout"]:
        return "Please /np a map first!"

    bmap = ctx.player.last_np["bmap"]

    if bmap.status != RankedStatus.Pending:
        return "Only pending maps may be requested for status change."

    await app.state.services.database.execute(
        "INSERT INTO map_requests "
        "(map_id, player_id, datetime, active) "
        "VALUES (:map_id, :user_id, NOW(), 1)",
        {"map_id": bmap.id, "user_id": ctx.player.id},
    )

    return "Request submitted."


@command(Privileges.UNRESTRICTED)
async def get_apikey(ctx: Context) -> Optional[str]:
    """Generate a new api key & assign it to the player."""
    if ctx.recipient is not app.state.sessions.bot:
        return f"Command only available in DMs with {app.state.sessions.bot.name}."

    # remove old token
    if ctx.player.api_key:
        app.state.sessions.api_keys.pop(ctx.player.api_key)

    # generate new token
    ctx.player.api_key = str(uuid.uuid4())

    await players_repo.update(ctx.player.id, api_key=ctx.player.api_key)
    app.state.sessions.api_keys[ctx.player.api_key] = ctx.player.id

    ctx.player.enqueue(
        app.packets.notification(
            "Type /savelog and click the popup for an easy way to copy this.",
        ),
    )
    return f"Your API key is now: {ctx.player.api_key}"


""" Nominator commands
# The commands below allow users to
# manage  the server's state of beatmaps.
"""


@command(Privileges.NOMINATOR, aliases=["reqs"], hidden=True)
async def requests(ctx: Context) -> Optional[str]:
    """Check the nomination request queue."""
    if ctx.args:
        return "Invalid syntax: !requests"

    rows = await app.state.services.database.fetch_all(
        "SELECT map_id, player_id, datetime FROM map_requests WHERE active = 1",
    )

    if not rows:
        return "The queue is clean! (0 map request(s))"

    l = [f"Total requests: {len(rows)}"]

    for map_id, player_id, dt in rows:
        # find player & map for each row, and add to output.
        player = await app.state.sessions.players.from_cache_or_sql(id=player_id)
        if not player:
            l.append(f"Failed to find requesting player ({player_id})?")
            continue

        bmap = await Beatmap.from_bid(map_id)
        if not bmap:
            l.append(f"Failed to find requested map ({map_id})?")
            continue

        l.append(f"[{player.embed} @ {dt:%b %d %I:%M%p}] {bmap.embed}.")

    return "\n".join(l)


_status_str_to_int_map = {"unrank": 0, "rank": 2, "love": 5}


def status_to_id(s: str) -> int:
    return _status_str_to_int_map[s]


@command(Privileges.NOMINATOR)
async def _map(ctx: Context) -> Optional[str]:
    """Changes the ranked status of the most recently /np'ed map."""
    if (
        len(ctx.args) != 2
        or ctx.args[0] not in ("rank", "unrank", "love")
        or ctx.args[1] not in ("set", "map")
    ):
        return "Invalid syntax: !map <rank/unrank/love> <map/set>"

    if ctx.player.last_np is None or time.time() >= ctx.player.last_np["timeout"]:
        return "Please /np a map first!"

    bmap = ctx.player.last_np["bmap"]
    new_status = RankedStatus(status_to_id(ctx.args[0]))

    if ctx.args[1] == "map":
        if bmap.status == new_status:
            return f"{bmap.embed} is already {new_status!s}!"
    else:  # ctx.args[1] == "set"
        if all(map.status == new_status for map in bmap.set.maps):
            return f"All maps from the set are already {new_status!s}!"

    # update sql & cache based on scope
    # XXX: not sure if getting md5s from sql
    # for updating cache would be faster?
    # surely this will not scale as well...

    async with app.state.services.database.connection() as db_conn:
        if ctx.args[1] == "set":
            # update whole set
            await db_conn.execute(
                "UPDATE maps SET status = :status, frozen = 1 WHERE set_id = :set_id",
                {"status": new_status, "set_id": bmap.set_id},
            )

            # select all map ids for clearing map requests.
            map_ids = [
                row["id"]
                for row in await maps_repo.fetch_many(
                    set_id=bmap.set_id,
                )
            ]

            for bmap in app.state.cache.beatmapset[bmap.set_id].maps:
                bmap.status = new_status

        else:
            # update only map
            await maps_repo.update(bmap.id, status=new_status, frozen=True)

            map_ids = [bmap.id]

            if bmap.md5 in app.state.cache.beatmap:
                app.state.cache.beatmap[bmap.md5].status = new_status

        # deactivate rank requests for all ids
        await db_conn.execute(
            "UPDATE map_requests SET active = 0 WHERE map_id IN :map_ids",
            {"map_ids": map_ids},
        )

    return f"{bmap.embed} updated to {new_status!s}."


""" Mod commands
# The commands below are somewhat dangerous,
# and are generally for managing players.
"""

ACTION_STRINGS = {
    "restrict": "Restricted for",
    "unrestrict": "Unrestricted for",
    "silence": "Silenced for",
    "unsilence": "Unsilenced for",
    "note": "Note added:",
}


@command(Privileges.MODERATOR, hidden=True)
async def notes(ctx: Context) -> Optional[str]:
    """Retrieve the logs of a specified player by name."""
    if len(ctx.args) != 2 or not ctx.args[1].isdecimal():
        return "Invalid syntax: !notes <name> <days_back>"

    target = await app.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return f'"{ctx.args[0]}" not found.'

    days = int(ctx.args[1])

    if days > 365:
        return "Please contact a developer to fetch >365 day old information."
    elif days <= 0:
        return "Invalid syntax: !notes <name> <days_back>"

    res = await app.state.services.database.fetch_all(
        "SELECT `action`, `msg`, `time`, `from` "
        "FROM `logs` WHERE `to` = :to "
        "AND UNIX_TIMESTAMP(`time`) >= UNIX_TIMESTAMP(NOW()) - :seconds "
        "ORDER BY `time` ASC",
        {"to": target.id, "seconds": days * 86400},
    )

    if not res:
        return f"No notes found on {target} in the past {days} days."

    notes = []
    for row in res:
        logger = await app.state.sessions.players.from_cache_or_sql(id=row["from"])
        if not logger:
            continue

        action_str = ACTION_STRINGS.get(row["action"], "Unknown action:")
        time_str = row["time"]
        note = row["msg"]

        notes.append(f"[{time_str}] {action_str} {note} by {logger.name}")

    return "\n".join(notes)


@command(Privileges.MODERATOR, hidden=True)
async def addnote(ctx: Context) -> Optional[str]:
    """Add a note to a specified player by name."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !addnote <name> <note ...>"

    target = await app.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return f'"{ctx.args[0]}" not found.'

    await app.state.services.database.execute(
        "INSERT INTO logs "
        "(`from`, `to`, `action`, `msg`, `time`) "
        "VALUES (:from, :to, :action, :msg, NOW())",
        {
            "from": ctx.player.id,
            "to": target.id,
            "action": "note",
            "msg": " ".join(ctx.args[1:]),
        },
    )

    return f"Added note to {target}."


# some shorthands that can be used as
# reasons in many moderative commands.
SHORTHAND_REASONS = {
    "aa": "having their appeal accepted",
    "cc": "using a modified osu! client",
    "3p": "using 3rd party programs",
    "rx": "using 3rd party programs (relax)",
    "tw": "using 3rd party programs (timewarp)",
    "au": "using 3rd party programs (auto play)",
}


@command(Privileges.MODERATOR, hidden=True)
async def silence(ctx: Context) -> Optional[str]:
    """Silence a specified player with a specified duration & reason."""
    if len(ctx.args) < 3:
        return "Invalid syntax: !silence <name> <duration> <reason>"

    target = await app.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return f'"{ctx.args[0]}" not found.'

    if target.priv & Privileges.STAFF and not ctx.player.priv & Privileges.DEVELOPER:
        return "Only developers can manage staff members."

    duration = timeparse(ctx.args[1])
    if not duration:
        return "Invalid timespan."

    reason = " ".join(ctx.args[2:])

    if reason in SHORTHAND_REASONS:
        reason = SHORTHAND_REASONS[reason]

    await target.silence(ctx.player, duration, reason)
    return f"{target} was silenced."


@command(Privileges.MODERATOR, hidden=True)
async def unsilence(ctx: Context) -> Optional[str]:
    """Unsilence a specified player."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !unsilence <name> <reason>"

    target = await app.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return f'"{ctx.args[0]}" not found.'

    if not target.silenced:
        return f"{target} is not silenced."

    if target.priv & Privileges.STAFF and not ctx.player.priv & Privileges.DEVELOPER:
        return "Only developers can manage staff members."

    reason = " ".join(ctx.args[1:])

    await target.unsilence(ctx.player, reason)
    return f"{target} was unsilenced."


""" Admin commands
# The commands below are relatively dangerous,
# and are generally for managing players.
"""


@command(Privileges.ADMINISTRATOR, aliases=["u"], hidden=True)
async def user(ctx: Context) -> Optional[str]:
    """Return general information about a given user."""
    if not ctx.args:
        # no username specified, use ctx.player
        player = ctx.player
    else:
        # username given, fetch the player
        player = await app.state.sessions.players.from_cache_or_sql(
            name=" ".join(ctx.args),
        )

        if not player:
            return "Player not found."

    priv_list = [
        priv.name
        for priv in Privileges
        if player.priv & priv and bin(priv).count("1") == 1
    ][::-1]
    if player.last_np is not None and time.time() < player.last_np["timeout"]:
        last_np = player.last_np["bmap"].embed
    else:
        last_np = None

    osu_version = player.client_details.osu_version.date if player.online else "Unknown"
    donator_info = (
        f"True (ends {timeago.format(player.donor_end)})"
        if player.priv & Privileges.DONATOR != 0
        else "False"
    )

    return "\n".join(
        (
            f'[{"Bot" if player.bot_client else "Player"}] {player.full_name} ({player.id})',
            f"Privileges: {priv_list}",
            f"Donator: {donator_info}",
            f"Channels: {[c._name for c in player.channels]}",
            f"Logged in: {timeago.format(player.login_time)}",
            f"Last server interaction: {timeago.format(player.last_recv_time)}",
            f"osu! build: {osu_version} | Tourney: {player.tourney_client}",
            f"Silenced: {player.silenced} | Spectating: {player.spectating}",
            f"Last /np: {last_np}",
            f"Recent score: {player.recent_score}",
            f"Match: {player.match}",
            f"Spectators: {player.spectators}",
        ),
    )


@command(Privileges.ADMINISTRATOR, hidden=True)
async def restrict(ctx: Context) -> Optional[str]:
    """Restrict a specified player's account, with a reason."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !restrict <name> <reason>"

    # find any user matching (including offline).
    target = await app.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return f'"{ctx.args[0]}" not found.'

    if target.priv & Privileges.STAFF and not ctx.player.priv & Privileges.DEVELOPER:
        return "Only developers can manage staff members."

    if target.restricted:
        return f"{target} is already restricted!"

    reason = " ".join(ctx.args[1:])

    if reason in SHORTHAND_REASONS:
        reason = SHORTHAND_REASONS[reason]

    await target.restrict(admin=ctx.player, reason=reason)

    # refresh their client state
    if target.online:
        target.logout()

    return f"{target} was restricted."


@command(Privileges.ADMINISTRATOR, hidden=True)
async def unrestrict(ctx: Context) -> Optional[str]:
    """Unrestrict a specified player's account, with a reason."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !unrestrict <name> <reason>"

    # find any user matching (including offline).
    target = await app.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return f'"{ctx.args[0]}" not found.'

    if target.priv & Privileges.STAFF and not ctx.player.priv & Privileges.DEVELOPER:
        return "Only developers can manage staff members."

    if not target.restricted:
        return f"{target} is not restricted!"

    reason = " ".join(ctx.args[1:])

    if reason in SHORTHAND_REASONS:
        reason = SHORTHAND_REASONS[reason]

    await target.unrestrict(ctx.player, reason)

    # refresh their client state
    if target.online:
        target.logout()

    return f"{target} was unrestricted."


@command(Privileges.ADMINISTRATOR, hidden=True)
async def alert(ctx: Context) -> Optional[str]:
    """Send a notification to all players."""
    if len(ctx.args) < 1:
        return "Invalid syntax: !alert <msg>"

    notif_txt = " ".join(ctx.args)

    app.state.sessions.players.enqueue(app.packets.notification(notif_txt))
    return "Alert sent."


@command(Privileges.ADMINISTRATOR, aliases=["alertu"], hidden=True)
async def alertuser(ctx: Context) -> Optional[str]:
    """Send a notification to a specified player by name."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !alertu <name> <msg>"

    target = app.state.sessions.players.get(name=ctx.args[0])
    if not target:
        return "Could not find a user by that name."

    notif_txt = " ".join(ctx.args[1:])

    target.enqueue(app.packets.notification(notif_txt))
    return "Alert sent."


# NOTE: this is pretty useless since it doesn't switch anything other
# than the c[e4].ppy.sh domains; it exists on bancho as a tournament
# server switch mechanism, perhaps we could leverage this in the future.
@command(Privileges.ADMINISTRATOR, hidden=True)
async def switchserv(ctx: Context) -> Optional[str]:
    """Switch your client's internal endpoints to a specified IP address."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !switch <endpoint>"

    new_bancho_ip = ctx.args[0]

    ctx.player.enqueue(app.packets.switch_tournament_server(new_bancho_ip))
    return "Have a nice journey.."


@command(Privileges.ADMINISTRATOR, aliases=["restart"])
async def shutdown(ctx: Context) -> Union[Optional[str], NoReturn]:
    """Gracefully shutdown the server."""
    if ctx.trigger == "restart":
        _signal = signal.SIGUSR1
    else:
        _signal = signal.SIGTERM

    if ctx.args:  # shutdown after a delay
        delay = timeparse(ctx.args[0])
        if not delay:
            return "Invalid timespan."

        if delay < 15:
            return "Minimum delay is 15 seconds."

        if len(ctx.args) > 1:
            # alert all online players of the reboot.
            alert_msg = (
                f"The server will {ctx.trigger} in {ctx.args[0]}.\n\n"
                f'Reason: {" ".join(ctx.args[1:])}'
            )

            app.state.sessions.players.enqueue(app.packets.notification(alert_msg))

        app.state.loop.call_later(delay, os.kill, os.getpid(), _signal)
        return f"Enqueued {ctx.trigger}."
    else:  # shutdown immediately
        os.kill(os.getpid(), _signal)


""" Developer commands
# The commands below are either dangerous or
# simply not useful for any other roles.
"""


@command(Privileges.DEVELOPER)
async def stealth(ctx: Context) -> Optional[str]:
    """Toggle the developer's stealth, allowing them to be hidden."""
    # NOTE: this command is a large work in progress and currently
    # half works; eventually it will be moved to the Admin level.
    ctx.player.stealth = not ctx.player.stealth

    return f'Stealth {"enabled" if ctx.player.stealth else "disabled"}.'


@command(Privileges.DEVELOPER)
async def recalc(ctx: Context) -> Optional[str]:
    """Recalculate pp for a given map, or all maps."""
    return (
        "Please use tools/recalc.py instead.\n"
        "If you need any support, join our Discord @ https://discord.gg/ShEQgUx."
    )


@command(Privileges.DEVELOPER, hidden=True)
async def debug(ctx: Context) -> Optional[str]:
    """Toggle the console's debug setting."""
    app.settings.DEBUG = not app.settings.DEBUG
    return f"Toggled {'on' if app.settings.DEBUG else 'off'}."


# NOTE: these commands will likely be removed
#       with the addition of a good frontend.
str_priv_dict = {
    "normal": Privileges.UNRESTRICTED,
    "verified": Privileges.VERIFIED,
    "whitelisted": Privileges.WHITELISTED,
    "supporter": Privileges.SUPPORTER,
    "premium": Privileges.PREMIUM,
    "alumni": Privileges.ALUMNI,
    "tournament": Privileges.TOURNEY_MANAGER,
    "nominator": Privileges.NOMINATOR,
    "mod": Privileges.MODERATOR,
    "admin": Privileges.ADMINISTRATOR,
    "developer": Privileges.DEVELOPER,
}


@command(Privileges.DEVELOPER, hidden=True)
async def addpriv(ctx: Context) -> Optional[str]:
    """Set privileges for a specified player (by name)."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !addpriv <name> <role1 role2 role3 ...>"

    bits = Privileges(0)

    for m in [m.lower() for m in ctx.args[1:]]:
        if m not in str_priv_dict:
            return f"Not found: {m}."

        bits |= str_priv_dict[m]

    target = await app.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return "Could not find user."

    if bits & Privileges.DONATOR != 0:
        return "Please use the !givedonator command to assign donator privileges to players."

    await target.add_privs(bits)
    return f"Updated {target}'s privileges."


@command(Privileges.DEVELOPER, hidden=True)
async def rmpriv(ctx: Context) -> Optional[str]:
    """Set privileges for a specified player (by name)."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !rmpriv <name> <role1 role2 role3 ...>"

    bits = Privileges(0)

    for m in [m.lower() for m in ctx.args[1:]]:
        if m not in str_priv_dict:
            return f"Not found: {m}."

        bits |= str_priv_dict[m]

    target = await app.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return "Could not find user."

    await target.remove_privs(bits)

    if bits & Privileges.DONATOR != 0:
        target.donor_end = 0
        await app.state.services.database.execute(
            "UPDATE users SET donor_end = 0 WHERE id = :user_id",
            {"user_id": target.id},
        )

    return f"Updated {target}'s privileges."


@command(Privileges.DEVELOPER, hidden=True)
async def givedonator(ctx: Context) -> Optional[str]:
    """Give donator status to a specified player for a specified duration."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !givedonator <name> <duration>"

    target = await app.state.sessions.players.from_cache_or_sql(name=ctx.args[0])
    if not target:
        return "Could not find user."

    timespan = timeparse(ctx.args[1])
    if not timespan:
        return "Invalid timespan."

    if target.donor_end < time.time():
        timespan += int(time.time())
    else:
        timespan += target.donor_end

    target.donor_end = timespan
    await app.state.services.database.execute(
        "UPDATE users SET donor_end = :end WHERE id = :user_id",
        {"end": timespan, "user_id": target.id},
    )

    await target.add_privs(Privileges.SUPPORTER)

    return f"Added {ctx.args[1]} of donator status to {target}."


@command(Privileges.DEVELOPER)
async def wipemap(ctx: Context) -> Optional[str]:
    # (intentionally no docstring)
    if ctx.args:
        return "Invalid syntax: !wipemap"

    if ctx.player.last_np is None or time.time() >= ctx.player.last_np["timeout"]:
        return "Please /np a map first!"

    map_md5 = ctx.player.last_np["bmap"].md5

    # delete scores from all tables
    await app.state.services.database.execute(
        "DELETE FROM scores WHERE map_md5 = :map_md5",
        {"map_md5": map_md5},
    )

    return "Scores wiped."


@command(Privileges.DEVELOPER, hidden=True)
async def menu(ctx: Context) -> Optional[str]:
    """Temporary command to illustrate the menu option idea."""
    ctx.player.send_current_menu()

    return None


@command(Privileges.DEVELOPER, aliases=["re"])
async def reload(ctx: Context) -> Optional[str]:
    """Reload a python module."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !reload <module>"

    parent, *children = ctx.args[0].split(".")

    try:
        mod = __import__(parent)
    except ModuleNotFoundError:
        return "Module not found."

    try:
        for child in children:
            mod = getattr(mod, child)
    except AttributeError:
        return f"Failed at {child}."  # type: ignore

    try:
        mod = importlib.reload(mod)
    except TypeError as exc:
        return f"{exc.args[0]}."

    return f"Reloaded {mod.__name__}"


@command(Privileges.UNRESTRICTED)
async def server(ctx: Context) -> Optional[str]:
    """Retrieve performance data about the server."""

    build_str = f"bancho.py v{app.settings.VERSION} ({app.settings.DOMAIN})"

    # get info about this process
    proc = psutil.Process(os.getpid())
    uptime = int(time.time() - proc.create_time())

    # get info about our cpu
    with open("/proc/cpuinfo") as f:
        header = "model name\t: "
        trailer = "\n"

        model_names = Counter(
            line[len(header) : -len(trailer)]
            for line in f.readlines()
            if line.startswith("model name")
        )

    # list of all cpus installed with thread count
    cpus_info = " | ".join(f"{v}x {k}" for k, v in model_names.most_common())

    # get system-wide ram usage
    sys_ram = psutil.virtual_memory()

    # output ram usage as `{bancho_used}MB / {sys_used}MB / {sys_total}MB`
    bancho_ram = proc.memory_info()[0]
    ram_values = (bancho_ram, sys_ram.used, sys_ram.total)
    ram_info = " / ".join([f"{v // 1024 ** 2}MB" for v in ram_values])

    # current state of settings
    mirror_url = app.settings.MIRROR_URL
    using_osuapi = app.settings.OSU_API_KEY != ""
    advanced_mode = app.settings.DEVELOPER_MODE
    auto_logging = app.settings.AUTOMATICALLY_REPORT_PROBLEMS

    # package versioning info
    # divide up pkg versions, 3 displayed per line, e.g.
    # aiohttp v3.6.3 | aiomysql v0.0.21 | bcrypt v3.2.0
    # cmyui v1.7.3 | datadog v0.40.1 | geoip2 v4.1.0
    # maniera v1.0.0 | mysql-connector-python v8.0.23 | orjson v3.5.1
    # psutil v5.8.0 | py3rijndael v0.3.3 | uvloop v0.15.2
    reqs = (Path.cwd() / "requirements.txt").read_text().splitlines()
    requirements_info = "\n".join(
        " | ".join("{} v{}".format(*pkg.split("==")) for pkg in section)
        for section in (reqs[i : i + 3] for i in range(0, len(reqs), 3))
    )

    return "\n".join(
        (
            f"{build_str} | uptime: {seconds_readable(uptime)}",
            f"cpu(s): {cpus_info}",
            f"ram: {ram_info}",
            f"mirror: {mirror_url} | osu!api connection: {using_osuapi}",
            f"advanced mode: {advanced_mode} | auto logging: {auto_logging}",
            "",
            "requirements",
            requirements_info,
        ),
    )


if app.settings.DEVELOPER_MODE:
    """Advanced (& potentially dangerous) commands"""

    # NOTE: some of these commands are potentially dangerous, and only
    # really intended for advanced users looking for access to lower level
    # utilities. Some may give direct access to utilties that could perform
    # harmful tasks to the underlying machine, so use at your own risk.

    from sys import modules as installed_mods

    __py_namespace: dict[str, Any] = globals() | {
        mod: __import__(mod)
        for mod in (
            "asyncio",
            "dis",
            "os",
            "sys",
            "struct",
            "discord",
            "datetime",
            "time",
            "inspect",
            "math",
            "importlib",
        )
        if mod in installed_mods
    }

    @command(Privileges.DEVELOPER)
    async def py(ctx: Context) -> Optional[str]:
        """Allow for (async) access to the python interpreter."""
        # This can be very good for getting used to bancho.py's API; just look
        # around the codebase and find things to play with in your server.
        # Ex: !py return (await app.state.sessions.players.get(name='cmyui')).status.action
        if not ctx.args:
            return "owo"

        # turn our input args into a coroutine definition string.
        definition = "\n ".join(["async def __py(ctx):", " ".join(ctx.args)])

        try:  # def __py(ctx)
            exec(definition, __py_namespace)  # add to namespace
            ret = await __py_namespace["__py"](ctx)  # await it's return
        except Exception as exc:  # return exception in osu! chat
            ret = f"{exc.__class__}: {exc}"

        if "__py" in __py_namespace:
            del __py_namespace["__py"]

        # TODO: perhaps size checks?

        if not isinstance(ret, str):
            ret = pprint.pformat(ret, compact=True)

        return ret


""" Multiplayer commands
# The commands below for multiplayer match management.
# Most commands are open to player usage.
"""

R = TypeVar("R", bound=Optional[str])


def ensure_match(
    f: Callable[[Context, Match], Awaitable[Optional[R]]],
) -> Callable[[Context], Awaitable[Optional[R]]]:
    @wraps(f)
    async def wrapper(ctx: Context) -> Optional[R]:
        match = ctx.player.match

        # multi set is a bit of a special case,
        # as we do some additional checks.
        if match is None:
            # player not in a match
            return None

        if ctx.recipient is not match.chat:
            # message not in match channel
            return None

        if f is not mp_help and (
            ctx.player not in match.refs
            and not ctx.player.priv & Privileges.TOURNEY_MANAGER
        ):
            # doesn't have privs to use !mp commands (allow help).
            return None

        return await f(ctx, match)

    return wrapper


@mp_commands.add(Privileges.UNRESTRICTED, aliases=["h"])
@ensure_match
async def mp_help(ctx: Context, match: Match) -> Optional[str]:
    """Show all documented multiplayer commands the player can access."""
    prefix = app.settings.COMMAND_PREFIX
    cmds = []

    for cmd in mp_commands.commands:
        if not cmd.doc or ctx.player.priv & cmd.priv != cmd.priv:
            # no doc, or insufficient permissions.
            continue

        cmds.append(f"{prefix}mp {cmd.triggers[0]}: {cmd.doc}")

    return "\n".join(cmds)


@mp_commands.add(Privileges.UNRESTRICTED, aliases=["st"])
@ensure_match
async def mp_start(ctx: Context, match: Match) -> Optional[str]:
    """Start the current multiplayer match, with any players ready."""
    if len(ctx.args) > 1:
        return "Invalid syntax: !mp start <force/seconds>"

    # this command can be used in a few different ways;
    # !mp start: start the match now (make sure all players are ready)
    # !mp start force: start the match now (don't check for ready)
    # !mp start N: start the match in N seconds (don't check for ready)
    # !mp start cancel: cancel the current match start timer

    if not ctx.args:
        # !mp start
        if match.starting is not None:
            time_remaining = int(match.starting["time"] - time.time())
            return f"Match starting in {time_remaining} seconds."

        if any([s.status == SlotStatus.not_ready for s in match.slots]):
            return "Not all players are ready (`!mp start force` to override)."
    else:
        if ctx.args[0].isdecimal():
            # !mp start N
            if match.starting is not None:
                time_remaining = int(match.starting["time"] - time.time())
                return f"Match starting in {time_remaining} seconds."

            # !mp start <seconds>
            duration = int(ctx.args[0])
            if not 0 < duration <= 300:
                return "Timer range is 1-300 seconds."

            def _start() -> None:
                """Remove any pending timers & start the match."""
                # remove start & alert timers
                match.starting = None

                # make sure player didn't leave the
                # match since queueing this start lol...
                if ctx.player not in {slot.player for slot in match.slots}:
                    match.chat.send_bot("Player left match? (cancelled)")
                    return

                match.start()
                match.chat.send_bot("Starting match.")

            def _alert_start(t: int) -> None:
                """Alert the match of the impending start."""
                match.chat.send_bot(f"Match starting in {t} seconds.")

            # add timers to our match object,
            # so we can cancel them if needed.
            match.starting = {
                "start": app.state.loop.call_later(duration, _start),
                "alerts": [
                    app.state.loop.call_later(duration - t, lambda t=t: _alert_start(t))
                    for t in (60, 30, 10, 5, 4, 3, 2, 1)
                    if t < duration
                ],
                "time": time.time() + duration,
            }

            return f"Match will start in {duration} seconds."
        elif ctx.args[0] in ("cancel", "c"):
            # !mp start cancel
            if match.starting is None:
                return "Match timer not active!"

            match.starting["start"].cancel()
            for alert in match.starting["alerts"]:
                alert.cancel()

            match.starting = None

            return "Match timer cancelled."
        elif ctx.args[0] not in ("force", "f"):
            return "Invalid syntax: !mp start <force/seconds>"
        # !mp start force simply passes through

    match.start()
    return "Good luck!"


@mp_commands.add(Privileges.UNRESTRICTED, aliases=["a"])
@ensure_match
async def mp_abort(ctx: Context, match: Match) -> Optional[str]:
    """Abort the current in-progress multiplayer match."""
    if not match.in_progress:
        return "Abort what?"

    match.unready_players(expected=SlotStatus.playing)

    match.in_progress = False
    match.enqueue(app.packets.match_abort())
    match.enqueue_state()
    return "Match aborted."


@mp_commands.add(Privileges.UNRESTRICTED)
@ensure_match
async def mp_map(ctx: Context, match: Match) -> Optional[str]:
    """Set the current match's current map by id."""
    if len(ctx.args) != 1 or not ctx.args[0].isdecimal():
        return "Invalid syntax: !mp map <beatmapid>"

    map_id = int(ctx.args[0])

    if map_id == match.map_id:
        return "Map already selected."

    bmap = await Beatmap.from_bid(map_id)
    if not bmap:
        return "Beatmap not found."

    match.map_id = bmap.id
    match.map_md5 = bmap.md5
    match.map_name = bmap.full_name

    match.mode = bmap.mode

    match.enqueue_state()
    return f"Selected: {bmap.embed}."


@mp_commands.add(Privileges.UNRESTRICTED)
@ensure_match
async def mp_mods(ctx: Context, match: Match) -> Optional[str]:
    """Set the current match's mods, from string form."""
    if len(ctx.args) != 1 or len(ctx.args[0]) % 2 != 0:
        return "Invalid syntax: !mp mods <mods>"

    mods = Mods.from_modstr(ctx.args[0])
    mods = mods.filter_invalid_combos(match.mode.as_vanilla)

    if match.freemods:
        if ctx.player is match.host:
            # allow host to set speed-changing mods.
            match.mods = mods & SPEED_CHANGING_MODS

        # set slot mods
        slot = match.get_slot(ctx.player)
        assert slot is not None

        slot.mods = mods & ~SPEED_CHANGING_MODS
    else:
        # not freemods, set match mods.
        match.mods = mods

    match.enqueue_state()
    return "Match mods updated."


@mp_commands.add(Privileges.UNRESTRICTED, aliases=["fm", "fmods"])
@ensure_match
async def mp_freemods(ctx: Context, match: Match) -> Optional[str]:
    """Toggle freemods status for the match."""
    if len(ctx.args) != 1 or ctx.args[0] not in ("on", "off"):
        return "Invalid syntax: !mp freemods <on/off>"

    if ctx.args[0] == "on":
        # central mods -> all players mods.
        match.freemods = True

        for s in match.slots:
            if s.player is not None:
                # the slot takes any non-speed
                # changing mods from the match.
                s.mods = match.mods & ~SPEED_CHANGING_MODS

        match.mods &= SPEED_CHANGING_MODS
    else:
        # host mods -> central mods.
        match.freemods = False

        host_slot = match.get_host_slot()
        assert host_slot is not None

        # the match keeps any speed-changing mods,
        # and also takes any mods the host has enabled.
        match.mods &= SPEED_CHANGING_MODS
        match.mods |= host_slot.mods

        for s in match.slots:
            if s.player is not None:
                s.mods = Mods.NOMOD

    match.enqueue_state()
    return "Match freemod status updated."


@mp_commands.add(Privileges.UNRESTRICTED)
@ensure_match
async def mp_host(ctx: Context, match: Match) -> Optional[str]:
    """Set the current match's current host by id."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp host <name>"

    target = app.state.sessions.players.get(name=ctx.args[0])
    if not target:
        return "Could not find a user by that name."

    if target is match.host:
        return "They're already host, silly!"

    if target not in {slot.player for slot in match.slots}:
        return "Found no such player in the match."

    match.host_id = target.id

    match.host.enqueue(app.packets.match_transfer_host())
    match.enqueue_state(lobby=True)
    return "Match host updated."


@mp_commands.add(Privileges.UNRESTRICTED)
@ensure_match
async def mp_randpw(ctx: Context, match: Match) -> Optional[str]:
    """Randomize the current match's password."""
    match.passwd = secrets.token_hex(8)
    return "Match password randomized."


@mp_commands.add(Privileges.UNRESTRICTED, aliases=["inv"])
@ensure_match
async def mp_invite(ctx: Context, match: Match) -> Optional[str]:
    """Invite a player to the current match by name."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp invite <name>"

    target = app.state.sessions.players.get(name=ctx.args[0])
    if not target:
        return "Could not find a user by that name."

    if target is app.state.sessions.bot:
        return "I'm too busy!"

    if target is ctx.player:
        return "You can't invite yourself!"

    target.enqueue(app.packets.match_invite(ctx.player, target.name))
    return f"Invited {target} to the match."


@mp_commands.add(Privileges.UNRESTRICTED)
@ensure_match
async def mp_addref(ctx: Context, match: Match) -> Optional[str]:
    """Add a referee to the current match by name."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp addref <name>"

    target = app.state.sessions.players.get(name=ctx.args[0])
    if not target:
        return "Could not find a user by that name."

    if target not in {slot.player for slot in match.slots}:
        return "User must be in the current match!"

    if target in match.refs:
        return f"{target} is already a match referee!"

    match._refs.add(target)
    return f"{target.name} added to match referees."


@mp_commands.add(Privileges.UNRESTRICTED)
@ensure_match
async def mp_rmref(ctx: Context, match: Match) -> Optional[str]:
    """Remove a referee from the current match by name."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp addref <name>"

    target = app.state.sessions.players.get(name=ctx.args[0])
    if not target:
        return "Could not find a user by that name."

    if target not in match.refs:
        return f"{target} is not a match referee!"

    if target is match.host:
        return "The host is always a referee!"

    match._refs.remove(target)
    return f"{target.name} removed from match referees."


@mp_commands.add(Privileges.UNRESTRICTED)
@ensure_match
async def mp_listref(ctx: Context, match: Match) -> Optional[str]:
    """List all referees from the current match."""
    return ", ".join(map(str, match.refs)) + "."


@mp_commands.add(Privileges.UNRESTRICTED)
@ensure_match
async def mp_lock(ctx: Context, match: Match) -> Optional[str]:
    """Lock all unused slots in the current match."""
    for slot in match.slots:
        if slot.status == SlotStatus.open:
            slot.status = SlotStatus.locked

    match.enqueue_state()
    return "All unused slots locked."


@mp_commands.add(Privileges.UNRESTRICTED)
@ensure_match
async def mp_unlock(ctx: Context, match: Match) -> Optional[str]:
    """Unlock locked slots in the current match."""
    for slot in match.slots:
        if slot.status == SlotStatus.locked:
            slot.status = SlotStatus.open

    match.enqueue_state()
    return "All locked slots unlocked."


@mp_commands.add(Privileges.UNRESTRICTED)
@ensure_match
async def mp_teams(ctx: Context, match: Match) -> Optional[str]:
    """Change the team type for the current match."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp teams <type>"

    team_type = ctx.args[0]

    if team_type in ("ffa", "freeforall", "head-to-head"):
        match.team_type = MatchTeamTypes.head_to_head
    elif team_type in ("tag", "coop", "co-op", "tag-coop"):
        match.team_type = MatchTeamTypes.tag_coop
    elif team_type in ("teams", "team-vs", "teams-vs"):
        match.team_type = MatchTeamTypes.team_vs
    elif team_type in ("tag-teams", "tag-team-vs", "tag-teams-vs"):
        match.team_type = MatchTeamTypes.tag_team_vs
    else:
        return "Unknown team type. (ffa, tag, teams, tag-teams)"

    # find the new appropriate default team.
    # defaults are (ffa: neutral, teams: red).
    if match.team_type in (MatchTeamTypes.head_to_head, MatchTeamTypes.tag_coop):
        new_t = MatchTeams.neutral
    else:
        new_t = MatchTeams.red

    # change each active slots team to
    # fit the correspoding team type.
    for s in match.slots:
        if s.player is not None:
            s.team = new_t

    if match.is_scrimming:
        # reset score if scrimming.
        match.reset_scrim()

    match.enqueue_state()
    return "Match team type updated."


@mp_commands.add(Privileges.UNRESTRICTED, aliases=["cond"])
@ensure_match
async def mp_condition(ctx: Context, match: Match) -> Optional[str]:
    """Change the win condition for the match."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp condition <type>"

    cond = ctx.args[0]

    if cond == "pp":
        # special case - pp can't actually be used as an ingame
        # win condition, but bancho.py allows it to be passed into
        # this command during a scrims to use pp as a win cond.
        if not match.is_scrimming:
            return "PP is only useful as a win condition during scrims."
        if match.use_pp_scoring:
            return "PP scoring already enabled."

        match.use_pp_scoring = True
    else:
        if match.use_pp_scoring:
            match.use_pp_scoring = False

        if cond == "score":
            match.win_condition = MatchWinConditions.score
        elif cond in ("accuracy", "acc"):
            match.win_condition = MatchWinConditions.accuracy
        elif cond == "combo":
            match.win_condition = MatchWinConditions.combo
        elif cond in ("scorev2", "v2"):
            match.win_condition = MatchWinConditions.scorev2
        else:
            return "Invalid win condition. (score, acc, combo, scorev2, *pp)"

    match.enqueue_state(lobby=False)
    return "Match win condition updated."


@mp_commands.add(Privileges.UNRESTRICTED, aliases=["autoref"])
@ensure_match
async def mp_scrim(ctx: Context, match: Match) -> Optional[str]:
    """Start a scrim in the current match."""
    r_match = regexes.BEST_OF.fullmatch(ctx.args[0])
    if len(ctx.args) != 1 or not r_match:
        return "Invalid syntax: !mp scrim <bo#>"

    best_of = int(r_match[1])
    if not 0 <= best_of < 16:
        return "Best of must be in range 0-15."

    winning_pts = (best_of // 2) + 1

    if winning_pts != 0:
        # setting to real num
        if match.is_scrimming:
            return "Already scrimming!"

        if best_of % 2 == 0:
            return "Best of must be an odd number!"

        match.is_scrimming = True
        msg = (
            f"A scrimmage has been started by {ctx.player.name}; "
            f"first to {winning_pts} points wins. Best of luck!"
        )
    else:
        # setting to 0
        if not match.is_scrimming:
            return "Not currently scrimming!"

        match.is_scrimming = False
        match.reset_scrim()
        msg = "Scrimming cancelled."

    match.winning_pts = winning_pts
    return msg


@mp_commands.add(Privileges.UNRESTRICTED, aliases=["end"])
@ensure_match
async def mp_endscrim(ctx: Context, match: Match) -> Optional[str]:
    """End the current matches ongoing scrim."""
    if not match.is_scrimming:
        return "Not currently scrimming!"

    match.is_scrimming = False
    match.reset_scrim()
    return "Scrimmage ended."  # TODO: final score (get_score method?)


@mp_commands.add(Privileges.UNRESTRICTED, aliases=["rm"])
@ensure_match
async def mp_rematch(ctx: Context, match: Match) -> Optional[str]:
    """Restart a scrim, or roll back previous match point."""
    if ctx.args:
        return "Invalid syntax: !mp rematch"

    if ctx.player is not match.host:
        return "Only available to the host."

    if not match.is_scrimming:
        if match.winning_pts == 0:
            msg = "No scrim to rematch; to start one, use !mp scrim."
        else:
            # re-start scrimming with old points
            match.is_scrimming = True
            msg = (
                f"A rematch has been started by {ctx.player.name}; "
                f"first to {match.winning_pts} points wins. Best of luck!"
            )
    else:
        # reset the last match point awarded
        if not match.winners:
            return "No match points have yet been awarded!"

        recent_winner = match.winners[-1]
        if recent_winner is None:
            return "The last point was a tie!"

        match.match_points[recent_winner] -= 1  # TODO: team name
        match.winners.pop()

        msg = f"A point has been deducted from {recent_winner}."

    return msg


@mp_commands.add(Privileges.ADMINISTRATOR, aliases=["f"], hidden=True)
@ensure_match
async def mp_force(ctx: Context, match: Match) -> Optional[str]:
    """Force a player into the current match by name."""
    # NOTE: this overrides any limits such as silences or passwd.
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp force <name>"

    target = app.state.sessions.players.get(name=ctx.args[0])
    if not target:
        return "Could not find a user by that name."

    target.join_match(match, match.passwd)
    return "Welcome."


# mappool-related mp commands


@mp_commands.add(Privileges.UNRESTRICTED, aliases=["lp"])
@ensure_match
async def mp_loadpool(ctx: Context, match: Match) -> Optional[str]:
    """Load a mappool into the current match."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp loadpool <name>"

    if ctx.player is not match.host:
        return "Only available to the host."

    name = ctx.args[0]

    pool = app.state.sessions.pools.get_by_name(name)
    if not pool:
        return "Could not find a pool by that name!"

    if match.pool is pool:
        return f"{pool!r} already selected!"

    match.pool = pool
    return f"{pool!r} selected."


@mp_commands.add(Privileges.UNRESTRICTED, aliases=["ulp"])
@ensure_match
async def mp_unloadpool(ctx: Context, match: Match) -> Optional[str]:
    """Unload the current matches mappool."""
    if ctx.args:
        return "Invalid syntax: !mp unloadpool"

    if ctx.player is not match.host:
        return "Only available to the host."

    if not match.pool:
        return "No mappool currently selected!"

    match.pool = None
    return "Mappool unloaded."


@mp_commands.add(Privileges.UNRESTRICTED)
@ensure_match
async def mp_ban(ctx: Context, match: Match) -> Optional[str]:
    """Ban a pick in the currently loaded mappool."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp ban <pick>"

    if not match.pool:
        return "No pool currently selected!"

    mods_slot = ctx.args[0]

    # separate mods & slot
    r_match = regexes.MAPPOOL_PICK.fullmatch(mods_slot)
    if not r_match:
        return "Invalid pick syntax; correct example: HD2"

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(r_match[1])
    slot = int(r_match[2])

    if (mods, slot) not in match.pool.maps:
        return f"Found no {mods_slot} pick in the pool."

    if (mods, slot) in match.bans:
        return "That pick is already banned!"

    match.bans.add((mods, slot))
    return f"{mods_slot} banned."


@mp_commands.add(Privileges.UNRESTRICTED)
@ensure_match
async def mp_unban(ctx: Context, match: Match) -> Optional[str]:
    """Unban a pick in the currently loaded mappool."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp unban <pick>"

    if not match.pool:
        return "No pool currently selected!"

    mods_slot = ctx.args[0]

    # separate mods & slot
    r_match = regexes.MAPPOOL_PICK.fullmatch(mods_slot)
    if not r_match:
        return "Invalid pick syntax; correct example: HD2"

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(r_match[1])
    slot = int(r_match[2])

    if (mods, slot) not in match.pool.maps:
        return f"Found no {mods_slot} pick in the pool."

    if (mods, slot) not in match.bans:
        return "That pick is not currently banned!"

    match.bans.remove((mods, slot))
    return f"{mods_slot} unbanned."


@mp_commands.add(Privileges.UNRESTRICTED)
@ensure_match
async def mp_pick(ctx: Context, match: Match) -> Optional[str]:
    """Pick a map from the currently loaded mappool."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !mp pick <pick>"

    if not match.pool:
        return "No pool currently loaded!"

    mods_slot = ctx.args[0]

    # separate mods & slot
    r_match = regexes.MAPPOOL_PICK.fullmatch(mods_slot)
    if not r_match:
        return "Invalid pick syntax; correct example: HD2"

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(r_match[1])
    slot = int(r_match[2])

    if (mods, slot) not in match.pool.maps:
        return f"Found no {mods_slot} pick in the pool."

    if (mods, slot) in match.bans:
        return f"{mods_slot} has been banned from being picked."

    # update match beatmap to the picked map.
    bmap = match.pool.maps[(mods, slot)]
    match.map_md5 = bmap.md5
    match.map_id = bmap.id
    match.map_name = bmap.full_name

    # TODO: some kind of abstraction allowing
    # for something like !mp pick fm.
    if match.freemods:
        # if freemods are enabled, disable them.
        match.freemods = False

        for s in match.slots:
            if s.player is not None:
                s.mods = Mods.NOMOD

    # update match mods to the picked map.
    match.mods = mods

    match.enqueue_state()

    return f"Picked {bmap.embed}. ({mods_slot})"


""" Mappool management commands
# The commands below are for event managers
# and tournament hosts/referees to help automate
# tedious processes of running tournaments.
"""


@pool_commands.add(Privileges.TOURNEY_MANAGER, aliases=["h"], hidden=True)
async def pool_help(ctx: Context) -> Optional[str]:
    """Show all documented mappool commands the player can access."""
    prefix = app.settings.COMMAND_PREFIX
    cmds = []

    for cmd in pool_commands.commands:
        if not cmd.doc or ctx.player.priv & cmd.priv != cmd.priv:
            # no doc, or insufficient permissions.
            continue

        cmds.append(f"{prefix}pool {cmd.triggers[0]}: {cmd.doc}")

    return "\n".join(cmds)


@pool_commands.add(Privileges.TOURNEY_MANAGER, aliases=["c"], hidden=True)
async def pool_create(ctx: Context) -> Optional[str]:
    """Add a new mappool to the database."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !pool create <name>"

    name = ctx.args[0]

    if app.state.sessions.pools.get_by_name(name):
        return "Pool already exists by that name!"

    # insert pool into db
    await app.state.services.database.execute(
        "INSERT INTO tourney_pools "
        "(name, created_at, created_by) "
        "VALUES (:name, NOW(), :user_id)",
        {"name": name, "user_id": ctx.player.id},
    )

    # add to cache (get from sql for id & time)
    row = await app.state.services.database.fetch_one(
        "SELECT * FROM tourney_pools WHERE name = :name",
        {"name": name},
    )
    assert row is not None

    row = dict(row)  # make mutable copy

    pool_creator = await app.state.sessions.players.from_cache_or_sql(
        id=row["created_by"],
    )
    assert pool_creator is not None

    app.state.sessions.pools.append(
        MapPool(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            created_by=pool_creator,
        ),
    )

    return f"{name} created."


@pool_commands.add(Privileges.TOURNEY_MANAGER, aliases=["del", "d"], hidden=True)
async def pool_delete(ctx: Context) -> Optional[str]:
    """Remove a mappool from the database."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !pool delete <name>"

    name = ctx.args[0]

    pool = app.state.sessions.pools.get_by_name(name)
    if not pool:
        return "Could not find a pool by that name!"

    # delete from db
    await app.state.services.database.execute(
        "DELETE FROM tourney_pools WHERE id = :pool_id",
        {"pool_id": pool.id},
    )

    await app.state.services.database.execute(
        "DELETE FROM tourney_pool_maps WHERE pool_id = :pool_id",
        {"pool_id": pool.id},
    )

    # remove from cache
    app.state.sessions.pools.remove(pool)

    return f"{name} deleted."


@pool_commands.add(Privileges.TOURNEY_MANAGER, aliases=["a"], hidden=True)
async def pool_add(ctx: Context) -> Optional[str]:
    """Add a new map to a mappool in the database."""
    if len(ctx.args) != 2:
        return "Invalid syntax: !pool add <name> <pick>"

    if ctx.player.last_np is None or time.time() >= ctx.player.last_np["timeout"]:
        return "Please /np a map first!"

    name, mods_slot = ctx.args
    mods_slot = mods_slot.upper()  # ocd
    bmap = ctx.player.last_np["bmap"]

    # separate mods & slot
    r_match = regexes.MAPPOOL_PICK.fullmatch(mods_slot)
    if not r_match:
        return "Invalid pick syntax; correct example: HD2"

    if len(r_match[1]) % 2 != 0:
        return "Invalid mods."

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(r_match[1])
    slot = int(r_match[2])

    pool = app.state.sessions.pools.get_by_name(name)
    if not pool:
        return "Could not find a pool by that name!"

    if (mods, slot) in pool.maps:
        return f"{mods_slot} is already {pool.maps[(mods, slot)].embed}!"

    if bmap in pool.maps.values():
        return "Map is already in the pool!"

    # insert into db
    await app.state.services.database.execute(
        "INSERT INTO tourney_pool_maps "
        "(map_id, pool_id, mods, slot) "
        "VALUES (:map_id, :pool_id, :mods, :slot)",
        {"map_id": bmap.id, "pool_id": pool.id, "mods": mods, "slot": slot},
    )

    # add to cache
    pool.maps[(mods, slot)] = bmap

    return f"{bmap.embed} added to {name}."


@pool_commands.add(Privileges.TOURNEY_MANAGER, aliases=["rm", "r"], hidden=True)
async def pool_remove(ctx: Context) -> Optional[str]:
    """Remove a map from a mappool in the database."""
    if len(ctx.args) != 2:
        return "Invalid syntax: !pool remove <name> <pick>"

    name, mods_slot = ctx.args
    mods_slot = mods_slot.upper()  # ocd

    # separate mods & slot
    r_match = regexes.MAPPOOL_PICK.fullmatch(mods_slot)
    if not r_match:
        return "Invalid pick syntax; correct example: HD2"

    # not calling mods.filter_invalid_combos here intentionally.
    mods = Mods.from_modstr(r_match[1])
    slot = int(r_match[2])

    pool = app.state.sessions.pools.get_by_name(name)
    if not pool:
        return "Could not find a pool by that name!"

    if (mods, slot) not in pool.maps:
        return f"Found no {mods_slot} pick in the pool."

    # delete from db
    await app.state.services.database.execute(
        "DELETE FROM tourney_pool_maps WHERE mods = :mods AND slot = :slot",
        {"mods": mods, "slot": slot},
    )

    # remove from cache
    del pool.maps[(mods, slot)]

    return f"{mods_slot} removed from {name}."


@pool_commands.add(Privileges.TOURNEY_MANAGER, aliases=["l"], hidden=True)
async def pool_list(ctx: Context) -> Optional[str]:
    """List all existing mappools information."""
    pools = app.state.sessions.pools
    if not pools:
        return "There are currently no pools!"

    l = [f"Mappools ({len(pools)})"]

    for pool in pools:
        l.append(
            f"[{pool.created_at:%Y-%m-%d}] {pool.id}. "
            f"{pool.name}, by {pool.created_by}.",
        )

    return "\n".join(l)


@pool_commands.add(Privileges.TOURNEY_MANAGER, aliases=["i"], hidden=True)
async def pool_info(ctx: Context) -> Optional[str]:
    """Get all information for a specific mappool."""
    if len(ctx.args) != 1:
        return "Invalid syntax: !pool info <name>"

    name = ctx.args[0]

    pool = app.state.sessions.pools.get_by_name(name)
    if not pool:
        return "Could not find a pool by that name!"

    _time = pool.created_at.strftime("%H:%M:%S%p")
    _date = pool.created_at.strftime("%Y-%m-%d")
    datetime_fmt = f"Created at {_time} on {_date}"
    l = [f"{pool.id}. {pool.name}, by {pool.created_by} | {datetime_fmt}."]

    for (mods, slot), bmap in pool.maps.items():
        l.append(f"{mods!r}{slot}: {bmap.embed}")

    return "\n".join(l)


""" Clan managment commands
# The commands below are for managing bancho.py
# clans, for users, clan staff, and server staff.
"""


@clan_commands.add(Privileges.UNRESTRICTED, aliases=["h"])
async def clan_help(ctx: Context) -> Optional[str]:
    """Show all documented clan commands the player can access."""
    prefix = app.settings.COMMAND_PREFIX
    cmds = []

    for cmd in clan_commands.commands:
        if not cmd.doc or ctx.player.priv & cmd.priv != cmd.priv:
            # no doc, or insufficient permissions.
            continue

        cmds.append(f"{prefix}clan {cmd.triggers[0]}: {cmd.doc}")

    return "\n".join(cmds)


@clan_commands.add(Privileges.UNRESTRICTED, aliases=["c"])
async def clan_create(ctx: Context) -> Optional[str]:
    """Create a clan with a given tag & name."""
    if len(ctx.args) < 2:
        return "Invalid syntax: !clan create <tag> <name>"

    tag = ctx.args[0].upper()
    if not 1 <= len(tag) <= 6:
        return "Clan tag may be 1-6 characters long."

    name = " ".join(ctx.args[1:])
    if not 2 <= len(name) <= 16:
        return "Clan name may be 2-16 characters long."

    if ctx.player.clan:
        return f"You're already a member of {ctx.player.clan}!"

    if app.state.sessions.clans.get(name=name):
        return "That name has already been claimed by another clan."

    if app.state.sessions.clans.get(tag=tag):
        return "That tag has already been claimed by another clan."

    created_at = datetime.now()

    # add clan to sql
    clan = await clans_repo.create(
        name=name,
        tag=tag,
        owner=ctx.player.id,
    )

    # add clan to cache
    clan = Clan(
        id=clan["id"],
        name=name,
        tag=tag,
        created_at=created_at,
        owner_id=ctx.player.id,
    )
    app.state.sessions.clans.append(clan)

    # set owner's clan & clan priv (cache & sql)
    ctx.player.clan = clan
    ctx.player.clan_priv = ClanPrivileges.Owner

    clan.owner_id = ctx.player.id
    clan.member_ids.add(ctx.player.id)

    await players_repo.update(
        ctx.player.id,
        clan_id=clan.id,
        clan_priv=ClanPrivileges.Owner,
    )

    # announce clan creation
    announce_chan = app.state.sessions.channels["#announce"]
    if announce_chan:
        msg = f"\x01ACTION founded {clan!r}."
        announce_chan.send(msg, sender=ctx.player, to_self=True)

    return f"{clan!r} created."


@clan_commands.add(Privileges.UNRESTRICTED, aliases=["delete", "d"])
async def clan_disband(ctx: Context) -> Optional[str]:
    """Disband a clan (admins may disband others clans)."""
    if ctx.args:
        # disband a specified clan by tag
        if ctx.player not in app.state.sessions.players.staff:
            return "Only staff members may disband the clans of others."

        clan = app.state.sessions.clans.get(tag=" ".join(ctx.args).upper())
        if not clan:
            return "Could not find a clan by that tag."
    else:
        # disband the player's clan
        clan = ctx.player.clan
        if not clan:
            return "You're not a member of a clan!"

    await clans_repo.delete(clan.id)
    app.state.sessions.clans.remove(clan)

    # remove all members from the clan,
    # reset their clan privs (cache & sql).
    # NOTE: only online players need be to be uncached.
    for member_id in clan.member_ids:
        await players_repo.update(member_id, clan_id=0, clan_priv=0)

        member = app.state.sessions.players.get(id=member_id)
        if member:
            member.clan = None
            member.clan_priv = None

    # announce clan disbanding
    announce_chan = app.state.sessions.channels["#announce"]
    if announce_chan:
        msg = f"\x01ACTION disbanded {clan!r}."
        announce_chan.send(msg, sender=ctx.player, to_self=True)

    return f"{clan!r} disbanded."


@clan_commands.add(Privileges.UNRESTRICTED, aliases=["i"])
async def clan_info(ctx: Context) -> Optional[str]:
    """Lookup information of a clan by tag."""
    if not ctx.args:
        return "Invalid syntax: !clan info <tag>"

    clan = app.state.sessions.clans.get(tag=" ".join(ctx.args).upper())
    if not clan:
        return "Could not find a clan by that tag."

    msg = [f"{clan!r} | Founded {clan.created_at:%b %d, %Y}."]

    # get members privs from sql
    clan_members = await players_repo.fetch_many(clan_id=clan.id)
    for member in sorted(clan_members, key=lambda m: m["clan_priv"], reverse=True):
        priv_str = ("Member", "Officer", "Owner")[member["clan_priv"] - 1]
        msg.append(f"[{priv_str}] {member['name']}")

    return "\n".join(msg)


@clan_commands.add(Privileges.UNRESTRICTED)
async def clan_leave(ctx: Context):
    """Leaves the clan you're in."""
    if not ctx.player.clan:
        return "You're not in a clan."
    elif ctx.player.clan_priv == ClanPrivileges.Owner:
        return "You must transfer your clan's ownership before leaving it. Alternatively, you can use !clan disband."

    await ctx.player.clan.remove_member(ctx.player)
    return f"You have successfully left {ctx.player.clan!r}."


# TODO: !clan inv, !clan join, !clan leave


@clan_commands.add(Privileges.UNRESTRICTED, aliases=["l"])
async def clan_list(ctx: Context) -> Optional[str]:
    """List all existing clans' information."""
    if ctx.args:
        if len(ctx.args) != 1 or not ctx.args[0].isdecimal():
            return "Invalid syntax: !clan list (page)"
        else:
            offset = 25 * int(ctx.args[0])
    else:
        offset = 0

    total_clans = len(app.state.sessions.clans)
    if offset >= total_clans:
        return "No clans found."

    msg = [f"bancho.py clans listing ({total_clans} total)."]

    for idx, clan in enumerate(app.state.sessions.clans, offset):
        msg.append(f"{idx + 1}. {clan!r}")

    return "\n".join(msg)


class CommandResponse(TypedDict):
    resp: Optional[str]
    hidden: bool


async def process_commands(
    player: Player,
    target: Union["Channel", Player],
    msg: str,
) -> Optional[CommandResponse]:
    # response is either a CommandResponse if we hit a command,
    # or simply False if we don't have any command hits.
    start_time = clock_ns()

    prefix_len = len(app.settings.COMMAND_PREFIX)
    trigger, *args = msg[prefix_len:].strip().split(" ")

    # case-insensitive triggers
    trigger = trigger.lower()

    # check if any command sets match.
    for cmd_set in command_sets:
        if trigger == cmd_set.trigger:
            if not args:
                args = ["help"]

            trigger, *args = args  # get subcommand

            # case-insensitive triggers
            trigger = trigger.lower()

            commands = cmd_set.commands
            break
    else:
        # no set commands matched, check normal commands.
        commands = regular_commands

    for cmd in commands:
        if trigger in cmd.triggers and player.priv & cmd.priv == cmd.priv:
            # found matching trigger with sufficient privs
            try:
                res = await cmd.callback(
                    Context(
                        player=player,
                        trigger=trigger,
                        args=args,
                        recipient=target,
                    ),
                )
            except Exception:
                # print exception info to the console,
                # but do not break the player's session.
                traceback.print_exc()

                res = "An exception occurred when running the command."

            if res is not None:
                # we have a message to return, include elapsed time
                elapsed = app.logging.magnitude_fmt_time(clock_ns() - start_time)
                return {"resp": f"{res} | Elapsed: {elapsed}", "hidden": cmd.hidden}
            else:
                # no message to return
                return {"resp": None, "hidden": False}

    return None
