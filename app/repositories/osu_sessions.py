from __future__ import annotations

import json
import textwrap
from typing import Any
from typing import TypedDict
from typing import cast

import app.state.services
from app._typing import UNSET
from app._typing import _UnsetSentinel
from app.constants.privileges import ClanPrivileges
from app.constants.privileges import Privileges
from app.objects.player import ClientDetails
from app.utils import make_safe_name

# we will use redis for this


class OsuSession(TypedDict):
    user_id: int
    name: str
    priv: Privileges
    pw_bcrypt: bytes | None
    token: str
    clan_id: int | None
    clan_priv: ClanPrivileges | None
    geoloc: app.state.services.Geolocation | None
    utc_offset: int
    pm_private: bool
    silence_end: int
    donor_end: int
    client_details: ClientDetails | None
    login_time: float
    is_bot_client: bool
    is_tourney_client: bool
    api_key: str | None


class OsuSessionUpdateFields(TypedDict, total=False): ...


def serialize(osu_session: OsuSession) -> str:
    """Serialize an osu! session to a string."""
    serializable = {
        "user_id": osu_session["user_id"],
        "name": osu_session["name"],
        "priv": osu_session["priv"].value,
        "pw_bcrypt": (
            osu_session["pw_bcrypt"].decode() if osu_session["pw_bcrypt"] else None
        ),
        "token": osu_session["token"],
        "clan_id": osu_session["clan_id"],
        "clan_priv": (
            osu_session["clan_priv"].value if osu_session["clan_priv"] else None
        ),
        "geoloc": osu_session["geoloc"],
        "utc_offset": osu_session["utc_offset"],
        "pm_private": osu_session["pm_private"],
        "silence_end": osu_session["silence_end"],
        "donor_end": osu_session["donor_end"],
        "client_details": osu_session["client_details"],
        "login_time": osu_session["login_time"],
        "is_bot_client": osu_session["is_bot_client"],
        "is_tourney_client": osu_session["is_tourney_client"],
        "api_key": osu_session["api_key"],
    }
    return json.dumps(serializable)


async def create(
    user_id: int,
    name: str,
    priv: Privileges,
    pw_bcrypt: bytes | None,
    token: str,
    clan_id: int | None = None,
    clan_priv: ClanPrivileges | None = None,
    geoloc: app.state.services.Geolocation | None = None,
    utc_offset: int = 0,
    pm_private: bool = False,
    silence_end: int = 0,
    donor_end: int = 0,
    client_details: ClientDetails | None = None,
    login_time: float = 0.0,
    is_bot_client: bool = False,
    is_tourney_client: bool = False,
    api_key: str | None = None,
) -> OsuSession:
    """Create a new osu! session in redis."""
    if geoloc is None:
        geoloc = {
            "latitude": 0.0,
            "longitude": 0.0,
            "country": {
                "acronym": "XX",
                "numeric": 0,
            },
        }

    osu_session: OsuSession = {
        "user_id": user_id,
        "name": name,
        "priv": priv,
        "pw_bcrypt": pw_bcrypt,
        "token": token,
        "clan_id": clan_id,
        "clan_priv": clan_priv,
        "geoloc": geoloc,
        "utc_offset": utc_offset,
        "pm_private": pm_private,
        "silence_end": silence_end,
        "donor_end": donor_end,
        "client_details": client_details,
        "login_time": login_time,
        "is_bot_client": is_bot_client,
        "is_tourney_client": is_tourney_client,
        "api_key": api_key,
    }
    await app.state.services.redis.set(
        name=f"bancho:osu_sessions:{token}",
        value=serialize(osu_session),
    )
    return osu_session
