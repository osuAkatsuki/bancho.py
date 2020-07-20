# -*- coding: utf-8 -*-

from socket import socket

__all__ = (
    'Connection',
    'Request',
    'Response',
    'Address'
)

from typing import Tuple, Union
# Will be (host: str, port: int) if INET,
# or (sock_dir: str) if UNIX.
Address = Union[Tuple[str, int], str]

class Request:
    __slots__ = ('headers', 'body', 'data', 'cmd', 'uri', 'httpver', 'args')

    def __init__(self, data: bytes):
        self.data = data
        self.parse_http_request()

    def parse_http_request(self) -> None:
        s = self.data.split(b'\r\n\r\n')

        # Split all headers up by newline.
        # This includes the HTTP request line.
        _headers = s[0].decode('utf-8', 'strict').split('\r\n')

        # Split request line into (command, uri, version)
        self.cmd, full_uri, self.httpver = _headers[0].split(' ')

        if self.cmd == 'GET':
            if (params_begin := full_uri.find('?')) != -1:
                self.uri = full_uri[:params_begin]
                self.args = {k: v for k, v in (
                    i.split('=') for i in full_uri[params_begin + 1:].split('&')
                )}
            else:
                self.args = None
                self.uri = full_uri
        else:
            # TODO: POST args
            self.args = None
            self.uri = full_uri

        # Split headers into key: value pairs.
        self.headers = {k: v.lstrip() for k, v in (h.split(':') for h in _headers[1:])}

        # Keep the body as bytes.
        self.body = s[1]

class Response:
    __slots__ = ('sock', 'headers')

    def __init__(self, sock: socket) -> None:
        self.sock = sock
        self.headers = []

    def add_header(self, header: str) -> None:
        self.headers.append(header)

    def send(self, data: bytes, code: int = 200) -> None:
        # Insert HTTP response line & content
        # length at the beginning of the headers.
        self.headers.insert(
            0, 'HTTP/1.1 ' + {
                200: '200 OK',
                404: '404 NOT FOUND'
            }[code])
        self.headers.insert(1, f'Content-Length: {len(data)}')
        self.sock.send('\r\n'.join(self.headers).encode() + b'\r\n\r\n' + data)

class Connection: # will probably end up removing addr?
    __slots__ = ('request', 'response', 'addr')

    def __init__(self, sock: socket, addr: Address) -> None:
        self.request = Request(self.read_data(sock))
        self.response = Response(sock)
        self.addr = addr

    @staticmethod
    def read_data(sock: socket) -> bytes:
        # Read all bytes from a socket.
        data = sock.recv(1024)
        if len(data) % 1024 == 0:
            data += sock.recv(1024)

        return data
