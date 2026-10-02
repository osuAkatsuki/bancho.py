from __future__ import annotations

import struct
from collections.abc import Callable

import pytest

from app.bancho.router import BanchoPacketRouter
from app.constants.privileges import Privileges
from app.objects.player import Player
from app.packets import BanchoPacketReader
from app.packets import BasePacket
from app.packets import ClientPackets


class _RecordingPacket(BasePacket):
    def __init__(
        self,
        reader: BanchoPacketReader,
        *,
        calls: list[tuple[Player, int]],
    ) -> None:
        self.value = reader.read_i32()
        self.calls = calls

    async def handle(self, player: Player) -> None:
        self.calls.append((player, self.value))


def _packet(packet_id: ClientPackets, payload: bytes = b"") -> bytes:
    return struct.pack("<HxI", packet_id, len(payload)) + payload


def _recording_factory(
    calls: list[tuple[Player, int]],
) -> Callable[[BanchoPacketReader], BasePacket]:
    def factory(reader: BanchoPacketReader) -> BasePacket:
        return _RecordingPacket(reader, calls=calls)

    return factory


def _player(*, restricted: bool) -> Player:
    return Player(
        id=3,
        name="test player",
        priv=(Privileges.VERIFIED if restricted else Privileges.UNRESTRICTED),
        pw_bcrypt=None,
        token=Player.generate_token(),
    )


def test_register_exposes_normal_and_restricted_packet_ids() -> None:
    router = BanchoPacketRouter()
    factory = _recording_factory([])

    router.register(ClientPackets.CHANGE_ACTION, factory)
    router.register(ClientPackets.PING, factory, allow_restricted=True)

    assert router.registered_packet_ids == (
        ClientPackets.CHANGE_ACTION,
        ClientPackets.PING,
    )
    assert router.restricted_packet_ids == (ClientPackets.PING,)


def test_register_rejects_duplicate_packet_ids() -> None:
    router = BanchoPacketRouter()
    factory = _recording_factory([])
    router.register(ClientPackets.PING, factory)

    with pytest.raises(ValueError, match="PING is already registered"):
        router.register(ClientPackets.PING, factory, allow_restricted=True)


def test_registrations_are_isolated_between_router_instances() -> None:
    first_router = BanchoPacketRouter()
    second_router = BanchoPacketRouter()

    first_router.register(ClientPackets.PING, _recording_factory([]))

    assert first_router.registered_packet_ids == (ClientPackets.PING,)
    assert second_router.registered_packet_ids == ()


@pytest.mark.parametrize("body_type", (bytes, memoryview))
async def test_dispatch_uses_registered_factories_and_skips_unregistered_packets(
    body_type: Callable[[bytes], bytes | memoryview],
) -> None:
    calls: list[tuple[Player, int]] = []
    router = BanchoPacketRouter()
    router.register(ClientPackets.PING, _recording_factory(calls))
    player = _player(restricted=False)
    body = _packet(ClientPackets.ERROR_REPORT, b"skip") + _packet(
        ClientPackets.PING,
        struct.pack("<i", 42),
    )

    await router.dispatch(body_type(body), player)

    assert calls == [(player, 42)]


async def test_dispatch_limits_restricted_players_to_allowed_packets() -> None:
    calls: list[tuple[Player, int]] = []
    router = BanchoPacketRouter()
    factory = _recording_factory(calls)
    router.register(ClientPackets.CHANGE_ACTION, factory)
    router.register(ClientPackets.PING, factory, allow_restricted=True)
    player = _player(restricted=True)
    body = _packet(ClientPackets.CHANGE_ACTION, struct.pack("<i", 1)) + _packet(
        ClientPackets.PING,
        struct.pack("<i", 2),
    )

    await router.dispatch(body, player)

    assert calls == [(player, 2)]
