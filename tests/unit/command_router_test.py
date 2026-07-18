from __future__ import annotations

import pytest

from app.command_router import CommandRouter
from app.command_router import Context
from app.command_router import DuplicateCommandError
from app.constants.privileges import Privileges
from app.objects.player import Player


def _player(privileges: Privileges) -> Player:
    return Player(
        id=3,
        name="player",
        priv=privileges,
        pw_bcrypt=None,
        token=Player.generate_token(),
    )


def _router(*, times: list[int] | None = None) -> CommandRouter:
    clock_values = iter(times or [0, 0])
    return CommandRouter(
        prefix="!",
        clock=lambda: next(clock_values),
        format_elapsed=lambda elapsed: f"{elapsed}ns",
    )


async def test_regular_command_dispatch_parses_an_alias_and_arguments() -> None:
    router = _router(times=[100, 125])
    player = _player(Privileges.UNRESTRICTED)
    recipient = player
    received_context: Context | None = None

    @router.command(
        "echo",
        privileges=Privileges.UNRESTRICTED,
        aliases=("say",),
        hidden=True,
    )
    async def echo(context: Context) -> str:
        nonlocal received_context
        received_context = context
        return " ".join(context.args)

    response = await router.process(player, recipient, "!SaY  one   two")

    assert response == {"resp": "one two | Elapsed: 25ns", "hidden": True}
    assert received_context is not None
    assert received_context.player is player
    assert received_context.recipient is recipient
    assert received_context.trigger == "say"
    assert received_context.args == ("one", "two")


async def test_router_does_not_process_messages_without_its_prefix() -> None:
    router = _router()
    player = _player(Privileges.UNRESTRICTED)
    called = False

    @router.command("test", privileges=Privileges.UNRESTRICTED)
    async def command(context: Context) -> None:
        nonlocal called
        called = True

    response = await router.process(player, player, "test")

    assert response is None
    assert called is False


async def test_command_dispatch_requires_all_command_privileges() -> None:
    router = _router(times=[0])
    player = _player(Privileges.UNRESTRICTED | Privileges.VERIFIED)
    called = False

    @router.command("restrict", privileges=Privileges.ADMINISTRATOR)
    async def restrict(context: Context) -> None:
        nonlocal called
        called = True

    response = await router.process(player, player, "!restrict target reason")

    assert response is None
    assert called is False


async def test_command_group_without_a_subcommand_dispatches_help() -> None:
    router = _router(times=[10, 14])
    player = _player(Privileges.UNRESTRICTED)
    multiplayer = router.create_group("mp", "Multiplayer commands.")
    received_context: Context | None = None

    @multiplayer.command("help", privileges=Privileges.UNRESTRICTED, aliases=("h",))
    async def help_command(context: Context) -> str:
        nonlocal received_context
        received_context = context
        return "help"

    response = await router.process(player, player, "!MP")

    assert response == {"resp": "help | Elapsed: 4ns", "hidden": False}
    assert received_context is not None
    assert received_context.trigger == "help"
    assert received_context.args == ()


def test_router_rejects_duplicate_regular_triggers_and_aliases() -> None:
    router = _router()

    @router.command("recent", privileges=Privileges.UNRESTRICTED, aliases=("r",))
    async def recent(context: Context) -> None:
        pass

    with pytest.raises(DuplicateCommandError, match="'r' is already registered"):

        @router.command("retry", privileges=Privileges.UNRESTRICTED, aliases=("R",))
        async def retry(context: Context) -> None:
            pass


def test_router_rejects_a_group_trigger_that_conflicts_with_a_command() -> None:
    router = _router()

    @router.command("mp", privileges=Privileges.UNRESTRICTED)
    async def multiplayer(context: Context) -> None:
        pass

    with pytest.raises(
        DuplicateCommandError,
        match="'mp' is already registered as a command",
    ):
        router.create_group("MP", "Multiplayer commands.")


async def test_command_exceptions_are_contained(
    capsys: pytest.CaptureFixture[str],
) -> None:
    router = _router(times=[20, 29])
    player = _player(Privileges.UNRESTRICTED)

    @router.command("fail", privileges=Privileges.UNRESTRICTED, hidden=True)
    async def failing_command(context: Context) -> str:
        raise RuntimeError("boom")

    response = await router.process(player, player, "!fail")

    assert response == {
        "resp": "An exception occurred when running the command. | Elapsed: 9ns",
        "hidden": True,
    }
    assert "RuntimeError: boom" in capsys.readouterr().err


async def test_command_registrations_are_owned_by_each_router_instance() -> None:
    first_router = _router()
    second_router = _router()
    player = _player(Privileges.UNRESTRICTED)

    @first_router.command("which", privileges=Privileges.UNRESTRICTED)
    async def first(context: Context) -> str:
        return "first"

    @second_router.command("which", privileges=Privileges.UNRESTRICTED)
    async def second(context: Context) -> str:
        return "second"

    first_response = await first_router.process(player, player, "!which")
    second_response = await second_router.process(player, player, "!which")

    assert first_response == {"resp": "first | Elapsed: 0ns", "hidden": False}
    assert second_response == {"resp": "second | Elapsed: 0ns", "hidden": False}
