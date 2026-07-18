from __future__ import annotations

import traceback
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import TypedDict

from app.constants.privileges import Privileges

if TYPE_CHECKING:
    from app.objects.channel import Channel
    from app.objects.player import Player


@dataclass(frozen=True)
class Context:
    player: Player
    trigger: str
    args: tuple[str, ...]
    recipient: Channel | Player


class CommandResponse(TypedDict):
    resp: str | None
    hidden: bool


CommandCallback = Callable[[Context], Awaitable[str | None]]
Clock = Callable[[], int]
ElapsedFormatter = Callable[[int], str]


@dataclass(frozen=True)
class Command:
    triggers: tuple[str, ...]
    callback: CommandCallback
    privileges: Privileges
    hidden: bool
    description: str | None


class DuplicateCommandError(ValueError):
    pass


def _normalize_trigger(trigger: str, *, allow_empty: bool) -> str:
    if trigger != trigger.strip():
        raise ValueError("command triggers may not contain surrounding whitespace")
    if not allow_empty and not trigger:
        raise ValueError("command triggers may not be empty")
    if any(character.isspace() for character in trigger):
        raise ValueError("command triggers may not contain whitespace")
    return trigger.casefold()


class CommandGroup:
    def __init__(self, trigger: str, description: str) -> None:
        self.trigger = trigger
        self.description = description
        self._commands_by_trigger: dict[str, Command] = {}
        self._commands: list[Command] = []

    @property
    def commands(self) -> tuple[Command, ...]:
        return tuple(self._commands)

    def register(
        self,
        callback: CommandCallback,
        *,
        trigger: str,
        privileges: Privileges,
        aliases: Sequence[str] = (),
        hidden: bool = False,
        description: str | None = None,
    ) -> CommandCallback:
        triggers = self._prepare_triggers(trigger, aliases)
        command = Command(
            triggers=triggers,
            callback=callback,
            privileges=privileges,
            hidden=hidden,
            description=description if description is not None else callback.__doc__,
        )

        for registered_trigger in triggers:
            self._commands_by_trigger[registered_trigger] = command
        self._commands.append(command)
        return callback

    def command(
        self,
        trigger: str,
        *,
        privileges: Privileges,
        aliases: Sequence[str] = (),
        hidden: bool = False,
        description: str | None = None,
    ) -> Callable[[CommandCallback], CommandCallback]:
        def decorator(callback: CommandCallback) -> CommandCallback:
            return self.register(
                callback,
                trigger=trigger,
                privileges=privileges,
                aliases=aliases,
                hidden=hidden,
                description=description,
            )

        return decorator

    def get(self, trigger: str) -> Command | None:
        return self._commands_by_trigger.get(trigger.casefold())

    def _prepare_triggers(
        self,
        trigger: str,
        aliases: Sequence[str],
    ) -> tuple[str, ...]:
        triggers = (
            _normalize_trigger(trigger, allow_empty=False),
            *(_normalize_trigger(alias, allow_empty=True) for alias in aliases),
        )
        if len(set(triggers)) != len(triggers):
            raise DuplicateCommandError(
                f"duplicate trigger while registering a command in {self.trigger!r}",
            )

        duplicate = next(
            (
                registered_trigger
                for registered_trigger in triggers
                if registered_trigger in self._commands_by_trigger
            ),
            None,
        )
        if duplicate is not None:
            raise DuplicateCommandError(
                f"trigger {duplicate!r} is already registered in {self.trigger!r}",
            )
        return triggers


