from socket import socket, AF_INET, AF_UNIX, SOCK_STREAM
from typing import Generator

from objects import glob
from objects.web import Address
from objects.web import Connection
from console import *

__all__ = ('Server',)

class Server:
    __slots__ = ('sock_family', 'sock_type', 'listening')

    def __init__(self, sock_family: int = AF_INET,
                 sock_type: int = SOCK_STREAM) -> None:
        self.sock_family = sock_family
        self.sock_type = sock_type
        self.listening = False # used to break loop lol

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb) -> None:
        pass

    def listen(self, addr: Address, max_conns: int = 5
              ) -> Generator[Connection, None, None]:
        if (unix_sock := self.sock_family == AF_UNIX):
            from os import path, remove
            if path.exists(glob.config.sock_file):
                remove(glob.config.sock_file)

        with socket(self.sock_family, self.sock_type) as s:
            s.bind(addr)

            if unix_sock:
                from os import chmod
                chmod(addr, 0o777)

            self.listening = True
            s.listen(max_conns)

            # TODO: ping timeout loop

            printlog('Listening for connections', Ansi.LIGHT_GREEN)

            while self.listening:
                yield Connection(*s.accept())

        printlog('Socket closed..', Ansi.LIGHT_GREEN)
