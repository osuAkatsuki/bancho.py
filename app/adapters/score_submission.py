from __future__ import annotations

from pathlib import Path

import app.packets
import app.settings
import app.state
import app.utils
from app.objects.beatmap import Beatmap
from app.objects.player import Player

REPLAYS_PATH = Path.cwd() / ".data/osr"


async def fetch_score_submission_beatmap(md5: str) -> Beatmap | None:
    return await Beatmap.from_md5(md5)


async def authenticate_score_submitter(
    username: str,
    password_md5: str,
) -> Player | None:
    return await app.state.sessions.players.from_login(username, password_md5)


async def record_score_submission_integrity_failure() -> None:
    stacktrace = app.utils.get_appropriate_stacktrace()
    await app.state.services.log_strange_occurrence(stacktrace)


def increment_score_submission_metric(metric: str) -> None:
    if app.state.services.datadog:
        app.state.services.datadog.increment(metric)  # type: ignore[no-untyped-call]


def send_personal_best_notification(player: Player, message: str) -> None:
    player.enqueue(app.packets.notification(message))


def publish_score_submitter_stats(player: Player) -> None:
    app.state.sessions.players.enqueue(app.packets.user_stats(player))
