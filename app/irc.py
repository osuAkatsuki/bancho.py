from __future__ import annotations

import asyncio
import re
import time
import traceback
from typing import Optional

import app.packets
import app.settings
import app.state
from app import commands
from app.logging import Ansi
from app.logging import log
from app.objects.channel import Channel
from app.objects.player import Player
from app.utils import make_safe_name


NAME = "banchopy-irc"
WHITE_SPACE = re.compile(r"\r?\n")


# Custom Bancho IRC exception.
class BanchoIRCException(Exception):
    """Custom expection."""

    def __init__(self, code_error: int, error: str):
        self.code: int = code_error
        self.error: str = error

    def __str__(self) -> str:
        return repr(self.error)


class IRCClient:
    def __init__(
        self,
        server: IRCServer,
        writer: asyncio.StreamWriter,
    ):
        self.ping_time = int(time.time())
        self.queue = bytearray()
        self.socket = writer
        self.server = server
        self.player: Player | None = None

    def __repr__(self) -> str:
        if self.player is not None:
            return f"{self.player.name}@{NAME}"
        else:
            return f"UNAUTHORIZED@{NAME}"

    def __str__(self) -> str:
        if self.player is not None:
            return f"{self.player.name}@{NAME}"
        else:
            return f"UNAUTHORIZED@{NAME}"

    def dequeue(self) -> bytearray:
        buffer = self.queue
        self.queue = bytearray()
        return buffer

    def add_queue(self, message: str) -> None:
        self.socket.write((message + "\r\n").encode())

    def send_welcome_msg(self) -> None:
        if self.player is None:
            raise RuntimeError(
                "Attempted to send welcome message to an unauthenticated IRC client.",
            )

        self.add_queue(
            f":{NAME} 001 {self.player.name} :Welcome to the Internet Relay Network, {self!r}",
        )
        self.add_queue(
            f":{NAME} 002 :- Your host is {self.socket.get_extra_info('peername')[0]}, running version bancho.py-{app.settings.VERSION}",
        )
        self.add_queue(
            f":{NAME} 251 :- There are {len(app.state.sessions.players)} users and 0 services on 1 server",
        )
        self.add_queue(f":{NAME} 375 :- {NAME} Message of the day - ")
        self.add_queue(
            f":{NAME} 372 {self.player.name} :- Visit https://github.com/osuAkatsuki/bancho.py",
        )
        self.add_queue(f":{NAME} 376 :End of MOTD command")

    async def login(self, irc_key: str = "") -> Player | None:
        player = await app.state.sessions.players.from_cache_or_sql(
            irc_key=irc_key,
        )

        if not player:
            raise BanchoIRCException(464, f"PASS :Incorrect password")

        if player.restricted:
            return None

        player.irc_client = True

        async with app.state.services.database.connection() as db_conn:
            await player.stats_from_sql_full(db_conn)

        user_data = app.packets.user_presence(player) + app.packets.user_stats(player)

        player.generate_token()
        player.last_recv_time = time.time()

        app.state.sessions.players.append(player)
        app.state.sessions.players.enqueue(user_data)

        log(f"{player} logged in from IRC", Ansi.LCYAN)

        return player

    async def data_received(self, data: bytes) -> None:
        message = data.decode("utf-8")
        try:
            client_data = WHITE_SPACE.split(message)[:-1]
            for cmd in client_data:
                if len(cmd) > 0:
                    command, args = cmd.split(" ", 1)
                else:
                    command, args = (cmd, "")

                if command == "CAP":
                    continue

                if command == "PASS":
                    player = await self.login(args)

                    if player:
                        self.player = player
                        self.send_welcome_msg()
                        continue

                    raise BanchoIRCException(464, f"{command} :Incorrect password")

                handler = getattr(self, f"handler_{command.lower()}", None)
                if not handler:
                    raise BanchoIRCException(421, f"{command} :Unknown Command!")

                await handler(args)
        except BanchoIRCException as e:
            self.socket.write(f":{NAME} {e.code} {e.error}\r\n".encode())
        except Exception as e:
            self.socket.write(f":{NAME} ERROR {repr(e)}".encode())
            traceback.print_exc()

    async def handler_nick(self, args: str) -> None:
        pass

    async def handler_ping(self, args: str) -> None:
        if self.player is None:
            raise RuntimeError(
                "Attempted to handle a ping from an unauthenticated IRC client.",
            )

        self.ping_time = int(time.time())
        self.add_queue(f":{NAME} PONG :{NAME}")

        if self.player.irc_client:
            self.player.last_recv_time = time.time()

    async def handler_privmsg(self, args: str) -> None:
        if self.player is None:
            raise RuntimeError(
                "Attempted to handle a private message from an unauthenticated IRC client.",
            )

        recipient, msg = args.split(" ", 1)
        msg = msg[1:]
        if recipient.startswith("#") or recipient.startswith("$"):
            channel = app.state.sessions.channels.get_by_name(recipient)
            if not channel:
                raise BanchoIRCException(
                    403,
                    f"{recipient} :Cannot send a message to a non-existing channel",
                )

            if channel not in self.player.channels:
                raise BanchoIRCException(
                    404,
                    f"{recipient} :Cannot send message to the channel",
                )

            await self.send_message(self.player, recipient, msg)

            for client in self.server.authorized_clients:
                assert client.player is not None

                if channel in client.player.channels and client != self:
                    client.add_queue(
                        f":{self.player.safe_name} PRIVMSG {recipient} :{msg}",
                    )
        else:
            await self.send_message(self.player, recipient, msg)

            for client in self.server.authorized_clients:
                assert client.player is not None

                if client.player.name == recipient:
                    client.add_queue(f":{self.player.name} PRIVMSG {recipient} :{msg}")

    async def handler_part(self, channel: str) -> None:
        if self.player is None:
            raise RuntimeError(
                "Attempted to handle a channel part from an unauthenticated IRC client.",
            )

        channel = channel.split(" ")[0]
        chan = app.state.sessions.channels.get_by_name(channel)

        if not chan:
            raise BanchoIRCException(
                403,
                f"{channel} :No channel named {channel} has been found",
            )

        if chan in self.player.channels:
            for client in self.server.authorized_clients:
                assert client.player is not None

                if chan in client.player.channels:
                    client.add_queue(f":{self.player.name} PART :{chan.name}")

            self.player.leave_channel(chan)
        else:
            raise BanchoIRCException(
                442,
                f"{channel} :You're not on that channel",
            )

    async def handler_join(self, channel: str) -> None:
        if self.player is None:
            raise RuntimeError(
                "Attempted to handle a channel join from an unauthenticated IRC client.",
            )

        chan = app.state.sessions.channels.get_by_name(channel)

        if not chan:
            raise BanchoIRCException(
                403,
                f"{channel} :No channel named {channel} has been found",
            )

        if self.player.join_channel(chan):
            for client in self.server.authorized_clients:
                assert client.player is not None

                if chan in client.player.channels:
                    client.add_queue(f":{self.player.name} JOIN :{chan._name}")

            if chan.topic:
                self.add_queue(f"332 {chan._name} :{chan.topic}")
            else:
                self.add_queue(f"331 {chan._name} :No topic is set")

            nicks = " ".join([x.name for x in chan.players])
            self.add_queue(f":{NAME} 353 {self.player.name} = {chan._name} :{nicks}")
            self.add_queue(
                f":{NAME} 366 {self.player.name} {chan._name} :End of NAMES list",
            )
        else:
            raise BanchoIRCException(
                403,
                f"{channel} :No channel named {channel} has been found",
            )

    async def handler_user(self, args: str) -> None:
        pass

    async def handler_away(self, args: str) -> None:
        pass

    async def handler_quit(self, args: str) -> None:
        if self.player is None:
            raise RuntimeError(
                "Attempted to handle a quit from an unauthenticated IRC client.",
            )

        for chan in self.player.channels:
            for client in self.server.authorized_clients:
                assert client.player is not None

                if chan in client.player.channels:
                    client.add_queue(f":{self.player.name} QUIT :{args.lstrip(':')}")

            if self.player.irc_client:
                self.player.logout()
                log(f"{self.player} disconnected from IRC", Ansi.YELLOW)

        self.socket.close()
        await self.socket.wait_closed()

    async def send_message(self, fro: Player, to: str, message: str) -> int:
        if to.startswith("#"):
            channel = app.state.sessions.channels.get_by_name(to)

            if not channel:
                return 403

            if message.startswith(app.settings.COMMAND_PREFIX):
                cmd = await commands.process_commands(fro, channel, message)
            else:
                cmd = None

            if cmd:
                # a command was triggered.
                if not cmd["hidden"]:
                    channel.send(message, sender=fro)
                    if cmd["resp"] is not None:
                        channel.send_bot(cmd["resp"])
                else:
                    staff = app.state.sessions.players.staff
                    channel.send_selective(
                        msg=message,
                        sender=fro,
                        recipients=staff - {fro},
                    )
                    if cmd["resp"] is not None:
                        channel.send_selective(
                            msg=cmd["resp"],
                            sender=app.state.sessions.bot,
                            recipients=staff | {fro},
                        )
            else:
                channel.send(message, fro)
                log(
                    f"{fro} @ {channel}: {message}",
                    Ansi.LCYAN,
                    file=".data/logs/chat.log",
                )
        else:
            recipient = await app.state.sessions.players.from_cache_or_sql(
                name=make_safe_name(to),
            )

            if not recipient:
                return 401

            if recipient.bot_client:
                if message.startswith(app.settings.COMMAND_PREFIX):
                    cmd = await commands.process_commands(fro, recipient, message)
                else:
                    cmd = None

                if cmd:
                    recipient.send(message, sender=fro)

                    if cmd["resp"] is not None:
                        fro.send_bot(cmd["resp"])
            else:
                recipient.send(message, fro)
                log(
                    f"{fro} @ {recipient}: {message}",
                    Ansi.LCYAN,
                    file=".data/logs/chat.log",
                )

        return 1


