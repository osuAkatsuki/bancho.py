from __future__ import annotations

from datetime import date
from ipaddress import IPv4Address
from pathlib import Path
from typing import Any
from typing import cast
from unittest.mock import create_autospec

import pytest

import app.packets
from app.api.domains import cho
from app.bancho.router import BanchoPacketRouter
from app.command_router import CommandRouter
from app.constants.privileges import Privileges
from app.objects.beatmap import Beatmap
from app.objects.collections import Channels
from app.objects.collections import Matches
from app.objects.collections import Players
from app.objects.match import MAX_MATCH_NAME_LENGTH
from app.objects.player import WINE_ADAPTER_SENTINEL
from app.objects.player import ClientDetails
from app.objects.player import OsuStream
from app.objects.player import OsuVersion
from app.objects.player import Player
from app.packets import BanchoPacketReader
from app.packets import ClientPackets
from app.packets import MultiplayerMatch
from app.repositories.mail import MailRepository
from app.services.performance import PerformanceService
from app.services.player_data import PlayerDataService
from app.services.player_sessions import PlayerSessionService
from app.services.players import PlayersService
from app.services.problem_reporting import ProblemReportingService
from app.services.relationships import RelationshipsService


async def _fetch_no_beatmap_by_id(beatmap_id: int) -> Beatmap | None:
    _ = beatmap_id
    return None


async def _fetch_no_beatmap_by_md5(beatmap_md5: str) -> Beatmap | None:
    _ = beatmap_md5
    return None


async def _ensure_no_osu_file(
    beatmap_id: int,
    *,
    expected_md5: str,
) -> bool:
    _ = (beatmap_id, expected_md5)
    return False


async def _ignore_problem(_occurrence: object) -> None:
    return None


def _build_isolated_packet_router() -> BanchoPacketRouter:
    bot = Player(
        id=1,
        name="BanchoBot",
        priv=Privileges.UNRESTRICTED,
        pw_bcrypt=None,
        token=Player.generate_token(),
        is_bot_client=True,
    )
    players = Players()
    players.append(bot)
    channels = Channels()
    matches = Matches()
    player_session_service = PlayerSessionService(
        players=players,
        channels=channels,
        matches=matches,
        bot=bot,
        decrement_online_players=lambda: None,
        debug=False,
    )

    return cho.build_packet_router(
        players=players,
        channels=channels,
        matches=matches,
        bot=bot,
        command_router=CommandRouter(
            prefix="!",
            clock=lambda: 0,
            format_elapsed=str,
        ),
        player_data_service=create_autospec(PlayerDataService, instance=True),
        player_session_service=player_session_service,
        players_service=create_autospec(PlayersService, instance=True),
        relationships_service=create_autospec(
            RelationshipsService,
            instance=True,
        ),
        mail_repository=create_autospec(MailRepository, instance=True),
        performance_service=PerformanceService(),
        problem_reporting_service=ProblemReportingService(
            report_occurrence=_ignore_problem,
        ),
        fetch_beatmap_by_id=_fetch_no_beatmap_by_id,
        fetch_beatmap_by_md5=_fetch_no_beatmap_by_md5,
        ensure_osu_file_available=_ensure_no_osu_file,
        beatmaps_path=Path(".data/osu"),
        pp_cached_accuracies=(95, 98, 99, 100),
        clock=lambda: 0.0,
        nanosecond_clock=lambda: 0,
        chat_logger=lambda _player, _recipient, _message: None,
        get_stacktrace=lambda: "stacktrace",
        schedule_background=lambda coroutine: coroutine.close(),
    )


def test_parse_login_data_handles_protocol_trailing_newline() -> None:
    login_data = (
        b"cmyui\n"
        b"password-md5\n"
        b"b20230814.2cuttingedge|-5|1|"
        b"osu-path.adapt:1.2.3.:adapters:uninstall:disk:|1\n"
    )

    parsed = cho.parse_login_data(login_data)

    assert parsed == {
        "username": "cmyui",
        "password_md5": b"password-md5",
        "osu_version": "b20230814.2cuttingedge",
        "utc_offset": -5,
        "display_city": True,
        "pm_private": True,
        "osu_path_md5": "osu-path.adapt",
        "adapters_str": "1.2.3.",
        "adapters_md5": "adapters",
        "uninstall_md5": "uninstall",
        "disk_signature_md5": "disk",
    }


@pytest.mark.parametrize(
    ("raw_version", "expected_date", "expected_revision", "expected_stream"),
    [
        ("b20230814", date(2023, 8, 14), None, OsuStream.STABLE),
        ("b20230814.2cuttingedge", date(2023, 8, 14), 2, OsuStream.CUTTINGEDGE),
        ("b20230814beta", date(2023, 8, 14), None, OsuStream.BETA),
    ],
)
def test_parse_osu_version_string(
    raw_version: str,
    expected_date: date,
    expected_revision: int | None,
    expected_stream: OsuStream,
) -> None:
    parsed = cho.parse_osu_version_string(raw_version)

    assert parsed is not None
    assert parsed.date == expected_date
    assert parsed.revision == expected_revision
    assert parsed.stream is expected_stream


