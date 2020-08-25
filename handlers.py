import packets
import aiofiles
import os

from cmyui.web import AsyncConnection, HTTPStatus
from urllib.parse import unquote

from objects import glob

from console import *

# NOTE: these also load the handler
# maps for each of the event categories.
from events import web, api, bancho

__all__ = (
    'handle_bancho',
    'handle_web',
    'handle_ss',
    'handle_dl',
    'handle_api',
    'handle_avatar',
    #'registration'
)

async def handle_bancho(conn: AsyncConnection) -> None:
    if 'User-Agent' not in conn.req.headers:
        return

    if conn.req.headers['User-Agent'] != 'osu!':
        # Most likely a request from a browser.
        await conn.resp.send(b'<!DOCTYPE html>' + '<br>'.join((
            f'Running gulag v{glob.version}',
            f'Players online: {len(glob.players) - 1}',
            '<a href="https://github.com/cmyui/gulag">Source code</a>',
            '',
            '<b>Bancho Handlers</b>',
            '<br>'.join(f'{int(x)}: {str(x)[9:]}' for x in glob.bancho_map.keys()),
            '',
            '<b>/web/ Handlers</b>',
            '<br>'.join(glob.web_map.keys())
        )).encode(), HTTPStatus.Ok)
        return

    resp = bytearray()

    if 'osu-token' not in conn.req.headers:
        # Login is a bit of a special case,
        # so we'll handle it separately.
        login_data = await bancho.login(conn.req.body,
                                        conn.req.headers['X-Real-IP'])

        resp.extend(login_data[0])
        await conn.resp.add_header(f'cho-token: {login_data[1]}')

    elif not (p := glob.players.get(conn.req.headers['osu-token'])):
        await plog('Token not found, forcing relog.')
        resp.extend(
            await packets.notification('Server is restarting.') +
            await packets.restartServer(0) # send 0ms since the server is already up!
        )

    else: # Player found, process normal packet.
        pr = packets.PacketReader(conn.req.body)

        # Bancho connections can send multiple packets at a time.
        # Iter through packets received and them handle indivudally.
        while not pr.empty():
            await pr.read_packet_header()
            if pr.packetID == -1:
                continue # skip, data empty?

            if pr.packetID in glob.bancho_map:
                # Server is able to handle the packet.
                await plog(f'Handling {pr!r}', Ansi.LIGHT_MAGENTA)
                await glob.bancho_map[pr.packetID](p, pr)
            else: # Packet reading behaviour not yet defined.
                await plog(f'Unhandled: {pr!r}', Ansi.LIGHT_YELLOW)
                pr.ignore_packet()

        while not p.queue_empty():
            # Read all queued packets into stream
            resp.extend(await p.dequeue())

    if glob.config.debug:
        await plog(bytes(resp), Ansi.LIGHT_GREEN)

    # Even if the packet is empty, we have to
    # send back an empty response so the client
    # knows it was successfully delivered.
    await conn.resp.send(bytes(resp), HTTPStatus.Ok)

async def handle_web(conn: AsyncConnection) -> None:
    handler = conn.req.path[5:] # cut off /web/

    # Connections to /web/ only send a single request
    # at a time; no need to iterate through received data.
    if handler not in glob.web_map:
        if handler.startswith('maps/'):
            await plog(f'Handling beatmap update.', Ansi.LIGHT_MAGENTA)
            # Special case for updating maps.
            if (resp := await web.updateBeatmap(conn.req)):
                await conn.resp.send(resp, HTTPStatus.Ok)
            return

        await plog(f'Unhandled: {conn.req.path}.', Ansi.YELLOW)
        return

    await plog(f'Handling {conn.req.path}', Ansi.LIGHT_MAGENTA)
    if (resp := await glob.web_map[handler](conn.req)):
        # XXX: Perhaps web handlers should return
        # a bytearray which could be cast to bytes
        # here at the end? Probably a better soln.

        if glob.config.debug:
            await plog(resp, Ansi.LIGHT_GREEN)

        await conn.resp.send(resp, HTTPStatus.Ok)

