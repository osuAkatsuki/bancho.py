from __future__ import annotations

import hashlib
import struct
from collections.abc import Awaitable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

import app.packets
from app.constants.gamemodes import GameMode
from app.objects.score import Score
from app.repositories.scores import ReplayHeader
from app.services.visibility import PlayerIdentity
from app.services.visibility import can_view_player

DATETIME_OFFSET = 0x89F7FF5F7B58000


class ScoreFetcher(Protocol):
    def __call__(self, score_id: int) -> Awaitable[Score | None]: ...


class ReplayHeaderFetcher(Protocol):
    def __call__(self, score_id: int) -> Awaitable[ReplayHeader | None]: ...


class ReplayViewScheduler(Protocol):
    def __call__(self, score: Score) -> None: ...


class ReplayResultCode(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"


@dataclass(frozen=True)
class ReplayResult:
    code: ReplayResultCode
    path: Path | None = None


@dataclass(frozen=True)
class FullReplay:
    data: bytes
    filename: str


@dataclass(frozen=True)
class ReplayService:
    replays_path: Path
    fetch_score: ScoreFetcher
    fetch_replay_header: ReplayHeaderFetcher
    schedule_replay_view_increment: ReplayViewScheduler

    async def build_full_replay(
        self,
        score_id: int,
        *,
        viewer: PlayerIdentity | None,
    ) -> FullReplay | None:
        """Build a complete .osr file (headers + frames) for a score,
        as the osu! client exports them.

        Replays of hidden (restricted or unverified) players are only
        available to staff and to the players themselves."""
        replay_path = self.replays_path / f"{score_id}.osr"
        if not replay_path.exists():
            return None
        raw_replay_data = replay_path.read_bytes()

        row = await self.fetch_replay_header(score_id)
        if row is None:
            return None

        if not can_view_player(
            viewer=viewer,
            target_id=row.user_id,
            target_priv=row.user_priv,
        ):
            return None

        replay_md5 = hashlib.md5(
            "{}p{}o{}o{}t{}a{}r{}e{}y{}o{}u{}{}{}".format(
                row.n100 + row.n300,
                row.n50,
                row.ngeki,
                row.nkatu,
                row.nmiss,
                row.map_md5,
                row.max_combo,
                str(row.perfect == 1),
                row.username,
                row.score,
                0,  # TODO: rank
                row.mods,
                "True",  # TODO: ??
            ).encode(),
        ).hexdigest()

        replay_data = bytearray()
        replay_data += struct.pack(
            "<Bi",
            GameMode(row.mode).as_vanilla,
            20200207,
        )  # TODO: osuver
        replay_data += app.packets.write_string(row.map_md5)
        replay_data += app.packets.write_string(row.username)
        replay_data += app.packets.write_string(replay_md5)
        replay_data += struct.pack(
            "<hhhhhhihBi",
            row.n300,
            row.n100,
            row.n50,
            row.ngeki,
            row.nkatu,
            row.nmiss,
            row.score,
            row.max_combo,
            row.perfect,
            row.mods,
        )
        replay_data += b"\x00"  # TODO: hp graph
        timestamp = int(row.play_time.timestamp() * 1e7)
        replay_data += struct.pack("<q", timestamp + DATETIME_OFFSET)
        replay_data += struct.pack("<i", len(raw_replay_data))
        replay_data += raw_replay_data
        replay_data += struct.pack("<q", score_id)
        # NOTE: target practice sends extra mods, but
        # can't submit scores so should not be a problem.

        filename = (
            f"{row.username} - {row.artist} - {row.title} "
            f"[{row.version}] ({row.play_time:%Y-%m-%d}).osr"
        )
        return FullReplay(data=bytes(replay_data), filename=filename)

    async def fetch_raw_replay(
        self,
        score_id: int,
        *,
        viewer: PlayerIdentity | None,
    ) -> bytes | None:
        """Fetch a replay's raw frame data (no .osr headers), subject to
        the same visibility rules as full replays."""
        row = await self.fetch_replay_header(score_id)
        if row is None or not can_view_player(
            viewer=viewer,
            target_id=row.user_id,
            target_priv=row.user_priv,
        ):
            return None

        replay_path = self.replays_path / f"{score_id}.osr"
        if not replay_path.exists():
            return None
        return replay_path.read_bytes()

    async def fetch_replay_file(
        self,
        *,
        viewer: PlayerIdentity,
        score_id: int,
    ) -> ReplayResult:
        score = await self.fetch_score(score_id)
        if score is None:
            return ReplayResult(code=ReplayResultCode.NOT_FOUND)

        replay_path = self.replays_path / f"{score_id}.osr"
        if not replay_path.exists():
            return ReplayResult(code=ReplayResultCode.NOT_FOUND)

        player = score.player
        if player is not None and not can_view_player(
            viewer=viewer,
            target_id=player.id,
            target_priv=int(player.priv),
        ):
            return ReplayResult(code=ReplayResultCode.NOT_FOUND)

        if player is not None and viewer.id != player.id:
            self.schedule_replay_view_increment(score)

        return ReplayResult(code=ReplayResultCode.FOUND, path=replay_path)
