# -*- coding: utf-8 -*-

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
from datetime import datetime as dt

from db.dbConnector import SQLPool

import packets
import config
from console import *

from objects import glob
from events import events
from objects.collections import PlayerList, ChannelList
from objects.channel import Channel
from objects.web import Request#, Response
from constants import Privileges, Type

class Server:
    def __init__(self, *args, **kwargs) -> None:
        self.run_time = time()
        self.shutdown = False # used to break loop lol

        glob.config = config
        glob.version = 1.0 # server version
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

        self.packet_map = {
            packets.Packet.c_changeAction: events.readStatus, # 0: client changed action
            packets.Packet.c_sendPublicMessage: events.sendMessage, # 1: client send a message
            packets.Packet.c_logout: events.logout, # 2: client logged out
            packets.Packet.c_requestStatusUpdate: events.statsUpdateRequest, # 3: client wants their stats updated
            packets.Packet.c_ping: events.ping, # 4: client wants their ping time updated
            packets.Packet.c_channelJoin: events.channelJoin, # 63: client joined a channel
            packets.Packet.c_channelPart: events.channelPart, # 78: client left a channel
            packets.Packet.c_userStatsRequest: events.statsRequest, # 85: client wants everyones stats
            packets.Packet.c_userPresenceRequest: events.userPresenceRequest # 97: client wants presence of specific users
        }

        self.start(config.concurrent) # starts server

    @staticmethod
    def ping_timeouts() -> None:
        # no idea if this thing works
        current_time = int(time())
        for p in glob.players.players:
            if p.ping_time + config.max_ping < current_time:
                printlog(f'Requesting ping from user {p.name} after {p.ping_time}')
                p.enqueue(packets.pong())

        sleep(config.max_ping)

    def start(self, connections: int = 10) -> None:
        if path.exists(config.sock_file):
            remove(config.sock_file)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.bind(config.sock_file)
            chmod(config.sock_file, 0o777)
            s.listen(connections)

            # Set up ping pingout loop
            Thread(target = self.ping_timeouts).start()

            printlog('Listening for connections', Ansi.LIGHT_GREEN)

            while not self.shutdown:
                conn, _ = s.accept()
                with conn:
                    try:
                        self.handle_connection(conn)
                    except BrokenPipeError: # will probably remove in production,
                                            # only really happens in debugging
                        printlog('Connection timed out?')

        printlog('Socket closed..', Ansi.LIGHT_GREEN)

    def handle_connection(self, conn: socket.socket) -> None:
        start_time = time()
        data = conn.recv(config.max_bytes)
        while len(data) % config.max_bytes == 0:
            data += conn.recv(config.max_bytes)

        req = Request(data)

        if 'User-Agent' not in req.headers \
        or req.headers['User-Agent'] != 'osu!':
            return

        ps = packets.PacketStream()

        if 'osu-token' not in req.headers:
            ps._data, token = events.login(req.body)
            ps.add_header(f'cho-token: {token}')
        elif not (p := glob.players.get(req.headers['osu-token'])):
            # A little bit suboptimal, but fine for now?
            printlog('Token not found, forcing relog.')
            ps += packets.notification('Server is restarting.')
            ps += packets.restartServer(0) # send 0ms since the server is already up!
        else: # Player found, process normal packet.
            pr = packets.PacketReader(req.body)
            while not pr.empty(): # iterate thru available packets
                pr.read_packet_header()
                if pr.packetID == -1:
                    continue # skip, data empty?

                if pr.packetID not in self.packet_map:
                    printlog(f'Unhandled: {pr!r}', Ansi.LIGHT_YELLOW)
                    pr.ignore_packet()
                    continue

                self.packet_map[pr.packetID](p, pr)

            while not p.queue_empty():
                # Read all queued packets into stream
                ps += p.dequeue()

        # Even if the packet is empty, we have to
        # send back an empty response so the client
        # knows it was successfully delivered.
        conn.send(bytes(ps))
        taken = (time() - start_time) * 1000
        printlog(f'Packet took {taken:.2f}ms', Ansi.LIGHT_CYAN)

if __name__ == '__main__':
    serv = Server(host = '127.0.0.1', port = 5001)
