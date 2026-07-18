from __future__ import annotations

from functools import partial
from unittest.mock import Mock

import pytest

import app.packets
import app.settings
from app.command_router import CommandRouter
from app.command_router import Context
from app.commands import ParsingError
from app.commands import build_command_router
from app.commands import mp_abort
from app.commands import parse__with__command_args
from app.commands import restrict
from app.commands import status_to_id
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import Privileges
from app.objects.channel import Channel
from app.objects.collections import Players
from app.objects.match import Match
from app.objects.match import MatchTeamTypes
from app.objects.match import MatchWinConditions
from app.objects.match import SlotStatus
from app.objects.player import Player


class _RecordingPlayer(Player):
    def __init__(
        self,
        *,
        id: int,
        name: str,
        priv: Privileges,
    ) -> None:
        super().__init__(
            id=id,
            name=name,
            priv=priv,
            pw_bcrypt=None,
            token=Player.generate_token(),
        )
        self.restriction: tuple[Player, str] | None = None
        self.logged_out = False

    async def restrict(self, admin: Player, reason: str) -> None:
        self.restriction = (admin, reason)
        self.priv &= ~Privileges.UNRESTRICTED

    def logout(self) -> None:
        self.logged_out = True


class _FakePlayersService:
    def __init__(self, players: Players) -> None:
        self.players = players

    async def fetch_player_session(
        self,
        *,
        user_id: int | None,
        username: str | None,
    ) -> Player | None:
        return self.players.get(id=user_id, name=username)


class _RecordingModerationService:
    async def restrict(
        self,
        player: Player,
        *,
        admin: Player,
        reason: str,
    ) -> None:
        assert isinstance(player, _RecordingPlayer)
        player.restriction = (admin, reason)
        player.priv &= ~Privileges.UNRESTRICTED
        player.logout()


def _player(*, id: int, name: str, priv: Privileges) -> Player:
    return Player(
        id=id,
        name=name,
        priv=priv,
        pw_bcrypt=None,
        token=Player.generate_token(),
    )


def _router() -> CommandRouter:
    return CommandRouter(
        prefix=app.settings.COMMAND_PREFIX,
        clock=lambda: 0,
        format_elapsed=lambda elapsed: f"{elapsed}ns",
    )


async def _fetch_beatmap(value: int | str) -> None:
    return None


async def _ensure_osu_file_available(
    beatmap_id: int,
    *,
    expected_md5: str,
) -> bool:
    return True


def _match(*, host: Player, guest: Player | None = None) -> Match:
    chat = Channel("#multi_0", "test match", instance=True)
    lobby = Channel("#lobby", "multiplayer lobby")
    match = Match(
        id=0,
        name="test match",
        password="",
        has_public_history=True,
        map_name="Artist - Title [Difficulty]",
        map_id=123,
        map_md5="0123456789abcdef0123456789abcdef",
        host_id=host.id,
        mode=GameMode.VANILLA_OSU,
        mods=Mods.NOMOD,
        win_condition=MatchWinConditions.score,
        team_type=MatchTeamTypes.head_to_head,
        freemods=False,
        seed=0,
        chat_channel=chat,
        lobby_channel=lobby,
    )
    match.slots[0].player = host
    match.slots[0].status = SlotStatus.playing
    chat.append(host)
    host.match = match
    if guest is not None:
        match.slots[1].player = guest
        match.slots[1].status = SlotStatus.playing
        chat.append(guest)
        guest.match = match
    return match


def test_with_command_arg_parser_accepts_acc_misses_combo_and_mods() -> None:
    parsed = parse__with__command_args(0, ["95.5%", "1m", "429x", "+hddt"])

    assert parsed == {
        "acc": 95.5,
        "mods": Mods.HIDDEN | Mods.DOUBLETIME,
        "combo": 429,
        "nmiss": 1,
    }


@pytest.mark.parametrize(
    ("args", "expected_error"),
    [
        ([], "Invalid syntax: !with <acc/nmiss/combo/mods ...>"),
        (["101%"], "Invalid accuracy."),
        (["bad"], "Unknown argument: bad"),
    ],
)
def test_with_command_arg_parser_rejects_invalid_args(
    args: list[str],
    expected_error: str,
) -> None:
    parsed = parse__with__command_args(0, args)

    assert isinstance(parsed, ParsingError)
    assert str(parsed) == expected_error


@pytest.mark.parametrize(
    ("status", "expected_id"),
    [
        ("unrank", 0),
        ("rank", 2),
        ("love", 5),
    ],
)
def test_status_to_id(status: str, expected_id: int) -> None:
    assert status_to_id(status) == expected_id


