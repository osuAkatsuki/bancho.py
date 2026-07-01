from __future__ import annotations

import app.services.client_integrity as client_integrity
from app.constants.clientflags import LastFMFlags


class _FakePlayer:
    def __init__(self) -> None:
        self.is_online = True
        self.restrictions: list[tuple[object, str]] = []
        self.notifications: list[str] = []
        self.logout_count = 0

    async def restrict(self, *, admin: object, reason: str) -> None:
        self.restrictions.append((admin, reason))

    def logout(self) -> None:
        self.logout_count += 1


def _service(*, restriction_roll: int = 1) -> client_integrity.ClientIntegrityService:
    return client_integrity.ClientIntegrityService(
        restriction_admin=object(),
        restriction_roll=lambda limit: restriction_roll,
        send_notification=lambda player, message: player.notifications.append(message),
    )


async def test_client_integrity_stops_lastfm_when_no_anticheat_flag_is_sent() -> None:
    player = _FakePlayer()

    result = await _service().handle_lastfm_flags(
        player=player,
        beatmap_id_or_hidden_flag="1234",
    )

    assert result is client_integrity.ClientIntegrityResult.STOP_SENDING
    assert player.restrictions == []
    assert player.notifications == []
    assert player.logout_count == 0


async def test_client_integrity_restricts_hq_osu_flags_and_logs_out_player() -> None:
    player = _FakePlayer()
    service = _service()

    result = await service.handle_lastfm_flags(
        player=player,
        beatmap_id_or_hidden_flag=f"a{int(LastFMFlags.HQ_FILE)}",
    )

    assert result is client_integrity.ClientIntegrityResult.STOP_SENDING
    assert player.restrictions == [
        (service.restriction_admin, f"hq!osu running ({LastFMFlags.HQ_FILE})"),
    ]
    assert player.logout_count == 1


async def test_client_integrity_warns_registry_edit_when_roll_misses() -> None:
    player = _FakePlayer()

    result = await _service(restriction_roll=1).handle_lastfm_flags(
        player=player,
        beatmap_id_or_hidden_flag=f"a{int(LastFMFlags.REGISTRY_EDITS)}",
    )

    assert result is client_integrity.ClientIntegrityResult.STOP_SENDING
    assert player.restrictions == []
    assert len(player.notifications) == 1
    assert "relife" in player.notifications[0]
    assert player.logout_count == 1
