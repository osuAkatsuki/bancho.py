from __future__ import annotations

import random
from typing import Literal

from fastapi.param_functions import Depends
from fastapi.param_functions import Query
from fastapi.responses import Response
from fastapi.routing import APIRouter

import app.packets
import app.state
from app.api.web.authentication import authenticate_player_session
from app.constants.clientflags import LastFMFlags
from app.objects.player import Player

router = APIRouter()


@router.get("/lastfm.php")
async def lastFM(
    action: Literal["scrobble", "np"],
    beatmap_id_or_hidden_flag: str = Query(
        ...,
        description=(
            "This flag is normally a beatmap ID, but is also "
            "used as a hidden anticheat flag within osu!"
        ),
        alias="b",
    ),
    player: Player = Depends(authenticate_player_session(Query, "us", "ha")),
) -> Response:
    if beatmap_id_or_hidden_flag[0] != "a":
        # not anticheat related, tell the
        # client not to send any more for now.
        return Response(b"-3")

    flags = LastFMFlags(int(beatmap_id_or_hidden_flag[1:]))

    if flags & (LastFMFlags.HQ_ASSEMBLY | LastFMFlags.HQ_FILE):
        # Player is currently running hq!osu; could possibly
        # be a separate client, buuuut prooobably not lol.

        await player.restrict(
            admin=app.state.sessions.bot,
            reason=f"hq!osu running ({flags})",
        )

        # refresh their client state
        if player.is_online:
            player.logout()

        return Response(b"-3")

    if flags & LastFMFlags.REGISTRY_EDITS:
        # Player has registry edits left from
        # hq!osu's multiaccounting tool. This
        # does not necessarily mean they are
        # using it now, but they have in the past.

        if random.randrange(32) == 0:
            # Random chance (1/32) for a ban.
            await player.restrict(
                admin=app.state.sessions.bot,
                reason="hq!osu relife 1/32",
            )

            # refresh their client state
            if player.is_online:
                player.logout()

            return Response(b"-3")

        player.enqueue(
            app.packets.notification(
                "\n".join(
                    [
                        "Hey!",
                        "It appears you have hq!osu's multiaccounting tool (relife) enabled.",
                        "This tool leaves a change in your registry that the osu! client can detect.",
                        "Please re-install relife and disable the program to avoid any restrictions.",
                    ],
                ),
            ),
        )

        player.logout()

        return Response(b"-3")

    """ These checks only worked for ~5 hours from release. rumoi's quick!
    if flags & (
        LastFMFlags.SDL2_LIBRARY
        | LastFMFlags.OPENSSL_LIBRARY
        | LastFMFlags.AQN_MENU_SAMPLE
    ):
        # AQN has been detected in the client, either
        # through the 'libeay32.dll' library being found
        # onboard, or from the menu sound being played in
        # the AQN menu while being in an inappropriate menu
        # for the context of the sound effect.
        pass
    """

    return Response(b"")
