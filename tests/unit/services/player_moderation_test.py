from __future__ import annotations

from typing import Any
from typing import cast

import app.packets
from app.constants.gamemodes import GameMode
from app.constants.privileges import ClientPrivileges
from app.constants.privileges import Privileges
from app.objects.player import ModeData
from app.objects.player import Player
from app.repositories.leaderboard_ranks import LeaderboardRanksRepository
from app.repositories.logs import LogsRepository
from app.repositories.users import UsersRepository
from app.services.player_data import PlayerDataService
from app.services.player_moderation import MODES_WITH_LEADERBOARDS
from app.services.player_moderation import PlayerModerationService
from app.services.player_sessions import PlayerSessionService


def _player(
    id: int,
    *,
    privileges: Privileges,
    online: bool = True,
) -> Player:
    return Player(
        id=id,
        name=f"player-{id}",
        priv=privileges,
        pw_bcrypt=None,
        token=Player.generate_token() if online else "",
        geoloc={
            "latitude": 0.0,
            "longitude": 0.0,
            "country": {"acronym": "ca", "numeric": 38},
        },
    )


def _mode_data(*, pp: int) -> ModeData:
    return ModeData(
        tscore=0,
        rscore=0,
        pp=pp,
        acc=0.0,
        plays=0,
        playtime=0,
        max_combo=0,
        total_hits=0,
        rank=0,
        grades={},
    )


class _FakeUsersRepository:
    def __init__(self) -> None:
        self.updates: list[dict[str, int]] = []

    async def partial_update(self, **updates: int) -> None:
        self.updates.append(updates)


class _FakeLogsRepository:
    def __init__(self) -> None:
        self.entries: list[dict[str, int | str]] = []

    async def create(self, **entry: int | str) -> None:
        self.entries.append(entry)


class _FakeLeaderboardRanksRepository:
    def __init__(self) -> None:
        self.removed_global: list[tuple[int, int]] = []
        self.removed_country: list[tuple[int, int, str]] = []
        self.added_global: list[tuple[int, int, int]] = []
        self.added_country: list[tuple[int, int, str, int]] = []

    async def remove_from_global_leaderboard(
        self,
        player_id: int,
        mode: int,
    ) -> None:
        self.removed_global.append((player_id, mode))

    async def remove_from_country_leaderboard(
        self,
        player_id: int,
        mode: int,
        country: str,
    ) -> None:
        self.removed_country.append((player_id, mode, country))

    async def add_to_global_leaderboard(
        self,
        player_id: int,
        mode: int,
        pp: int,
    ) -> None:
        self.added_global.append((player_id, mode, pp))

    async def add_to_country_leaderboard(
        self,
        player_id: int,
        mode: int,
        country: str,
        pp: int,
    ) -> None:
        self.added_country.append((player_id, mode, country, pp))


class _FakePlayerDataService:
    def __init__(self) -> None:
        self.hydrated: list[Player] = []

    async def hydrate_stats(self, player: Player) -> None:
        self.hydrated.append(player)
        player.stats[GameMode.VANILLA_OSU] = _mode_data(pp=321)


class _FakePlayerSessionService:
    def __init__(self) -> None:
        self.logged_out: list[Player] = []
        self.left_matches: list[Player] = []

    def logout(self, player: Player) -> None:
        self.logged_out.append(player)

    def leave_match(self, player: Player) -> None:
        self.left_matches.append(player)


class _Harness:
    def __init__(self) -> None:
        self.users = _FakeUsersRepository()
        self.logs = _FakeLogsRepository()
        self.ranks = _FakeLeaderboardRanksRepository()
        self.player_data = _FakePlayerDataService()
        self.player_sessions = _FakePlayerSessionService()
        self.broadcasts: list[bytes] = []
        self.audit_logs: list[str] = []
        self.service = PlayerModerationService(
            users=cast(UsersRepository, self.users),
            logs=cast(LogsRepository, self.logs),
            leaderboard_ranks=cast(LeaderboardRanksRepository, self.ranks),
            player_data=cast(PlayerDataService, self.player_data),
            player_sessions=cast(PlayerSessionService, self.player_sessions),
            broadcast_packet=self.broadcasts.append,
            send_audit_log=self.audit_logs.append,
            current_time=lambda: 100.9,
        )


