from __future__ import annotations

from typing import TYPE_CHECKING

from app.packets import BanchoPacketReader
from app.packets import ClientPackets
from app.packets import PacketFactory

if TYPE_CHECKING:
    from app.objects.player import Player


class BanchoPacketRouter:
    def __init__(self) -> None:
        self._packet_factories: dict[ClientPackets, PacketFactory] = {}
        self._restricted_packet_factories: dict[ClientPackets, PacketFactory] = {}

    @property
    def registered_packet_ids(self) -> tuple[ClientPackets, ...]:
        return tuple(self._packet_factories)

    @property
    def restricted_packet_ids(self) -> tuple[ClientPackets, ...]:
        return tuple(self._restricted_packet_factories)

    def register(
        self,
        packet_id: ClientPackets,
        factory: PacketFactory,
        *,
        allow_restricted: bool = False,
    ) -> None:
        if packet_id in self._packet_factories:
            raise ValueError(f"Packet {packet_id.name} is already registered.")

        self._packet_factories[packet_id] = factory
        if allow_restricted:
            self._restricted_packet_factories[packet_id] = factory

    async def dispatch(
        self,
        body: bytes | memoryview,
        player: Player,
    ) -> None:
        packet_factories = (
            self._restricted_packet_factories
            if player.restricted
            else self._packet_factories
        )

        with memoryview(body) as body_view:
            for packet in BanchoPacketReader(body_view, packet_factories):
                await packet.handle(player)