class CommandRouter:
    def __init__(
        self,
        *,
        prefix: str,
        clock: Clock,
        format_elapsed: ElapsedFormatter,
    ) -> None:
        if not prefix:
            raise ValueError("command prefix may not be empty")

        self.prefix = prefix
        self._clock = clock
        self._format_elapsed = format_elapsed
        self._commands_by_trigger: dict[str, Command] = {}
        self._commands: list[Command] = []
        self._groups_by_trigger: dict[str, CommandGroup] = {}
        self._groups: list[CommandGroup] = []

    @property
    def commands(self) -> tuple[Command, ...]:
        return tuple(self._commands)

    @property
    def groups(self) -> tuple[CommandGroup, ...]:
        return tuple(self._groups)

    def register(
        self,
        callback: CommandCallback,
        *,
        trigger: str,
        privileges: Privileges,
        aliases: Sequence[str] = (),
        hidden: bool = False,
        description: str | None = None,
    ) -> CommandCallback:
        triggers = self._prepare_triggers(trigger, aliases)
        command = Command(
            triggers=triggers,
            callback=callback,
            privileges=privileges,
            hidden=hidden,
            description=description if description is not None else callback.__doc__,
        )

        for registered_trigger in triggers:
            self._commands_by_trigger[registered_trigger] = command
        self._commands.append(command)
        return callback

    def command(
        self,
        trigger: str,
        *,
        privileges: Privileges,
        aliases: Sequence[str] = (),
        hidden: bool = False,
        description: str | None = None,
    ) -> Callable[[CommandCallback], CommandCallback]:
        def decorator(callback: CommandCallback) -> CommandCallback:
            return self.register(
                callback,
                trigger=trigger,
                privileges=privileges,
                aliases=aliases,
                hidden=hidden,
                description=description,
            )

        return decorator

    def create_group(self, trigger: str, description: str) -> CommandGroup:
        normalized_trigger = _normalize_trigger(trigger, allow_empty=False)
        if normalized_trigger in self._groups_by_trigger:
            raise DuplicateCommandError(
                f"command group {normalized_trigger!r} is already registered",
            )
        if normalized_trigger in self._commands_by_trigger:
            raise DuplicateCommandError(
                f"trigger {normalized_trigger!r} is already registered as a command",
            )

        group = CommandGroup(normalized_trigger, description)
        self._groups_by_trigger[normalized_trigger] = group
        self._groups.append(group)
        return group

    async def process(
        self,
        player: Player,
        recipient: Channel | Player,
        message: str,
    ) -> CommandResponse | None:
        if not message.startswith(self.prefix):
            return None

        started_at = self._clock()
        trigger, args = self._parse_message(message)

        group = self._groups_by_trigger.get(trigger)
        if group is not None:
            if args:
                trigger, args = args[0].casefold(), args[1:]
            else:
                trigger = "help"

            command = group.get(trigger)
        else:
            command = self._commands_by_trigger.get(trigger)

        if command is None or player.priv & command.privileges != command.privileges:
            return None

        try:
            response = await command.callback(
                Context(
                    player=player,
                    trigger=trigger,
                    args=args,
                    recipient=recipient,
                ),
            )
        except Exception:
            traceback.print_exc()
            response = "An exception occurred when running the command."

        if response is None:
            return {"resp": None, "hidden": False}

        elapsed = self._format_elapsed(self._clock() - started_at)
        return {
            "resp": f"{response} | Elapsed: {elapsed}",
            "hidden": command.hidden,
        }

    def _prepare_triggers(
        self,
        trigger: str,
        aliases: Sequence[str],
    ) -> tuple[str, ...]:
        triggers = (
            _normalize_trigger(trigger, allow_empty=False),
            *(_normalize_trigger(alias, allow_empty=True) for alias in aliases),
        )
        if len(set(triggers)) != len(triggers):
            raise DuplicateCommandError("duplicate trigger while registering a command")

        duplicate = next(
            (
                registered_trigger
                for registered_trigger in triggers
                if registered_trigger in self._commands_by_trigger
                or registered_trigger in self._groups_by_trigger
            ),
            None,
        )
        if duplicate is not None:
            raise DuplicateCommandError(f"trigger {duplicate!r} is already registered")
        return triggers

    def _parse_message(self, message: str) -> tuple[str, tuple[str, ...]]:
        content = message[len(self.prefix) :].strip()
        if not content:
            return "", ()

        trigger, *args = content.split()
        return trigger.casefold(), tuple(args)