async def test_add_privileges_persists_and_refreshes_online_client_privileges() -> None:
    harness = _Harness()
    player = _player(3, privileges=Privileges.UNRESTRICTED)
    assert player.bancho_priv is ClientPrivileges.PLAYER

    await harness.service.add_privileges(player, Privileges.SUPPORTER)

    assert player.priv == Privileges.UNRESTRICTED | Privileges.SUPPORTER
    assert harness.users.updates == [{"id": 3, "priv": int(player.priv)}]
    assert player.dequeue() == app.packets.bancho_privileges(
        ClientPrivileges.PLAYER | ClientPrivileges.SUPPORTER,
    )


async def test_restrict_removes_all_public_ranks_logs_and_logs_out() -> None:
    harness = _Harness()
    admin = _player(2, privileges=Privileges.DEVELOPER)
    player = _player(
        3,
        privileges=Privileges.UNRESTRICTED | Privileges.VERIFIED,
    )

    await harness.service.restrict(player, admin=admin, reason="testing")

    assert player.restricted
    assert harness.users.updates == [{"id": 3, "priv": int(Privileges.VERIFIED)}]
    assert harness.logs.entries == [
        {"_from": 2, "to": 3, "action": "restrict", "msg": "testing"},
    ]
    assert harness.ranks.removed_global == [
        (3, mode) for mode in MODES_WITH_LEADERBOARDS
    ]
    assert harness.ranks.removed_country == [
        (3, mode, "ca") for mode in MODES_WITH_LEADERBOARDS
    ]
    assert harness.player_sessions.logged_out == [player]
    assert harness.audit_logs == [
        "<player-2 (2)> restricted <player-3 (3)> for: testing.",
    ]


async def test_unrestrict_hydrates_offline_stats_before_restoring_ranks() -> None:
    harness = _Harness()
    admin = _player(2, privileges=Privileges.DEVELOPER)
    player = _player(3, privileges=Privileges.VERIFIED, online=False)

    await harness.service.unrestrict(player, admin=admin, reason="appeal")

    assert not player.restricted
    assert harness.player_data.hydrated == [player]
    assert harness.ranks.added_global == [(3, GameMode.VANILLA_OSU.value, 321)]
    assert harness.ranks.added_country == [
        (3, GameMode.VANILLA_OSU.value, "ca", 321),
    ]
    assert harness.player_sessions.logged_out == []
    assert harness.logs.entries == [
        {"_from": 2, "to": 3, "action": "unrestrict", "msg": "appeal"},
    ]


async def test_silence_persists_broadcasts_and_removes_player_from_match() -> None:
    harness = _Harness()
    admin = _player(2, privileges=Privileges.MODERATOR)
    player = _player(3, privileges=Privileges.UNRESTRICTED)
    player.match = cast(Any, object())

    await harness.service.silence(
        player,
        admin=admin,
        duration=30.4,
        reason="spam",
    )

    assert player.silence_end == 131
    assert harness.users.updates == [{"id": 3, "silence_end": 131}]
    assert harness.logs.entries == [
        {"_from": 2, "to": 3, "action": "silence", "msg": "spam"},
    ]
    assert player.dequeue() == app.packets.silence_end(30)
    assert harness.broadcasts == [app.packets.user_silenced(3)]
    assert harness.player_sessions.left_matches == [player]


async def test_unsilence_persists_and_refreshes_the_client() -> None:
    harness = _Harness()
    admin = _player(2, privileges=Privileges.MODERATOR)
    player = _player(3, privileges=Privileges.UNRESTRICTED)
    player.silence_end = 500

    await harness.service.unsilence(player, admin=admin, reason="served")

    assert player.silence_end == 100
    assert harness.users.updates == [{"id": 3, "silence_end": 100}]
    assert harness.logs.entries == [
        {"_from": 2, "to": 3, "action": "unsilence", "msg": "served"},
    ]
    assert player.dequeue() == app.packets.silence_end(0)
