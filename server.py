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
from time import time, sleep
from enum import IntFlag, IntEnum, unique, auto
from os import path, chmod, remove
from random import choices
from string import ascii_lowercase
from threading import Thread

from db.dbConnector import SQLPool

import packets
import config

from objects import glob
from objects.player import Player
from objects.collections import PlayerList, ChannelList
from objects.channel import Channel
from objects.web import Request#, Response
from constants import Privileges, Type

class Server:
    def __init__(self, *args, **kwargs) -> None:
        self.run_time = time()
        self.shutdown = False # used to break loop lol

        glob.db = SQLPool(pool_size = 4, config = config.mysql)

        # Default channels.
        # At some point, this will either be moved
        # to db, or possibly just configration.
        glob.channels.add(Channel(
            name = '#osu',
            topic = 'First topic',
            read = Privileges.Verified,
            write = Privileges.Verified,
            auto_join = True))
        glob.channels.add(Channel(
            name = '#announce',
            topic = 'Second topic',
            read = Privileges.Verified,
            write = Privileges.Admin,
            auto_join = True))
        glob.channels.add(Channel(
            name = '#frosti',
            topic = 'drinks',
            read = Privileges.Dangerous,
            write = Privileges.Dangerous,
            auto_join = False))

        self.start(config.concurrent) # starts server

    @staticmethod
    def ping_timeouts() -> None:
        # no idea if this thing works
        current_time = int(time())
        for p in glob.players.players:
            if p.ping_time + config.max_ping < current_time:
                pass#p.enqueue(new packet PLZ)

        sleep(config.max_ping)

    def start(self, connections: int = 10) -> None:
        if path.exists(config.sock_file):
            remove(config.sock_file)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.bind(config.sock_file)
            chmod(config.sock_file, 0o777)
            s.listen(connections)

            # Set up ping pingout loop
            Thread(target = self.ping_timeouts)

            print('\x1b[0;92mListening for connections..\x1b[0m')

            while not self.shutdown:
                conn, _ = s.accept()
                with conn:
                    try:
                        self.handle_connection(conn)
                    except BrokenPipeError: # will probably remove in production,
                                            # only really happens in debugging
                        print('Connection timed out..')

        print('\x1b[0;92mSocket closed..\x1b[0m')

    def handle_connection(self, conn: socket.socket) -> None:
        #from io import BufferedIOBase
        start_time = time()
        #stream = BufferedIOBase()
        #stream.read()
        data = conn.recv(config.max_bytes)
        while len(data) % config.max_bytes == 0:
            data += conn.recv(config.max_bytes)

        req = Request(data)

        if 'User-Agent' not in req.headers \
        or req.headers['User-Agent'] != 'osu!':
            return

        if 'osu-token' not in req.headers:
            ret = self.handle_login(req)
        elif not(p := glob.players.get(req.headers['osu-token'])):
            # A little bit suboptimal, but fine for now?
            print('Token not found, forcing relog.')
            pw = packets.PacketWriter()
            pw.write(packets.Packet.s_notification, ('Server is restarting.. one moment', Type.string))
            pw.write(packets.Packet.s_restart, (500, Type.i32))
            ret = bytes(pw)
        else: # Player found, process normal packet.
            pr = packets.PacketReader(req.body)
            while not pr.empty(): # iterate thru available packets
                pr.read_packet_header()
                if not (pr.packetID):
                    continue
                print(f'Handling packet {pr.packetID} (len {pr.length})')
                if pr.packetID == 4: # Ping, no resp so just
                    print('pong') # update and kill it
                    p.ping_time = time()
                    return

                map = {
                    packets.Packet.c_changeAction: packets.readStatus, # 0: user wishes to inform otehrs
                    #Packet.c_changeAction: 1,#statusUpdate,
                    packets.Packet.c_logout: packets.Logout, # 2: logout
                    packets.Packet.c_requestStatusUpdate: packets.statsUpdateRequest, # 3
                    packets.Packet.c_channelJoin: packets.joinChannel, # 63
                    packets.Packet.c_userStatsRequest: packets.statsRequest # 85
                }

                if pr.packetID not in map:
                    print(f'\x1b[0;93mUnhandled: {pr.packetID} (len {pr.length}) took {(time() - start_time) * 1000:.2f}ms.\x1b[0m')
                    return

                ret = map[pr.packetID](p, pr) or b''

                while not p._queue.empty():
                    # suboptimal bytestring concat zzzzz
                    ret += p._queue.get_nowait()

        conn.send(ret)
        print(f'Packet took {(time() - start_time) * 1000:.2f}ms.')

    def handle_login(self, req: Request) -> None:
        # TODO: use enqueue
        username, pw_hash, user_data = [s for s in req.body.decode().split('\n') if s]
        build_name, utc_offset, display_city, client_hashes, pm_private = user_data.split('|')

        if req.headers['osu-version'] != build_name:
            return

        if not (res := glob.db.fetch(
            'SELECT id, name, priv FROM users WHERE name_safe = %s',
            [Player.ensure_safe(username)]
        )):
            # Incorrect login (-1)
            pw = packets.PacketWriter()
            pw.add_header(f'cho-token: no')
            pw.write(packets.Packet.s_userID, (-1, Type.i32))
            return bytes(pw)

        p = Player(utc_offset = int(utc_offset), pm_private = int(pm_private), **res)
        glob.players.add(p)

        pw = packets.PacketWriter()
        pw.add_header(f'cho-token: {p.token}')
        pw.write(packets.Packet.s_userID, (p.id, Type.i32))
        pw.write(packets.Packet.s_protocolVersion, (19, Type.i32))
        pw.write(packets.Packet.s_supporterGMT, (p.bancho_priv, Type.i32))
        pw.write(packets.Packet.s_notification, ('987654321 Welcome gamers 123456789', Type.string))
        #pw.write(packets.Packet.s_RTX, ('Test', Type.string))

        # channels
        pw.write(packets.Packet.s_channelInfoEnd)
        for c in glob.channels.channels: # TODO: __iter__ and __next__ in all collections
            if not p.priv & c.read:
                continue # no priv to read

            pw.write(packets.Packet.s_channelInfo,
                (c.name, Type.string),
                (c.topic, Type.string),
                (len(c.players), Type.i16))

            # Autojoinable channels
            if c.auto_join and c.join(p):
                pw.write(packets.Packet.s_channelJoinSuccess, (c.name, Type.string))

        return bytes(pw)

if __name__ == '__main__':
    serv = Server(host = '127.0.0.1', port = 5001)