class IRCServer:
    def __init__(self, port: int, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        self.host = "0.0.0.0"
        self.port = port
        self.socket_server: asyncio.Server | None = None
        self.clients: set[IRCClient] = set()

    @property
    def authorized_clients(self) -> set[IRCClient]:
        return {x for x in self.clients if x.player is not None}

    def bancho_join(self, player: Player, channel: Channel) -> None:
        for client in self.authorized_clients:
            assert client.player is not None

            if channel in client.player.channels:
                client.add_queue(f":{player.name} JOIN {channel.name}")

    def bancho_part(self, player: Player, channel: Channel) -> None:
        for client in self.authorized_clients:
            assert client.player is not None

            if channel in client.player.channels:
                client.add_queue(f":{player.name} PART {channel.name}")

    def bancho_message(self, fro: str, to: str, message: str) -> None:
        if to.startswith("#"):
            for client in self.authorized_clients:
                assert client.player is not None

                if client.player.name != fro and to in [
                    x.name for x in client.player.channels
                ]:
                    client.add_queue(f":{fro} PRIVMSG {to} :{message}")
        else:
            for client in self.authorized_clients:
                assert client.player is not None

                if client.player.name == to and client.player.name != fro:
                    client.add_queue(f":{fro} PRIVMSG {to} :{message}")

    async def callback_handler(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        client = IRCClient(self, writer)

        try:
            self.clients.add(client)
            while True:
                dequeue = client.dequeue()
                if dequeue:
                    writer.write(dequeue)

                data = await reader.read(4096)
                message = data.decode("utf-8")
                try:
                    await client.data_received(data)
                except BanchoIRCException as e:
                    writer.write(e.error.encode())

                if app.settings.DEBUG:
                    message = message.replace("\r\n", "; ")
                    log(f"[IRC] Received: {message}", Ansi.LGREEN)

                await writer.drain()
        except ConnectionResetError:
            client.socket.close()
            await client.socket.wait_closed()
        finally:
            self.clients.remove(client)
            writer.close()

    async def start(self) -> IRCServer:
        server = await asyncio.start_server(
            self.callback_handler,
            self.host,
            self.port,
            loop=self.loop,
        )

        sockname = server.sockets[0].getsockname()
        log(
            f"Serving IRC on {sockname[0]}:{sockname[1]}",
            Ansi.LCYAN,
        )

        self.socket_server = server
        return self