def test_build_command_router_registers_all_production_commands() -> None:
    bot = _player(id=1, name="bot", priv=Privileges.UNRESTRICTED)
    router = build_command_router(
        prefix="!",
        clock=lambda: 0,
        format_elapsed=lambda elapsed: f"{elapsed}ns",
        developer_mode=True,
        players=Players(),
        players_service=Mock(),
        channels=Mock(),
        bot=bot,
        api_keys={},
        database=Mock(),
        loop=Mock(),
        beatmap_cache={},
        beatmapset_cache={},
        users=Mock(),
        map_requests=Mock(),
        maps=Mock(),
        logs=Mock(),
        clans_repository=Mock(),
        clans=Mock(),
        tourney_pools=Mock(),
        performance=Mock(),
        player_sessions=Mock(),
        player_moderation=Mock(),
        relationships=Mock(),
        fetch_beatmap_by_id=_fetch_beatmap,
        fetch_beatmap_by_md5=_fetch_beatmap,
        ensure_osu_file_available=_ensure_osu_file_available,
    )

    assert len(router.commands) == 35
    assert {group.trigger: len(group.commands) for group in router.groups} == {
        "mp": 25,
        "pool": 7,
        "clan": 7,
    }

    restrict_command = next(
        command for command in router.commands if "restrict" in command.triggers
    )
    assert restrict_command.privileges is Privileges.ADMINISTRATOR
    assert restrict_command.hidden is True


async def test_command_dispatch_requires_the_commands_privilege() -> None:
    router = _router()
    player = _player(
        id=3,
        name="ordinary player",
        priv=Privileges.UNRESTRICTED | Privileges.VERIFIED,
    )
    target = _RecordingPlayer(
        id=4,
        name="target",
        priv=Privileges.UNRESTRICTED | Privileges.VERIFIED,
    )
    callback_called = False

    @router.command("restrict", privileges=Privileges.ADMINISTRATOR)
    async def restricted_command(context: Context) -> None:
        nonlocal callback_called
        callback_called = True

    response = await router.process(
        player,
        player,
        f"{app.settings.COMMAND_PREFIX}restrict target cc",
    )

    assert response is None
    assert callback_called is False
    assert target.restriction is None
    assert target.logged_out is False


async def test_restrict_command_expands_reason_and_refreshes_online_target() -> None:
    router = _router()
    admin = _player(
        id=3,
        name="admin",
        priv=(Privileges.UNRESTRICTED | Privileges.VERIFIED | Privileges.ADMINISTRATOR),
    )
    target = _RecordingPlayer(
        id=4,
        name="target",
        priv=Privileges.UNRESTRICTED | Privileges.VERIFIED,
    )
    players = Players()
    players.append(admin)
    players.append(target)
    players_service = _FakePlayersService(players)
    player_moderation = _RecordingModerationService()
    router.register(
        partial(
            restrict,
            players_service=players_service,
            player_moderation=player_moderation,
        ),
        trigger="restrict",
        privileges=Privileges.ADMINISTRATOR,
        hidden=True,
        description=restrict.__doc__,
    )

    response = await router.process(
        admin,
        admin,
        f"{app.settings.COMMAND_PREFIX}restrict target cc",
    )

    assert response is not None
    assert response["resp"] is not None
    assert response["resp"].startswith("<target (4)> was restricted. | Elapsed:")
    assert response["hidden"] is True
    assert target.restriction == (admin, "using a modified osu! client")
    assert target.logged_out is True


async def test_multiplayer_abort_requires_a_referee_and_resets_match_state() -> None:
    router = _router()
    host = _player(
        id=3,
        name="host",
        priv=Privileges.UNRESTRICTED | Privileges.VERIFIED,
    )
    guest = _player(
        id=4,
        name="guest",
        priv=Privileges.UNRESTRICTED | Privileges.VERIFIED,
    )
    players = Players()
    players.append(host)
    players.append(guest)
    multiplayer = router.create_group("mp", "Multiplayer commands.")
    multiplayer.register(
        mp_abort,
        trigger="abort",
        privileges=Privileges.UNRESTRICTED,
        aliases=("a",),
        description=mp_abort.__doc__,
    )
    match = _match(host=host, guest=guest)
    match.in_progress = True
    for slot in match.slots[:2]:
        slot.loaded = True
        slot.skipped = True

    denied_response = await router.process(
        guest,
        match.chat,
        f"{app.settings.COMMAND_PREFIX}mp abort",
    )

    assert denied_response == {"resp": None, "hidden": False}
    assert match.in_progress is True

    accepted_response = await router.process(
        host,
        match.chat,
        f"{app.settings.COMMAND_PREFIX}mp abort",
    )

    assert accepted_response is not None
    assert accepted_response["resp"] is not None
    assert accepted_response["resp"].startswith("Match aborted. | Elapsed:")
    assert match.in_progress is False
    assert [slot.status for slot in match.slots[:2]] == [
        SlotStatus.not_ready,
        SlotStatus.not_ready,
    ]
    assert all(not slot.loaded and not slot.skipped for slot in match.slots)
    expected_packets = app.packets.match_abort() + app.packets.update_match(
        match,
        send_pw=True,
    )
    assert host.dequeue() == expected_packets
    assert guest.dequeue() == expected_packets
