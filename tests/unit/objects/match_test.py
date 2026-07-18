from __future__ import annotations

import app.packets
from app.constants.gamemodes import GameMode
from app.constants.mods import Mods
from app.constants.privileges import Privileges
from app.objects.channel import Channel
from app.objects.collections import Channels
from app.objects.collections import Matches
from app.objects.collections import Players
from app.objects.match import Match
from app.objects.match import MatchTeams
from app.objects.match import MatchTeamTypes
from app.objects.match import MatchWinConditions
from app.objects.match import SlotStatus
from app.objects.player import Player
from app.services.player_sessions import PlayerSessionService


def _player(*, id: int, name: str) -> Player:
    return Player(
        id=id,
        name=name,
        priv=Privileges.UNRESTRICTED | Privileges.VERIFIED,
        pw_bcrypt=None,
        token=Player.generate_token(),
    )


def _match(
    *,
    host_id: int,
    chat: Channel,
    lobby: Channel | None = None,
) -> Match:
    return Match(
        id=0,
        name="test match",
        password="secret",
        has_public_history=True,
        map_name="Artist - Title [Difficulty]",
        map_id=123,
        map_md5="0123456789abcdef0123456789abcdef",
        host_id=host_id,
        mode=GameMode.VANILLA_OSU,
        mods=Mods.NOMOD,
        win_condition=MatchWinConditions.score,
        team_type=MatchTeamTypes.team_vs,
        freemods=False,
        seed=0,
        chat_channel=chat,
        lobby_channel=lobby,
    )


def _sessions(bot: Player) -> PlayerSessionService:
    players = Players()
    players.append(bot)
    return PlayerSessionService(
        players=players,
        channels=Channels(),
        matches=Matches(),
        bot=bot,
        decrement_online_players=lambda: None,
        debug=False,
    )


def test_join_match_rejects_an_incorrect_password() -> None:
    host = _player(id=3, name="host")
    guest = _player(id=4, name="guest")
    sessions = _sessions(host)
    sessions.players.append(guest)
    match = _match(
        host_id=host.id,
        chat=Channel("#multi_0", "test match", instance=True),
    )

    joined = sessions.join_match(guest, match, "incorrect")

    assert joined is False
    assert guest.match is None
    assert match.get_slot(guest) is None
    assert guest.dequeue() == app.packets.match_join_fail()


def test_match_join_host_departure_and_empty_match_cleanup() -> None:
    host = _player(id=3, name="host")
    guest = _player(id=4, name="guest")
    sessions = _sessions(host)
    sessions.players.append(guest)
    chat = Channel("#multi_0", "test match", auto_join=False, instance=True)
    sessions.channels.append(chat)
    match = _match(host_id=host.id, chat=chat)
    sessions.matches[match.id] = match

    assert sessions.join_match(host, match, "secret") is True
    assert sessions.join_match(guest, match, "secret") is True
    host.dequeue()
    guest.dequeue()

    host_slot = match.get_slot(host)
    guest_slot = match.get_slot(guest)
    assert host_slot is not None
    assert host_slot.status is SlotStatus.not_ready
    assert guest_slot is not None
    assert guest_slot.status is SlotStatus.not_ready
    assert guest_slot.team is MatchTeams.red

    sessions.leave_match(host)

    assert host.match is None
    assert match.slots[0].status is SlotStatus.open
    assert match.host is guest
    assert guest.dequeue() is not None
    assert match in sessions.matches

    sessions.leave_match(guest)

    assert guest.match is None
    assert match.slots[1].status is SlotStatus.open
    assert match not in sessions.matches
    assert chat not in sessions.channels


def test_start_match_only_sends_start_packet_to_players_with_the_map() -> None:
    ready_player = _player(id=3, name="ready")
    no_map_player = _player(id=4, name="no map")
    chat = Channel("#multi_0", "test match", instance=True)
    match = _match(host_id=ready_player.id, chat=chat)
    chat.append(ready_player)
    chat.append(no_map_player)
    match.slots[0].player = ready_player
    match.slots[0].status = SlotStatus.ready
    match.slots[1].player = no_map_player
    match.slots[1].status = SlotStatus.no_map

    match.start()

    match_start = app.packets.match_start(match)
    match_state = app.packets.update_match(match, send_pw=True)
    assert match.in_progress is True
    assert match.slots[0].status is SlotStatus.playing
    assert match.slots[1].status is SlotStatus.no_map
    assert ready_player.dequeue() == match_start + match_state
    assert no_map_player.dequeue() == match_state
