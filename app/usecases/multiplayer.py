from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from typing import Sequence
from typing import Union

import app.packets
import app.state.sessions
from app import repositories
from app.objects.match import Match
from app.objects.match import MatchTeams
from app.objects.match import MatchTeamTypes
from app.objects.match import Slot
from app.objects.match import SlotStatus
from app.objects.player import Player

# TODO: these are really bad


async def await_submissions(
    match: Match,
    was_playing: Sequence[Slot],
) -> tuple[dict[Union[MatchTeams, Player], int], Sequence[Player]]:
    """Await score submissions from all players in completed state."""
    scores: dict[Union[MatchTeams, Player], int] = defaultdict(int)
    didnt_submit: list[Player] = []
    time_waited = 0  # allow up to 10s (total, not per player)

    ffa = match.team_type in (MatchTeamTypes.head_to_head, MatchTeamTypes.tag_coop)

    if match.use_pp_scoring:
        win_cond = "pp"
    else:
        win_cond = ("score", "acc", "max_combo", "score")[match.win_condition]

    beatmap = await repositories.beatmaps.fetch_by_md5(match.map_md5)

    if not beatmap:
        # map isn't submitted
        return {}, ()

    for s in was_playing:
        # continue trying to fetch each player's
        # scores until they've all been submitted.
        while True:
            rc_score = s.player.recent_score
            max_age = datetime.now() - timedelta(
                seconds=beatmap.total_length + time_waited + 0.5,
            )

            if rc_score and rc_score.server_time > max_age:
                # score found, add to our scores dict if != 0.
                if score := getattr(rc_score, win_cond):
                    key = s.player if ffa else s.team
                    scores[key] += score

                break

            # wait 0.5s and try again
            await asyncio.sleep(0.5)
            time_waited += 0.5

            if time_waited > 10:
                # inform the match this user didn't
                # submit a score in time, and skip them.
                didnt_submit.append(s.player)
                break

    # all scores retrieved, update the match.
    return scores, didnt_submit


def send_data_to_clients(
    match: Match,
    data: bytes,
    lobby: bool = True,
    immune: Sequence[int] = [],
) -> None:
    """Add data to be sent to all clients in the match."""
    match.chat.enqueue(data, immune)

    if lobby and (lchan := app.state.sessions.channels["#lobby"]) and lchan.players:
        lchan.enqueue(data)


def send_match_state_to_clients(match: Match, lobby: bool = True) -> None:
    """Enqueue `self`'s state to players in the match & lobby."""
    # TODO: hmm this is pretty bad, writes twice

    # send password only to users currently in the match.
    match.chat.enqueue(app.packets.update_match(match, send_pw=True))

    if lobby and (lchan := app.state.sessions.channels["#lobby"]) and lchan.players:
        lchan.enqueue(app.packets.update_match(match, send_pw=False))


def unready_players(match: Match, expected: SlotStatus = SlotStatus.ready) -> None:
    """Unready any players in the `expected` state."""
    for s in match.slots:
        if s.status == expected:
            s.status = SlotStatus.not_ready


def start(match: Match) -> None:
    """Start the match for all ready players with the map."""
    no_map: list[int] = []

    for s in match.slots:
        # start each player who has the map.
        if s.status & SlotStatus.has_player:
            if s.status != SlotStatus.no_map:
                s.status = SlotStatus.playing
            else:
                no_map.append(s.player.id)

    match.in_progress = True
    send_data_to_clients(
        match,
        app.packets.match_start(match),
        immune=no_map,
        lobby=False,
    )
    send_match_state_to_clients(match)


def reset_scrimmage_state(match: Match) -> None:
    """Reset the current scrim's winning points & bans."""
    match.match_points.clear()
    match.winners.clear()
    match.bans.clear()
