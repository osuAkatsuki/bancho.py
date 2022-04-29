from __future__ import annotations

import hashlib
import time

import pymysql
import pytest

import app.settings
import app.state.sessions
from app import repositories
from app import usecases
from app.constants.privileges import Privileges

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("setup_app")]

# the variance to allow for time-related inaccuracies
TIME_LENIENCY_SECONDS = 5


async def test_registration() -> None:
    """Test player registration process."""
    real_player_info = {
        "player_name": "test_user",
        "email": "some-test_email@gmail.com",
        "pw_plaintext": "Abc123#@!real",
        "country": "us",
    }

    # success case
    player_id = await usecases.players.register(**real_player_info)

    # register a second time - this should throw an error
    with pytest.raises(pymysql.err.IntegrityError):
        player_id = await usecases.players.register(**real_player_info)

    # add md5 password to player info
    pw_md5 = hashlib.md5(real_player_info["pw_plaintext"].encode()).hexdigest().encode()

    player = await repositories.players.fetch(id=player_id)
    assert player is not None
    assert usecases.players.validate_credentials(
        password=pw_md5,
        hashed_password=player.pw_bcrypt,  # type: ignore
    )

    # TODO: should we do player deletion?
    # await usecases.players.delete(player_id)


async def test_update_name():
    player = await repositories.players.fetch(name="test_user")
    assert player is not None

    # test_user -> test_user2
    await usecases.players.update_name(player, "test_user2")
    assert player.name == "test_user2"

    # test_user2 -> test_user
    await usecases.players.update_name(player, "test_user")
    assert player.name == "test_user"


async def test_privileges():
    player = await repositories.players.fetch(name="test_user")
    assert player is not None

    await usecases.players.add_privileges(player, Privileges.MODERATOR)
    assert player.priv & Privileges.MODERATOR != 0

    await usecases.players.remove_privileges(player, Privileges.MODERATOR)
    assert player.priv & Privileges.MODERATOR == 0

    current_privileges = player.priv
    new_privileges = (
        Privileges.UNRESTRICTED
        | Privileges.VERIFIED
        | Privileges.TOURNEY_MANAGER
        | Privileges.DEVELOPER
    )
    await usecases.players.update_privileges(player, new_privileges)
    assert player.priv == new_privileges

    await usecases.players.update_privileges(player, current_privileges)
    assert player.priv == current_privileges


async def test_donor_time():
    player = await repositories.players.fetch(name="test_user")
    assert player is not None


async def test_restrictions():
    player = await repositories.players.fetch(name="test_user")
    assert player is not None

    # ensure we're unrestricted
    assert player.priv & Privileges.UNRESTRICTED != 0

    # restrict player
    await usecases.players.restrict(
        player,
        admin=app.state.sessions.bot,
        reason="did something bad",
    )
    assert player.priv & Privileges.UNRESTRICTED == 0

    # unrestrict player
    await usecases.players.unrestrict(
        player,
        admin=app.state.sessions.bot,
        reason="did something good",
    )
    assert player.priv & Privileges.UNRESTRICTED != 0

    # TODO: assert notes were set?


async def test_silences():
    player = await repositories.players.fetch(name="test_user")
    assert player is not None

    # ensure we're unsilenced
    assert player.silence_end == 0

    # silence player for 60s
    await usecases.players.silence(
        player,
        admin=app.state.sessions.bot,
        duration=60,
        reason="did something bad",
    )

    assert abs(player.silence_end - (time.time() + 60)) < TIME_LENIENCY_SECONDS

    # unsilence player
    await usecases.players.unsilence(
        player,
        admin=app.state.sessions.bot,
    )
    assert player.silence_end == 0

    # TODO: assert notes were set?