def test_parse_osu_version_string_rejects_invalid_versions() -> None:
    assert cho.parse_osu_version_string("definitely-not-osu") is None


def test_parse_adapters_string() -> None:
    adapters, running_under_wine = cho.parse_adapters_string("1.2.3.")

    assert adapters == ["1", "2", "3"]
    assert running_under_wine is False


def test_parse_adapters_string_detects_wine() -> None:
    adapters, running_under_wine = cho.parse_adapters_string(WINE_ADAPTER_SENTINEL)

    assert adapters == [WINE_ADAPTER_SENTINEL]
    assert running_under_wine is True


def test_parse_adapters_string_rejects_non_wine_without_trailing_delimiter() -> None:
    with pytest.raises(ValueError):
        cho.parse_adapters_string("1.2.3")


def test_client_details_client_hash_preserves_wine_adapter_sentinel() -> None:
    client_details = ClientDetails(
        osu_version=OsuVersion(
            date=date(2026, 6, 22),
            revision=None,
            stream=OsuStream.STABLE,
        ),
        osu_path_md5="osu-path",
        adapters=[WINE_ADAPTER_SENTINEL],
        adapters_md5="adapters",
        uninstall_md5="uninstall",
        disk_signature_md5="disk",
        ip=IPv4Address("127.0.0.1"),
    )

    assert (
        client_details.client_hash
        == "osu-path:runningunderwine:adapters:uninstall:disk:"
    )


def test_validate_match_data_accepts_expected_host_and_reasonable_name() -> None:
    match_data = MultiplayerMatch()
    match_data.host_id = 32
    match_data.name = "friendly lobby"

    assert cho.validate_match_data(match_data, expected_host_id=32) is True


@pytest.mark.parametrize(
    ("host_id", "name", "expected_host_id"),
    [
        (99, "friendly lobby", 32),
        (32, "x" * (MAX_MATCH_NAME_LENGTH + 1), 32),
    ],
)
def test_validate_match_data_rejects_untrusted_fields(
    host_id: int,
    name: str,
    expected_host_id: int,
) -> None:
    match_data = MultiplayerMatch()
    match_data.host_id = host_id
    match_data.name = name

    assert cho.validate_match_data(match_data, expected_host_id) is False


def test_build_packet_router_preserves_the_production_packet_contract() -> None:
    packet_router = _build_isolated_packet_router()

    assert packet_router.registered_packet_ids == (
        ClientPackets.PING,
        ClientPackets.CHANGE_ACTION,
        ClientPackets.SEND_PUBLIC_MESSAGE,
        ClientPackets.LOGOUT,
        ClientPackets.REQUEST_STATUS_UPDATE,
        ClientPackets.START_SPECTATING,
        ClientPackets.STOP_SPECTATING,
        ClientPackets.SPECTATE_FRAMES,
        ClientPackets.CANT_SPECTATE,
        ClientPackets.SEND_PRIVATE_MESSAGE,
        ClientPackets.PART_LOBBY,
        ClientPackets.JOIN_LOBBY,
        ClientPackets.CREATE_MATCH,
        ClientPackets.JOIN_MATCH,
        ClientPackets.PART_MATCH,
        ClientPackets.MATCH_CHANGE_SLOT,
        ClientPackets.MATCH_READY,
        ClientPackets.MATCH_LOCK,
        ClientPackets.MATCH_CHANGE_SETTINGS,
        ClientPackets.MATCH_START,
        ClientPackets.MATCH_SCORE_UPDATE,
        ClientPackets.MATCH_COMPLETE,
        ClientPackets.MATCH_CHANGE_MODS,
        ClientPackets.MATCH_LOAD_COMPLETE,
        ClientPackets.MATCH_NO_BEATMAP,
        ClientPackets.MATCH_NOT_READY,
        ClientPackets.MATCH_FAILED,
        ClientPackets.MATCH_HAS_BEATMAP,
        ClientPackets.MATCH_SKIP_REQUEST,
        ClientPackets.CHANNEL_JOIN,
        ClientPackets.MATCH_TRANSFER_HOST,
        ClientPackets.TOURNAMENT_MATCH_INFO_REQUEST,
        ClientPackets.TOURNAMENT_JOIN_MATCH_CHANNEL,
        ClientPackets.TOURNAMENT_LEAVE_MATCH_CHANNEL,
        ClientPackets.FRIEND_ADD,
        ClientPackets.FRIEND_REMOVE,
        ClientPackets.MATCH_CHANGE_TEAM,
        ClientPackets.CHANNEL_PART,
        ClientPackets.RECEIVE_UPDATES,
        ClientPackets.SET_AWAY_MESSAGE,
        ClientPackets.USER_STATS_REQUEST,
        ClientPackets.MATCH_INVITE,
        ClientPackets.MATCH_CHANGE_PASSWORD,
        ClientPackets.USER_PRESENCE_REQUEST,
        ClientPackets.USER_PRESENCE_REQUEST_ALL,
        ClientPackets.TOGGLE_BLOCK_NON_FRIEND_DMS,
    )
    assert packet_router.restricted_packet_ids == (
        ClientPackets.PING,
        ClientPackets.CHANGE_ACTION,
        ClientPackets.LOGOUT,
        ClientPackets.REQUEST_STATUS_UPDATE,
        ClientPackets.CHANNEL_JOIN,
        ClientPackets.CHANNEL_PART,
        ClientPackets.RECEIVE_UPDATES,
        ClientPackets.USER_STATS_REQUEST,
    )


