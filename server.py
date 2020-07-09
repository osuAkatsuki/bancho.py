# -*- coding: utf-8 -*-

# 51.161.34.235

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
from bcrypt import hashpw, gensalt
from hashlib import md5
from re import compile as re_comp, match as re_match

from db.dbConnector import SQLPool

import packets
from console import *

from objects import glob
from events import events
from objects.player import Player
from objects.collections import PlayerList, ChannelList
from objects.channel import Channel
from objects.web import Request#, Response
from constants.types import osuTypes
from constants.privileges import Privileges

username_regex = re_comp(r'^[\w \[\]-]{2,15}$')
email_regex = re_comp(r'^[\w\.\+\-]+@[\w\-]+\.[\w\-\.]+$')

class Server:
    def __init__(self, *args, **kwargs) -> None:
        self.run_time = time()
        self.shutdown = False # used to break loop lol

        glob.version = 1.0 # server version
        glob.db = SQLPool(pool_size = 4, config = glob.config.mysql)

        # Aika
        glob.bot = Player(id = 1, name = 'Aika', priv = Privileges.Admin)
        glob.bot.ping_time = 0x7fffffff

        glob.bot.stats_from_sql_full() # no need to get friends
        glob.players.add(glob.bot)

        # Default channels.
        # At some point, this will either be moved
        # to db, or possibly just configration.
        glob.channels.add(Channel(
            name = '#osu',
            topic = 'Gaming  with the GULAG!',
            read = Privileges.Verified,
            write = Privileges.Verified,
            auto_join = True))
        glob.channels.add(Channel(
            name = '#announce',
            topic = 'may you see them',
            read = Privileges.Verified,
            write = Privileges.Admin,
            auto_join = True))
        glob.channels.add(Channel(
            name = '#lobby',
            topic = 'Multiplayer lobby chat.',
            read = Privileges.Verified,
            write = Privileges.Verified,
            auto_join = False))

        self.packet_map = {
            # 0: Client changed action
            packets.Packet.c_changeAction: events.readStatus,
            # 1: Client sends a message
            packets.Packet.c_sendPublicMessage: events.sendMessage,
            # 2: Client logged out.
            packets.Packet.c_logout: events.logout,
            # 3: Client wishes their stats updated
            packets.Packet.c_requestStatusUpdate: events.statsUpdateRequest,
            # 4: Client wishes their ping time updated.
            packets.Packet.c_ping: events.ping,
            # 16. Client started spectating another user.
            packets.Packet.c_startSpectating: events.startSpectating,
            # 17: Client stopped spectating another user.
            packets.Packet.c_stopSpectating: events.stopSpectating,
            # 18: Client is sending spectator frames for server to distribute to spectators.
            packets.Packet.c_spectateFrames: events.spectateFrames,
            # 21: Client wishes to inform fellow spectators that he cannot spectate.
            packets.Packet.c_cantSpectate: events.cantSpectate,
            # 25: Client sends a private message.
            packets.Packet.c_sendPrivateMessage: events.sendPrivateMessage,
            # 29: Client has left the multiplayer lobby.
            packets.Packet.c_partLobby: events.lobbyPart,
            # 30: Client has joined the multiplayer lobby.
            packets.Packet.c_joinLobby: events.lobbyJoin,
            # 31: Client creates a multiplayer match.
            packets.Packet.c_createMatch: events.matchCreate,
            # 32: Client wishes to join a multiplayer match.
            packets.Packet.c_joinMatch: events.matchJoin,
            # 33: Client wishes to leave a multiplayer match.
            packets.Packet.c_partMatch: events.matchPart,
            # 38: Client wishes to change their slot in multiplayer.
            packets.Packet.c_matchChangeSlot: events.matchChangeSlot,
            # 39: Client wishes to ready up in multiplayer.
            packets.Packet.c_matchReady: events.matchReady,
            # 40: Client wishes to lock the multiplayer game.
            packets.Packet.c_matchLock: events.matchLock,
            # 41: Client wishes to update a multiplayer match.
            packets.Packet.c_matchChangeSettings: events.matchChangeSettings,
            # 44: Client wishes to start the multiplayer match.
            packets.Packet.c_matchStart: events.matchStart,
            # 47: Client sends new score data to distribute to others match mates.
            packets.Packet.c_matchScoreUpdate: events.matchScoreUpdate,
            # 48: Client sends a new scoreframe in multiplayer.
            packets.Packet.c_matchScoreUpdate: events.matchScoreUpdate,
            # 49: Client wishes to inform bancho they're finished their play in multiplayer.
            packets.Packet.c_matchComplete: events.matchComplete,
            # 51: Client wishes to change mods in multiplayer.
            packets.Packet.c_matchChangeMods: events.matchChangeMods,
            # 52: Client wishes to inform bancho that it's completed loading
            packets.Packet.c_matchLoadComplete: events.matchLoadComplete,
            # 55: Client wishes to unready in multiplayer.
            packets.Packet.c_matchNotReady: events.matchNotReady,
            # 60: Client wishes to skip the current map's intro in multiplayer.
            packets.Packet.c_matchSkipRequest: events.matchSkipRequest,
            # 63: Client joined a channel.
            packets.Packet.c_channelJoin: events.channelJoin,
            # 70: Client wishes to transfer host to another player.
            packets.Packet.c_matchTransferHost: events.matchTransferHost,
            # 73: Client added someone to their friends.
            packets.Packet.c_friendAdd: events.friendAdd,
            # 74: Client added someone from their friends.
            packets.Packet.c_friendRemove: events.friendRemove,
            # 77: Client changed their team in multiplayer.
            packets.Packet.c_matchChangeTeam: events.matchChangeTeam,
            # 78: Client left a channel.
            packets.Packet.c_channelPart: events.channelPart,
            # 82: Client wishes to update their away message.
            packets.Packet.c_setAwayMessage: events.setAwayMessage,
            # 85: Client wishes everyones stats.
            packets.Packet.c_userStatsRequest: events.statsRequest,
            # 87: Client is inviting another player to their multiplayer match.
            packets.Packet.c_invite: events.matchInvite,
            # 97: Client wishes presence of specific users.
            packets.Packet.c_userPresenceRequest: events.userPresenceRequest,
            # 100: Client would like to block dms from non-friends.
            packets.Packet.c_userToggleBlockNonFriendPM: events.toggleBlockingDMs,
        }

        self.start(glob.config.concurrent) # starts server

    def ping_timeouts(self) -> None:
        while not self.shutdown:
            current_time = int(time())
            for p in glob.players:
                if (p.ping_time + glob.config.max_ping) < current_time:
                    printlog(f'Timing out {p}.', Ansi.YELLOW)
                    p.logout()

            sleep(glob.config.max_ping)

    def start(self, connections: int = 10) -> None:
        if path.exists(glob.config.sock_file):
            remove(glob.config.sock_file)

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.bind(glob.config.sock_file)
            chmod(glob.config.sock_file, 0o777)
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

    @staticmethod
    def registration(data: bytes) -> None:
        split = [i for i in data.decode().split('--') if i]
        headers = split[0]
        name, email, password = [i.split('\r\n')[3] for i in split[2:5]]
        # peppy sends password as plaintext..?

        if len(password) not in range(8, 33):
            return printlog('Registration: password does not meet length reqs.')

        if not re_match(username_regex, name):
            return printlog('Registration: name did not match regex.', Ansi.YELLOW)

        if not re_match(email_regex, email) or len(email) > 254: # TODO: add len checks to regex
            return printlog('Registration: email did not match regex.', Ansi.YELLOW)

        name_safe = Player.ensure_safe(name)

        if glob.db.fetch('SELECT 1 FROM users WHERE name_safe = %s', [name_safe]):
            return printlog(f'Registration: user {name} already exists.', Ansi.YELLOW)

        user_id = glob.db.execute(
            'INSERT INTO users '
            '(name, name_safe, email, priv, pw_hash) ' # TODO: country
            'VALUES (%s, %s, %s, %s, %s)', [
                name,
                name_safe,
                email,
                int(Privileges.Verified),
                hashpw(md5(password.encode()).hexdigest().encode(), gensalt()).decode()
            ])

        glob.db.execute('INSERT INTO stats (id) VALUES (%s)', [user_id])
        printlog(f'Registration: <name: {name} | id: {user_id}>.', Ansi.GREEN)

    def handle_connection(self, conn: socket.socket) -> None:
        start_time = time()
        data = conn.recv(glob.config.max_bytes)
        while len(data) % glob.config.max_bytes == 0:
            data += conn.recv(glob.config.max_bytes)

        if data.startswith(b'POST /users'):
            # Handle ingame registrations.
            # TODO: figure out what to send back xd
            return self.registration(data)

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

                printlog(f'Handling {pr!r}')
                self.packet_map[pr.packetID](p, pr)

            while not p.queue_empty():
                # Read all queued packets into stream
                ps += p.dequeue()

        # Even if the packet is empty, we have to
        # send back an empty response so the client
        # knows it was successfully delivered.
        resp = bytes(ps)
        if glob.config.debug:
            printlog(resp, Ansi.MAGENTA)
        conn.send(resp)
        taken = (time() - start_time) * 1000
        printlog(f'Packet took {taken:.2f}ms', Ansi.LIGHT_CYAN)

if __name__ == '__main__':
    serv = Server(host = '127.0.0.1', port = 5001)
