from __future__ import annotations

from collections.abc import Awaitable
from collections.abc import Callable

import pytest

from app.bg_loops import OSU_CLIENT_MIN_PING_INTERVAL
from app.bg_loops import SUPPORTER_EXPIRED_NOTIFICATION
from app.bg_loops import HousekeepingService
from app.bg_loops import run_periodically
from app.constants.privileges import Privileges
from app.objects.player import Player


def _player(
    *,
    id: int,
    online: bool = True,
    donor_end: int = 0,
    last_recv_time: float = 0,
) -> Player:
    player = Player(
        id=id,
        name=f"player-{id}",
        priv=Privileges.UNRESTRICTED | Privileges.DONATOR,
        pw_bcrypt=None,
        token=Player.generate_token() if online else "",
        donor_end=donor_end,
    )
    player.last_recv_time = last_recv_time
    return player


class _FakeUsersRepository:
    def __init__(self, expired_donor_ids: list[int]) -> None:
        self.expired_donor_ids = expired_donor_ids
        self.fetch_expired_donor_ids_calls = 0
        self.partial_updates: list[dict[str, int]] = []

    async def fetch_expired_donor_ids(self) -> list[int]:
        self.fetch_expired_donor_ids_calls += 1
        return self.expired_donor_ids

    async def partial_update(self, *, id: int, donor_end: int) -> None:
        self.partial_updates.append({"id": id, "donor_end": donor_end})


def _housekeeping_service(
    *,
    users: _FakeUsersRepository,
    online_players: list[Player],
    fetch_player: Callable[[int], Awaitable[Player | None]],
    remove_privileges: Callable[[Player, Privileges], Awaitable[None]],
    notify_player: Callable[[Player, str], None] = lambda player, message: None,
    logout_player: Callable[[Player], None] = lambda player: None,
    clear_bot_status_cache: Callable[[], None] = lambda: None,
    current_time: Callable[[], float] = lambda: 0,
) -> HousekeepingService:
    return HousekeepingService(
        users=users,
        online_players=online_players,
        fetch_player=fetch_player,
        remove_privileges=remove_privileges,
        notify_player=notify_player,
        logout_player=logout_player,
        clear_bot_status_cache=clear_bot_status_cache,
        current_time=current_time,
        debug=False,
    )


async def test_expire_donation_privileges_updates_players_and_persistence() -> None:
    online_donor = _player(id=3, online=True, donor_end=100)
    offline_donor = _player(id=4, online=False, donor_end=100)
    players = {online_donor.id: online_donor, offline_donor.id: offline_donor}
    users = _FakeUsersRepository(list(players))
    removed_privileges: list[tuple[int, Privileges]] = []
    notifications: list[tuple[int, str]] = []

    async def fetch_player(player_id: int) -> Player | None:
        return players.get(player_id)

    async def remove_privileges(player: Player, bits: Privileges) -> None:
        removed_privileges.append((player.id, bits))
        player.priv &= ~bits

    service = _housekeeping_service(
        users=users,
        online_players=[online_donor],
        fetch_player=fetch_player,
        remove_privileges=remove_privileges,
        notify_player=lambda player, message: notifications.append(
            (player.id, message),
        ),
    )

    await service.expire_donation_privileges_once()

    assert removed_privileges == [
        (online_donor.id, Privileges.DONATOR),
        (offline_donor.id, Privileges.DONATOR),
    ]
    assert online_donor.donor_end == 0
    assert offline_donor.donor_end == 0
    assert users.partial_updates == [
        {"id": online_donor.id, "donor_end": 0},
        {"id": offline_donor.id, "donor_end": 0},
    ]
    assert notifications == [
        (online_donor.id, SUPPORTER_EXPIRED_NOTIFICATION),
    ]
    assert users.fetch_expired_donor_ids_calls == 1


async def test_disconnect_ghosts_only_logs_out_players_beyond_timeout() -> None:
    current_time = 1_000.0
    stale = _player(
        id=3,
        last_recv_time=current_time - OSU_CLIENT_MIN_PING_INTERVAL - 1,
    )
    on_boundary = _player(
        id=4,
        last_recv_time=current_time - OSU_CLIENT_MIN_PING_INTERVAL,
    )
    active = _player(id=5, last_recv_time=current_time - 1)
    logged_out: list[Player] = []

    async def unused_fetch_player(player_id: int) -> Player | None:
        raise AssertionError("player lookup should not be used")

    async def unused_remove_privileges(
        player: Player,
        bits: Privileges,
    ) -> None:
        raise AssertionError("privilege removal should not be used")

    service = _housekeeping_service(
        users=_FakeUsersRepository([]),
        online_players=[stale, on_boundary, active],
        fetch_player=unused_fetch_player,
        remove_privileges=unused_remove_privileges,
        logout_player=logged_out.append,
        current_time=lambda: current_time,
    )

    await service.disconnect_ghosts_once()

    assert logged_out == [stale]


async def test_refresh_bot_status_clears_the_cached_packet() -> None:
    clear_calls = 0

    def clear_bot_status_cache() -> None:
        nonlocal clear_calls
        clear_calls += 1

    async def unused_fetch_player(player_id: int) -> Player | None:
        raise AssertionError("player lookup should not be used")

    async def unused_remove_privileges(
        player: Player,
        bits: Privileges,
    ) -> None:
        raise AssertionError("privilege removal should not be used")

    service = _housekeeping_service(
        users=_FakeUsersRepository([]),
        online_players=[],
        fetch_player=unused_fetch_player,
        remove_privileges=unused_remove_privileges,
        clear_bot_status_cache=clear_bot_status_cache,
    )

    await service.refresh_bot_status_once()

    assert clear_calls == 1


class _StopPeriodic(Exception):
    pass


@pytest.mark.parametrize(
    ("initial_delay", "expected_events"),
    [
        (0, [("action", 0)]),
        (5, [("sleep", 5), ("action", 0)]),
    ],
)
async def test_run_periodically_preserves_initial_delay(
    initial_delay: float,
    expected_events: list[tuple[str, float]],
) -> None:
    events: list[tuple[str, float]] = []

    async def action() -> None:
        events.append(("action", 0))
        raise _StopPeriodic

    async def sleep(delay: float) -> None:
        events.append(("sleep", delay))

    with pytest.raises(_StopPeriodic):
        await run_periodically(
            action,
            interval=10,
            initial_delay=initial_delay,
            sleep=sleep,
        )

    assert events == expected_events


async def test_run_periodically_waits_between_completed_actions() -> None:
    events: list[tuple[str, float]] = []
    action_calls = 0

    async def action() -> None:
        nonlocal action_calls
        action_calls += 1
        events.append(("action", 0))
        if action_calls == 2:
            raise _StopPeriodic

    async def sleep(delay: float) -> None:
        events.append(("sleep", delay))

    with pytest.raises(_StopPeriodic):
        await run_periodically(action, interval=10, sleep=sleep)

    assert events == [("action", 0), ("sleep", 10), ("action", 0)]
