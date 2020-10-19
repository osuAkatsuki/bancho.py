# -*- coding: utf-8 -*-

from struct import pack
import time
import packets
import aiofiles
import orjson
import os
import gzip
import hashlib, bcrypt
from collections import defaultdict

from cmyui import AsyncConnection, log, Ansi

from objects import glob
from constants import regexes

# NOTE: these also load the handler
# maps for each of the event categories.
from events import web, api, bancho
from packets import BanchoPacketReader, ClientPacketType

__all__ = (
    'handle_bancho',
    'handle_web',
    'handle_ss',
    'handle_dl',
    'handle_api',
    'handle_avatar',
    'handle_registration'
)

# a list of packetids that gulag
# will refuse to reply to more
# than once per connection.
deny_doublereply = frozenset({
    ClientPacketType.USER_STATS_REQUEST
})

async def handle_bancho(conn: AsyncConnection) -> None:
    """Handle a bancho request (POST c.ppy.sh/)."""
    if 'User-Agent' not in conn.headers:
        return

    if conn.headers['User-Agent'] != 'osu!':
        # most likely a request from a browser.
        resp = '<br>'.join((
            f'Running gulag v{glob.version}',
            f'Players online: {len(glob.players) - 1}',
            '<a href="https://github.com/cmyui/gulag">Source code</a>',
            '',
            '<b>Bancho Handlers</b>',
            '<br>'.join(f'{h.name} ({h.value})' for h in glob.bancho_map),
            '',
            '<b>/web/ Handlers</b>',
            '<br>'.join(glob.web_map),
            '',
            '<b>/api/ Handlers</b>',
            '<br>'.join(glob.api_map)
        ))

        await conn.send(200, f'<!DOCTYPE html>{resp}'.encode())
        return

    # check for 'osu-token' in the headers.
    # if it's not there, this is a login request.

    if 'osu-token' not in conn.headers:
        # login is a bit of a special case,
        # so we'll handle it separately.
        resp, token = await bancho.login(
            conn.body, conn.headers['X-Real-IP']
        )

        await conn.add_resp_header(f'cho-token: {token}')
        await conn.send(200, resp)
        return

    # get the player from the specified osu token.
    p = glob.players.get(conn.headers['osu-token'])

    if not p:
        # token was not found; changes are, we just restarted
        # the server. just tell their client to re-connect.
        resp = packets.notification('Server is restarting') + \
               packets.restartServer(0) # send 0ms since server is up

        await conn.send(200, resp)
        return

    """
    # gulag refuses to reply to a group of packets more than once per
    # connection. the list is defined above! var: `deny_doublereply`.
    # this list will simply keep track of which of these packets we've
    # replied to during this connection to allow this functonality.
    blocked_packets: list[ClientPacketType] = []
    """

    # bancho connections can be comprised of multiple packets;
    # our reader is designed to iterate through them individually,
    # allowing logic to be implemented around the actual handler.
    packet_reader = BanchoPacketReader(conn.body)

    # NOTE: this will internally discard any
    # packets whose logic has not been defined.
    async for packet in packet_reader:
        # call our packet's handler
        await packet.handle(p)

        if glob.config.debug:
            log(repr(packet.type), Ansi.LMAGENTA)


    """
    # bancho connections can send multiple packets at a time.
    # iter through packets received and them handle indivudally.
    while not pr.empty():
        await pr.read_packet_header()
        if pr.current_packet is None:
            continue # skip, packet empty or corrupt?

        if pr.current_packet == ClientPacketType.PING:
            continue

        if pr.current_packet in deny_doublereply:
            # this is a connection we should
            # only allow once per connection.

            if pr.current_packet in blocked_packets:
                # this packet has already been
                # replied to in this connection.
                pr.ignore_packet()
                continue

            # log that the packet was handled.
            blocked_packets.append(pr.current_packet)

        if pr.current_packet in glob.bancho_map:
            # Server is able to handle the packet.
            if glob.config.debug:
                log(repr(pr.current_packet), Ansi.LMAGENTA)

            await glob.bancho_map[pr.current_packet](p, pr)

        else:
            # packet reading behaviour not yet defined.
            log(f'Unhandled: {pr!r}', Ansi.LYELLOW)
            pr.ignore_packet()
    """

    p.last_recv_time = int(time.time())

    # TODO: this could probably be done better?
    resp = bytearray()

    while not p.queue_empty():
        # read all queued packets into stream
        resp.extend(p.dequeue())

    resp = bytes(resp)

    # compress with gzip if enabled.
    if glob.config.gzip['web'] > 0:
        resp = gzip.compress(resp, glob.config.gzip['web'])
        await conn.add_resp_header('Content-Encoding: gzip')

    # add headers and such
    await conn.add_resp_header('Content-Type: text/html; charset=UTF-8')

    # even if the packet is empty, we have to
    # send back an empty response so the client
    # knows it was successfully delivered.
    await conn.send(200, resp)

# XXX: perhaps (web) handlers should return
# a bytearray which could be cast to bytes
# here at the end? probably a better soln.