async def test_match_create_publishes_only_after_the_host_joins() -> None:
    bot = Player(
        id=1,
        name="BanchoBot",
        priv=Privileges.UNRESTRICTED,
        pw_bcrypt=None,
        token=Player.generate_token(),
        is_bot_client=True,
    )
    player = Player(
        id=3,
        name="host",
        priv=Privileges.UNRESTRICTED,
        pw_bcrypt=None,
        token=Player.generate_token(),
    )
    players = Players()
    players.append(bot)
    players.append(player)
    channels = Channels()
    matches = Matches()
    player_sessions = PlayerSessionService(
        players=players,
        channels=channels,
        matches=matches,
        bot=bot,
        decrement_online_players=lambda: None,
        debug=False,
    )
    player_data = create_autospec(PlayerDataService, instance=True)
    reader = create_autospec(BanchoPacketReader, instance=True)
    reader.read_match.return_value = MultiplayerMatch(
        name="test lobby",
        host_id=player.id,
    )
    packet = cho.MatchCreate(
        reader,
        matches=matches,
        channels=channels,
        bot=bot,
        player_data_service=player_data,
        player_session_service=player_sessions,
    )

    await packet.handle(player)

    match = matches[0]
    assert match is not None
    assert match.host is player
    assert player.match is match
    assert match.chat in channels
    player_data.schedule_latest_activity_update.assert_called_once_with(player)


async def test_match_create_does_not_publish_a_match_when_host_join_fails() -> None:
    bot = Player(
        id=1,
        name="BanchoBot",
        priv=Privileges.UNRESTRICTED,
        pw_bcrypt=None,
        token=Player.generate_token(),
        is_bot_client=True,
    )
    player = Player(
        id=3,
        name="host",
        priv=Privileges.UNRESTRICTED,
        pw_bcrypt=None,
        token=Player.generate_token(),
    )
    player.match = cast(Any, object())
    players = Players()
    players.append(bot)
    players.append(player)
    channels = Channels()
    matches = Matches()
    player_sessions = PlayerSessionService(
        players=players,
        channels=channels,
        matches=matches,
        bot=bot,
        decrement_online_players=lambda: None,
        debug=False,
    )
    player_data = create_autospec(PlayerDataService, instance=True)
    reader = create_autospec(BanchoPacketReader, instance=True)
    reader.read_match.return_value = MultiplayerMatch(
        name="test lobby",
        host_id=player.id,
    )
    packet = cho.MatchCreate(
        reader,
        matches=matches,
        channels=channels,
        bot=bot,
        player_data_service=player_data,
        player_session_service=player_sessions,
    )

    await packet.handle(player)

    assert all(match is None for match in matches)
    assert channels == []
    player_data.schedule_latest_activity_update.assert_not_called()
    assert player.dequeue() == app.packets.match_join_fail()


async def test_friend_add_does_not_mutate_blocks_before_persistence() -> None:
    bot = Player(
        id=1,
        name="BanchoBot",
        priv=Privileges.UNRESTRICTED,
        pw_bcrypt=None,
        token=Player.generate_token(),
        is_bot_client=True,
    )
    player = Player(
        id=3,
        name="player",
        priv=Privileges.UNRESTRICTED,
        pw_bcrypt=None,
        token=Player.generate_token(),
    )
    target = Player(
        id=4,
        name="target",
        priv=Privileges.UNRESTRICTED,
        pw_bcrypt=None,
        token=Player.generate_token(),
    )
    player.blocks.add(target.id)
    players = Players()
    for online_player in (bot, player, target):
        players.append(online_player)

    reader = create_autospec(BanchoPacketReader, instance=True)
    reader.read_i32.return_value = target.id
    player_data_service = create_autospec(PlayerDataService, instance=True)
    relationships_service = create_autospec(RelationshipsService, instance=True)
    relationships_service.add_friend.side_effect = RuntimeError(
        "relationship upsert failed",
    )
    packet = cho.FriendAdd(
        reader,
        players=players,
        bot=bot,
        player_data_service=player_data_service,
        relationships_service=relationships_service,
    )

    with pytest.raises(RuntimeError, match="relationship upsert failed"):
        await packet.handle(player)

    assert player.blocks == {target.id}