async def handle_ss(conn: AsyncConnection) -> None:
    if len(conn.req.path) != 16:
        await conn.resp.send(b'No file found!', HTTPStatus.NotFound)
        return

    path = f'screenshots/{conn.req.path[4:]}'

    if not os.path.exists(path):
        await conn.resp.send(b'No file found!', HTTPStatus.NotFound)
        return

    async with aiofiles.open(path, 'rb') as f:
        await conn.resp.send(await f.read(), HTTPStatus.Ok)

async def handle_dl(conn: AsyncConnection) -> None:
    if not all(x in conn.req.args for x in ('u', 'h', 'vv')):
        await conn.resp.send(b'Method requires authorization.', HTTPStatus.Unauthorized)
        return

    if not conn.req.path[3:].isnumeric():
        # Requested set id is not a number.
        return

    pname = unquote(conn.req.args['u'])
    phash = conn.req.args['h']

    if not (p := await glob.players.get_login(pname, phash)):
        return

    set_id = int(conn.req.path[3:])

    if os.path.exists(filepath := f'mapsets/{set_id}.osz'):
        async with aiofiles.open(filepath, 'rb') as f:
            content = await f.read()
    else:
        # Map not cached, get from a mirror
        # XXX: I'm considering handling this myself, aswell..
        async with glob.http.get(f'https://osu.gatari.pw/d/{set_id}') as resp:
            if not resp or resp.status != 200:
                return

            content = await resp.read()

        # Save to disk.
        async with aiofiles.open(filepath, 'wb+') as f:
            await f.write(content)

    await conn.resp.send(content, HTTPStatus.Ok)

async def handle_avatar(conn: AsyncConnection) -> None:
    pid = conn.req.path[1:]
    found = pid.isnumeric() and os.path.exists(f'avatars/{pid}')
    path = f"avatars/{pid if found else 'default'}.jpg"

    async with aiofiles.open(path, 'rb') as f:
        await conn.resp.send(await f.read(), HTTPStatus.Ok)

async def handle_api(conn: AsyncConnection) -> None:
    handler = conn.req.path[5:] # cut off /api/

    if handler not in glob.api_map:
        await plog(f'Unhandled: {conn.req.path}.', Ansi.YELLOW)
        return

    await plog(f'Handling {conn.req.path}', Ansi.LIGHT_MAGENTA)
    if (resp := await glob.api_map[handler](conn.req)):
        if glob.config.debug:
            await plog(resp, Ansi.LIGHT_GREEN)

        await conn.resp.send(resp, HTTPStatus.Ok)

# XXX: This won't be completed for a while most likely..
# Focused on other parts of the design (web mostly).
# username_regex = re_comp(r'^[\w \[\]-]{2,15}$')
# email_regex = re_comp(r'^[\w\.\+\-]+@[\w\-]+\.[\w\-\.]+$')
#async def registration(data: bytes) -> None:
#    split = [i for i in data.decode().split('--') if i]
#    headers = split[0]
#    name, email, password = [i.split('\r\n')[3] for i in split[2:5]]
#    # peppy sends password as plaintext..?
#
#    if len(password) not in range(8, 33):
#        return await plog('Registration: password does not meet length reqs.')
#
#    if not re_match(username_regex, name):
#        return await plog('Registration: name did not match regex.', Ansi.YELLOW)
#
#    if not re_match(email_regex, email) or len(email) > 254: # TODO: add len checks to regex
#        return await plog('Registration: email did not match regex.', Ansi.YELLOW)
#
#    name_safe = Player.ensure_safe(name)
#
#    if await glob.db.fetch('SELECT 1 FROM users WHERE name_safe = %s', [name_safe]):
#        return await plog(f'Registration: user {name} already exists.', Ansi.YELLOW)
#
#    user_id = await glob.db.execute(
#        'INSERT INTO users '
#        '(name, name_safe, email, priv, pw_hash) ' # TODO: country
#        'VALUES (%s, %s, %s, %s, %s)', [
#            name,
#            name_safe,
#            email,
#            int(Privileges.Normal),
#            hashpw(md5(password.encode()).hexdigest().encode(), gensalt()).decode()
#        ])
#
#    await glob.db.execute('INSERT INTO stats (id) VALUES (%s)', [user_id])
#    await plog(f'Registration: <name: {name} | id: {user_id}>.', Ansi.GREEN)
