# -*- coding: utf-8 -*-

class Request:
    def __init__(self, data: bytes) -> None:
        # Headers are converted from bytes to a string,
        # while the request body is left as bytes.
        self.data = data
        self.headers = {}
        self.body = []
        self.parse()

    def parse(self) -> None:
        s = [i for i in self.data.split(b'\r\n\r\n')]
        for h in s[0].decode().split('\r\n')[1:]:
            split = [i.strip() for i in h.split(':')]
            self.headers.update({split[0]: split[1]})
        self.body = s[1]

class Response:
    def __init__(self) -> None:
        pass
