import packets
import aiofiles
import os

from cmyui.web import AsyncConnection
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
    'handle_avatar'
)

async def handle_bancho(conn: AsyncConnection) -> None:
    if 'User-Agent' not in conn.req.headers:
        return

    if conn.req.headers['User-Agent'] != 'osu!':
        # Most likely a request from a browser.
        await conn.resp.send(200, b'<!DOCTYPE html>' + '<br>'.join((
            f'Running gulag v{glob.version}',
            f'Players online: {len(glob.players) - 1}',
            '<a href="https://github.com/cmyui/gulag">Source code</a>',
            '',
            '<b>Bancho Handlers</b>',
            '<br>'.join(f'{int(x)}: {str(x)[9:]}' for x in glob.bancho_map.keys()),
            '',
            '<b>/web/ Handlers</b>',
            '<br>'.join(glob.web_map.keys())
        )).encode())
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
    await conn.resp.send(200, bytes(resp))

# XXX: perhaps (web) handlers should return
# a bytearray which could be cast to bytes
# here at the end? Probably a better soln.

async def handle_web(conn: AsyncConnection) -> None:
    handler = conn.req.path[5:] # cut off /web/

    if handler in glob.web_map:
        await plog(f'Handling {conn.req.path}', Ansi.LIGHT_MAGENTA)

        if resp := await glob.web_map[handler](conn.req):
            # We have data to send back to the client.
            if glob.config.debug:
                await plog(resp, Ansi.LIGHT_GREEN)

            await conn.resp.send(200, resp)

    elif handler.startswith('maps/'):
        await plog(f'Handling map update.', Ansi.LIGHT_MAGENTA)

        # Special case for updating maps.
        if resp := await web.updateBeatmap(conn.req):
            # Map found, send back the data.
            await conn.resp.send(200, resp)

    else: # Handler not found
        await plog(f'Unhandled: {conn.req.path}.', Ansi.YELLOW)

async def handle_ss(conn: AsyncConnection) -> None:
    if len(conn.req.path) != 16:
        await conn.resp.send(404, b'No file found!')
        return

    path = f'screenshots/{conn.req.path[4:]}'

    if not os.path.exists(path):
        await conn.resp.send(404, b'No file found!')
        return

    async with aiofiles.open(path, 'rb') as f:
        content = await f.read()

    await conn.resp.send(200, content)

async def handle_dl(conn: AsyncConnection) -> None:
    if not all(x in conn.req.args for x in ('u', 'h', 'vv')):
        await conn.resp.send(401, b'Method requires authorization.')
        return

    if not conn.req.path[3:].isdecimal():
        # Requested set id is not a number.
        return

    pname = unquote(conn.req.args['u'])
    phash = conn.req.args['h']

    if not (p := await glob.players.get_login(pname, phash)):
        return

    set_id = int(conn.req.path[3:])

    # TODO: at the moment, if a map's dl is disabled on osu it
    # will send back 'This download has been disabled by peppy',
    # which gulag will save into a file.. We'll need a var in
    # the db to store whether a map has been disabled, i guess.

    if glob.config.mirror: # Use gulag as a mirror (cache maps on disk).
        if os.path.exists(filepath := f'mapsets/{set_id}.osz'):
            # We have the map in cache.
            async with aiofiles.open(filepath, 'rb') as f:
                content = await f.read()

        else: # Get the map for our mirror & client.
            bmap_url = f'{glob.config.external_mirror}/d/{set_id}'
            async with glob.http.get(bmap_url) as resp:
                if not resp or resp.status != 200:
                    return

                content = await resp.read()

            # Save to disk.
            async with aiofiles.open(filepath, 'wb') as f:
                await f.write(content)

        await conn.resp.send(200, content)

    else: # Don't use gulag as a mirror, just reflect another.
        bmap_url = f'{glob.config.external_mirror}/d/{set_id}'
        await conn.resp.add_header(f'Location: {bmap_url}')
        await conn.resp.send(302, None)

async def handle_avatar(conn: AsyncConnection) -> None:
    pid = conn.req.path[1:]
    found = pid.isdecimal() and os.path.exists(f'avatars/{pid}')
    path = f"avatars/{pid if found else 'default'}.jpg"

    async with aiofiles.open(path, 'rb') as f:
        content = await f.read()

    await conn.resp.send(200, content)

async def handle_api(conn: AsyncConnection) -> None:
    handler = conn.req.path[5:] # cut off /api/

    if handler in glob.api_map:
        await plog(f'Handling {conn.req.path}', Ansi.LIGHT_MAGENTA)

        if resp := await glob.api_map[handler](conn.req):
            # We have data to send back to the client.
            if glob.config.debug:
                await plog(resp, Ansi.LIGHT_GREEN)

            await conn.resp.send(200, resp)

    else: # Handler not found.
        await plog(f'Unhandled: {conn.req.path}.', Ansi.YELLOW)
