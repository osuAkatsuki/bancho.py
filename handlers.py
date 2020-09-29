import packets
import aiofiles
import os
import gzip

from cmyui import AsyncConnection
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
    if 'User-Agent' not in conn.headers:
        return

    if conn.headers['User-Agent'] != 'osu!':
        # Most likely a request from a browser.
        await conn.send(200, b'<!DOCTYPE html>' + '<br>'.join((
            f'Running gulag v{glob.version}',
            f'Players online: {len(glob.players) - 1}',
            '<a href="https://github.com/cmyui/gulag">Source code</a>',
            '',
            '<b>Bancho Handlers</b>',
            '<br>'.join(f'{int(k)}: {str(k)[9:]}' for k in glob.bancho_map),
            '',
            '<b>/web/ Handlers</b>',
            '<br>'.join(glob.web_map)
        )).encode())
        return

    resp = bytearray()

    if 'osu-token' not in conn.headers:
        # Login is a bit of a special case,
        # so we'll handle it separately.
        login_data = await bancho.login(conn.body,
                                        conn.headers['X-Real-IP'])

        resp.extend(login_data[0])
        await conn.add_resp_header(f'cho-token: {login_data[1]}')

    elif not (p := glob.players.get(conn.headers['osu-token'])):
        await plog('Token not found, forcing relog.')
        resp.extend(
            await packets.notification('Server is restarting.') +
            await packets.restartServer(0) # send 0ms since the server is already up!
        )

    else: # Player found, process normal packet.
        pr = packets.PacketReader(conn.body)

        # keep track of the packetIDs we've already handled, the osu
        # client will stack many packets of the same type into one
        # connection (200iq design), theres no point double replying.
        packets_handled = []

        # Bancho connections can send multiple packets at a time.
        # Iter through packets received and them handle indivudally.
        while not pr.empty():
            await pr.read_packet_header()
            if pr.packetID == -1:
                continue # skip, data empty?

            if pr.packetID in packets_handled:
                # we've already handled a packet of
                # this type during this connection.
                pr.ignore_packet()
                continue

            packets_handled.append(pr.packetID)

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

    resp = bytes(resp)

    if glob.config.debug:
        await plog(resp, Ansi.LIGHT_GREEN)

    # Compress with gzip if enabled.
    if glob.config.gzip['web'] > 0:
        resp = gzip.compress(resp, glob.config.gzip['web'])
        await conn.add_resp_header('Content-Encoding: gzip')

    # Add headers and such
    await conn.add_resp_header('Content-Type: text/html; charset=UTF-8')
    #await conn.add_resp_header('Connection: keep-alive')

    # Even if the packet is empty, we have to
    # send back an empty response so the client
    # knows it was successfully delivered.
    await conn.send(200, resp)

# XXX: perhaps (web) handlers should return
# a bytearray which could be cast to bytes
# here at the end? Probably a better soln.

async def handle_web(conn: AsyncConnection) -> None:
    handler = conn.path[5:] # cut off /web/

    if handler in glob.web_map:
        await plog(f'Handling {conn.path}', Ansi.LIGHT_MAGENTA)

        if resp := await glob.web_map[handler](conn):
            # We have data to send back to the client.
            if glob.config.debug:
                await plog(resp, Ansi.LIGHT_GREEN)

            # Compress with gzip if enabled.
            if glob.config.gzip['web'] > 0:
                resp = gzip.compress(resp, glob.config.gzip['web'])
                await conn.add_resp_header('Content-Encoding: gzip')

            # Add headers and such
            await conn.add_resp_header('Content-Type: text/html; charset=UTF-8')
            #await conn.add_resp_header('Connection: keep-alive')

            await conn.send(200, resp)

    elif handler.startswith('maps/'):
        await plog(f'Handling map update.', Ansi.LIGHT_MAGENTA)

        # Special case for updating maps.
        if resp := await web.updateBeatmap(conn):
            # Map found, send back the data.
            await conn.send(200, resp)

    else: # Handler not found
        await plog(f'Unhandled: {conn.path}.', Ansi.YELLOW)

async def handle_ss(conn: AsyncConnection) -> None:
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
    if not all(x in conn.args for x in ('u', 'h', 'vv')):
        await conn.send(401, b'Method requires authorization.')
        return

    if not conn.path[3:].isdecimal():
        # Requested set id is not a number.
        return

    pname = unquote(conn.args['u'])
    phash = conn.args['h']

    if not (p := await glob.players.get_login(pname, phash)):
        return

    set_id = int(conn.path[3:])

    # TODO: at the moment, if a map's dl is disabled on osu it
    # will send back 'This download has been disabled by peppy',
    # which gulag will save into a file.. We'll need a var in
    # the db to store whether a map has been disabled, i guess.

    if glob.config.mirror: # Use gulag as a mirror (cache maps on disk).
        if os.path.exists(filepath := f'.data/osz/{set_id}.osz'):
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

        await conn.send(200, content)

    else: # Don't use gulag as a mirror, just reflect another.
        bmap_url = f'{glob.config.external_mirror}/d/{set_id}'
        await conn.add_resp_header(f'Location: {bmap_url}')
        await conn.send(302, None)

async def handle_avatar(conn: AsyncConnection) -> None:
    pid = conn.path[1:]
    found = pid.isdecimal() and os.path.exists(f'avatars/{pid}')
    path = f"avatars/{pid if found else 'default'}.jpg"

    async with aiofiles.open(path, 'rb') as f:
        await conn.send(200, await f.read())

async def handle_api(conn: AsyncConnection) -> None:
    handler = conn.path[5:] # cut off /api/

    if handler in glob.api_map:
        await plog(f'Handling {conn.path}', Ansi.LIGHT_MAGENTA)

        if resp := await glob.api_map[handler](conn):
            # We have data to send back to the client.
            if glob.config.debug:
                await plog(resp, Ansi.LIGHT_GREEN)

            await conn.send(200, resp)

    else: # Handler not found.
        await plog(f'Unhandled: {conn.path}.', Ansi.YELLOW)
