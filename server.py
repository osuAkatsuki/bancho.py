# OSU SERVER ATTEMPT #3
# This is going to be disgusting.
# I've reached a point where I don't care
# about doing things right the first time;
# i will learn from iteration, and this
# iteration will be a fucking diaster 100%.

from typing import Any, Final, Tuple, Dict, List
#import asyncio
#from aiohttp import web
import socket
import struct
from time import time
from enum import IntFlag, IntEnum, unique, auto
from os import path, chmod, remove
from random import choices
from string import ascii_lowercase

from db.dbConnector import SQLPool
from packets import Packet, PacketWriter, statusUpdate
from objects.player import Player, PlayerManager
from objects.channel import Channel
from objects.web import Request#, Response
from constants import Privileges, Type
import config

class Server:
    def __init__(self, *args, **kwargs) -> None:
        self.players = PlayerManager()
        self.channels = (
            Channel(
                name = '#osu',
                topic = 'First topic',
                read = Privileges.Verified,
                write = Privileges.Verified,
                auto_join = False),
            Channel(
                name = '#announce',
                topic = 'Second topic',
                read = Privileges.Verified,
                write = Privileges.Admin,
                auto_join = True),
            Channel(
                name = '#frosti',
                topic = 'drinks',
                read = Privileges.Dangerous,
                write = Privileges.Dangerous
            )
        )

        self.start_time = 0

        self.db = SQLPool(pool_size = 4, config = config.mysql)
        self.start(config.concurrent) # starts server

    def start(self, connections: int = 10) -> None:
        if path.exists(config.sock_file):
            remove(config.sock_file)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.bind(config.sock_file)
            chmod(config.sock_file, 0o777)
            s.listen(connections)

            while True:
                conn, _ = s.accept()
                with conn:
                    self.handle_connection(conn)

    def handle_connection(self, conn: socket.socket) -> None:
        self.start_time = time()
        data = conn.recv(config.max_bytes)
        while len(data) % config.max_bytes == 0:
            data += conn.recv(config.max_bytes)

        req = Request(data)

        if 'User-Agent' not in req.headers \
        or req.headers['User-Agent'] != 'osu!':
            return

        if 'osu-token' not in req.headers:
            #self.handle_login(conn, headers, [s for s in body.split(b'\n') if s])
            self.handle_login(conn, req)
        else:
            if not (p := self.players.get(req.headers['osu-token'])):
                print('Token not found, forcing relog.')
                pw = PacketWriter()
                pw.write(Packet.s_userID, (-5, Type.i32))
                conn.send(bytes(pw))
                return

            packetID, length = struct.unpack('<hxi', req.body[:7])

            if packetID == 4: # Ping
                print('pong')
                p.ping_time = time()
                return

            map = {
                Packet.c_changeAction: statusUpdate,
            }

            # madness ensues
            if packetID in map:
                if not (ret := map[packetID](p, req)):
                    raise Exception('Critical failure')

                conn.send(bytes(ret))
                return

            # has already logged in
            print(f'\x1b[0;93mUnhandled: {packetID} (len {length})\x1b[0m')

    def handle_login(self, conn: socket.socket, req: Request) -> None:
        username, pw_hash, user_data = [s for s in req.body.decode().split('\n') if s]
        build_name, utc_offset, display_city, client_hashes, pm_private = user_data.split('|')

        if req.headers['osu-version'] != build_name:
            return

        if not (res := self.db.fetch(
            'SELECT id, name, priv FROM users WHERE name_safe = %s',
            [Player.ensure_safe(username)]
        )):
            # Incorrect login (-1)
            pw = PacketWriter()
            pw.write(Packet.s_userID, (-1, Type.i32))
            conn.send(bytes(pw))
            return

        p = Player(utc_offset = int(utc_offset), pm_private = int(pm_private), **res)
        self.players.add(p)

        pw = PacketWriter()
        pw.add_header(f'cho-token: {p.token}')
        pw.write(Packet.s_userID, (p.id, Type.i32))
        pw.write(Packet.s_protocolVersion, (19, Type.i32))
        pw.write(Packet.s_supporterGMT, (p.bancho_priv, Type.i32))
        pw.write(Packet.s_notification, ('987654321 Welcome gamers 123456789', Type.string))
        #pw.write(Packet.s_RTX, ('Test', Type.string))

        # channels
        pw.write(Packet.s_channelInfoEnd)
        for c in self.channels:
            if not p.priv & c.read:
                continue # no priv to read

            # autojoin channels
            if c.auto_join and c.join(p):
                p.join_channel(c)

            pack = Packet.c_channelJoin if c.auto_join \
              else Packet.s_channelInfo

            pw.write(pack,
                (c.name, Type.string),
                (c.topic, Type.string),
                (len(c.players), Type.i16))


        r = bytes(pw)
        print(r)
        conn.send(r)
        print(f'Login took {(time() - self.start_time) * 1000:.2f}ms.')

if __name__ == '__main__':
    s = Server(host = '127.0.0.1', port = 5001)
