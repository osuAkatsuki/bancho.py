from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from typing import Sequence
from typing import Union

import app.packets
import app.repositories.beatmaps
import app.state.sessions
from app.constants import regexes
from app.objects.match import Match
from app.objects.match import MatchTeams
from app.objects.match import MatchTeamTypes
from app.objects.match import MatchWinConditions
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

    beatmap = await app.repositories.beatmaps.fetch_by_md5(match.map_md5)

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


async def update_matchpoints(match: Match, was_playing: Sequence[Slot]) -> None:
    """\
    Determine the winner from `scores`, increment & inform players.

    This automatically works with the match settings (such as
    win condition, teams, & co-op) to determine the appropriate
    winner, and will use any team names included in the match name,
    along with the match name (fmt: OWC2020: (Team1) vs. (Team2)).

    For the examples, we'll use accuracy as a win condition.

    Teams, match title: `OWC2015: (United States) vs. (China)`.
        United States takes the point! (293.32% vs 292.12%)
        Total Score: United States | 7 - 2 | China
        United States takes the match, finishing OWC2015 with a score of 7 - 2!

    FFA, the top <=3 players will be listed for the total score.
        Justice takes the point! (94.32% [Match avg. 91.22%])
        Total Score: Justice - 3 | cmyui - 2 | FrostiDrinks - 2
        Justice takes the match, finishing with a score of 4 - 2!
    """

    assert match.chat is not None
    scores, didnt_submit = await await_submissions(match, was_playing)

    for p in didnt_submit:
        match.chat.send_bot(f"{p} didn't submit a score (timeout: 10s).")

    if scores:
        ffa = match.team_type in (
            MatchTeamTypes.head_to_head,
            MatchTeamTypes.tag_coop,
        )

        # all scores are equal, it was a tie.
        if len(scores) != 1 and len(set(scores.values())) == 1:
            match.winners.append(None)
            match.chat.send_bot("The point has ended in a tie!")
            return None

        # Find the winner & increment their matchpoints.
        winner: Union[Player, MatchTeams] = max(scores, key=lambda k: scores[k])
        match.winners.append(winner)
        match.match_points[winner] += 1

        msg: list[str] = []

        def add_suffix(score: Union[int, float]) -> Union[str, int, float]:
            if match.use_pp_scoring:
                return f"{score:.2f}pp"
            elif match.win_condition == MatchWinConditions.accuracy:
                return f"{score:.2f}%"
            elif match.win_condition == MatchWinConditions.combo:
                return f"{score}x"
            else:
                return str(score)

        if ffa:
            msg.append(
                f"{winner.name} takes the point! ({add_suffix(scores[winner])} "
                f"[Match avg. {add_suffix(int(sum(scores.values()) / len(scores)))}])",
            )

            wmp = match.match_points[winner]

            # check if match point #1 has enough points to win.
            if match.winning_pts and wmp == match.winning_pts:
                # we have a champion, announce & reset our match.
                match.is_scrimming = False
                reset_scrimmage_state(match)
                match.bans.clear()

                m = f"{winner.name} takes the match! Congratulations!"
            else:
                # no winner, just announce the match points so far.
                # for ffa, we'll only announce the top <=3 players.
                m_points = sorted(match.match_points.items(), key=lambda x: x[1])
                m = f"Total Score: {' | '.join([f'{k.name} - {v}' for k, v in m_points])}"

            msg.append(m)
            del m

        else:  # teams
            if r_match := regexes.TOURNEY_MATCHNAME.match(match.name):
                match_name = r_match["name"]
                team_names = {
                    MatchTeams.blue: r_match["T1"],
                    MatchTeams.red: r_match["T2"],
                }
            else:
                match_name = match.name
                team_names = {MatchTeams.blue: "Blue", MatchTeams.red: "Red"}

            # teams are binary, so we have a loser.
            loser = MatchTeams({1: 2, 2: 1}[winner])

            # from match name if available, else blue/red.
            wname = team_names[winner]
            lname = team_names[loser]

            # scores from the recent play
            # (according to win condition)
            ws = add_suffix(scores[winner])
            ls = add_suffix(scores[loser])

            # total win/loss score in the match.
            wmp = match.match_points[winner]
            lmp = match.match_points[loser]

            # announce the score for the most recent play.
            msg.append(f"{wname} takes the point! ({ws} vs. {ls})")

            # check if the winner has enough match points to win the match.
            if match.winning_pts and wmp == match.winning_pts:
                # we have a champion, announce & reset our match.
                match.is_scrimming = False
                reset_scrimmage_state(match)

                msg.append(
                    f"{wname} takes the match, finishing {match_name} "
                    f"with a score of {wmp} - {lmp}! Congratulations!",
                )
            else:
                # no winner, just announce the match points so far.
                msg.append(f"Total Score: {wname} | {wmp} - {lmp} | {lname}")

        if didnt_submit:
            match.chat.send_bot(
                "If you'd like to perform a rematch, "
                "please use the `!mp rematch` command.",
            )

        for line in msg:
            match.chat.send_bot(line)

    else:
        match.chat.send_bot("Scores could not be calculated.")


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
