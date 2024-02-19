from __future__ import annotations

from app.logging import Ansi
from app.logging import log
from app.repositories import osu_sessions as osu_sessions_repo
from app.repositories.osu_sessions import OsuSession


async def logout(osu_session: OsuSession) -> None:
    # leave multiplayer
    # stop spectating other users
    # remove players who are spectating us
    # revoke all of our channel memberships
    # remove our session from redis
    # if we aren't restricted:
    # - inform online users of our logout
    # - decrement the online user count (datadog)
    log(f"User {osu_session['user_id']} logged out.", Ansi.LBLUE)