async def handle_web(conn: AsyncConnection) -> None:
    """Handle a web request (osu.ppy.sh/web/*)."""
    handler = conn.path[5:] # cut off /web/

    if handler in glob.web_map:
        # we have a handler for this connection.
        if glob.config.debug:
            log(conn.path, Ansi.LMAGENTA)

        # call our handler with the connection obj.
        if resp := await glob.web_map[handler](conn):
            # we have data to send back.
            # compress if enabled for web.

            # gzip if enabled.
            if glob.config.gzip['web'] > 0:
                resp = gzip.compress(resp, glob.config.gzip['web'])
                await conn.add_resp_header('Content-Encoding: gzip')

        # attach headers & send response.
        await conn.add_resp_header('Content-Type: text/html; charset=UTF-8')

        await conn.send(200, resp or b'')

    elif handler.startswith('maps/'):
        # this connection is a map update request.
        if glob.config.debug:
            log(f'Beatmap update request.', Ansi.LMAGENTA)

        if resp := await web.updateBeatmap(conn):
            # map found, send back the data.
            await conn.send(200, resp)

    else:
        # we don't have a handler for this connection.
        log(f'Unhandled: {conn.path}.', Ansi.YELLOW)

async def handle_ss(conn: AsyncConnection) -> None:
    """Handle a screenshot request (osu.ppy.sh/ss/*)."""
    if len(conn.path) != 16:
        await conn.send(404, b'No file found!')
        return

    path = f'.data/ss/{conn.path[4:]}'

    if not os.path.exists(path):
        await conn.send(404, b'No file found!')
        return

    async with aiofiles.open(path, 'rb') as f:
        await conn.send(200, await f.read())

async def handle_dl(conn: AsyncConnection) -> None:
    """Handle a map download request (osu.ppy.sh/d/*)."""
    if not (set_id := conn.path[3:]).isdecimal():
        # requested set id is not a number.
        return

    # redirect to our mirror
    mirror_url = f'{glob.config.mirror}/d/{set_id}'
    await conn.add_resp_header(f'Location: {mirror_url}')
    await conn.send(302, None)

default_avatar = f'.data/avatars/default.jpg'
async def handle_avatar(conn: AsyncConnection) -> None:
    """Handle an avatar request (a.ppy.sh/*)."""
    _path = f'.data/avatars/{conn.path[1:]}.jpg'
    path = (os.path.exists(_path) and _path) or default_avatar

    async with aiofiles.open(path, 'rb') as f:
        await conn.send(200, await f.read())

async def handle_registration(conn: AsyncConnection) -> None:
    mp_args = conn.multipart_args

    name = mp_args['user[username]']
    email = mp_args['user[user_email]']
    pw_txt = mp_args['user[password]']

    if not all((name, email, pw_txt)) or 'check' not in mp_args:
        return # missing required params.

    # ensure all args passed
    # are safe for registration.
    errors = defaultdict(list)

    # Usernames must:
    # - be within 2-15 characters in length
    # - not contain both ' ' and '_', one is fine
    # - not be in the config's `disallowed_names` list
    # - not already be taken by another player
    if not regexes.username.match(name):
        errors['username'].append('Must be 2-15 characters in length.')

    if '_' in name and ' ' in name:
        errors['username'].append('May contain "_" and " ", but not both.')

    if name in glob.config.disallowed_names:
        errors['username'].append('Disallowed username; pick another.')

    if await glob.db.fetch('SELECT 1 FROM users WHERE name = %s', name):
        errors['username'].append('Username already taken by another player.')

    # Emails must:
    # - match the regex `^[^@\s]{1,200}@[^@\s\.]{1,30}\.[^@\.\s]{1,24}$`
    # - not already be taken by another player
    if not regexes.email.match(email):
        errors['user_email'].append('Invalid email syntax.')

    if await glob.db.fetch('SELECT 1 FROM users WHERE email = %s', email):
        errors['user_email'].append('Email already taken by another player.')

    # Passwords must:
    # - be within 8-32 characters in length
    # - have more than 3 unique characters
    # - not be in the config's `disallowed_passwords` list
    if 8 > len(pw_txt) < 32:
        errors['password'].append('Must be 8-32 characters in length.')

    if len(set(pw_txt)) <= 3:
        errors['password'].append('Must have more than 3 unique characters.')

    if pw_txt.lower() in glob.config.disallowed_passwords:
        errors['password'].append('That password was deemed too simple.')

    if errors:
        # we have errors to send back.
        errors_full = {'form_error': {'user': errors}}
        return await conn.send(400, orjson.dumps(errors_full))

    if mp_args['check'] == '0':
        # the client isn't just checking values,
        # they want to register the account now.

        # make the md5 & bcrypt the md5 for sql.
        pw_md5 = hashlib.md5(pw_txt.encode()).hexdigest().encode()
        pw_bcrypt = bcrypt.hashpw(pw_md5, bcrypt.gensalt()).decode()
        glob.cache['bcrypt'][pw_md5] = pw_bcrypt # cache result for login

        safe_name = name.lower().replace(' ', '_')

        # add to `users` table.
        user_id = await glob.db.execute(
            'INSERT INTO users '
            '(name, name_safe, email, pw_hash, creation_time) '
            'VALUES (%s, %s, %s, %s, NOW())',
            [name, safe_name, email, pw_bcrypt]
        )

        # add to `stats` table.
        await glob.db.execute(
            'INSERT INTO stats '
            '(id) VALUES (%s)',
            [user_id]
        )

        log(f'<{name} ({user_id})> has registered!', Ansi.LGREEN)

    await conn.send(200, b'ok') # success

async def handle_api(conn: AsyncConnection) -> None:
    """Handle an api request (osu.ppy.sh/api/*)."""
    handler = conn.path[5:] # cut off /api/

    if handler in glob.api_map:
        if glob.config.debug:
            log(conn.path, Ansi.LMAGENTA)

        if resp := await glob.api_map[handler](conn):
            # we have data to send back to the client.
            if glob.config.debug:
                log(resp, Ansi.LGREEN)

            await conn.send(200, resp)

    else:
        # handler not found.
        log(f'Unhandled: {conn.path}.', Ansi.YELLOW)
