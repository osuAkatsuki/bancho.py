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

# a list of packetids that gulag
# will refuse to reply to more
# than once per connection.
deny_doublereply = frozenset({
    85
})

async def handle_bancho(conn: AsyncConnection) -> None:
    """Handle a bancho request (c.ppy.sh/*)."""
    if 'User-Agent' not in conn.headers:
        return

    if conn.headers['User-Agent'] != 'osu!':
        # most likely a request from a browser.
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
        # login is a bit of a special case,
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

    else: # player found, process normal packet.
        pr = packets.BanchoPacketReader(conn.body)

        # gulag refuses to reply to a group of packets
        # more than once per connection. the list is
        # defined above! var: `deny_doublereply`.
        # this list will simply keep track of which
        # of these packet's we've replied to during
        # this connection to allow this functonality.
        blocked_packets = []

        # bancho connections can send multiple packets at a time.
        # iter through packets received and them handle indivudally.
        while not pr.empty():
            await pr.read_packet_header()
            if pr.packetID == -1:
                continue # skip, data empty?

            if pr.packetID in deny_doublereply:
                # this is a connection we should
                # only allow once per connection.

                if pr.packetID in blocked_packets:
                    # this packet has already been
                    # replied to in this connection.
                    pr.ignore_packet()
                    continue

                # log that the packet was handled.
                blocked_packets.append(pr.packetID)

            if pr.packetID in glob.bancho_map:
                # Server is able to handle the packet.
                await plog(repr(pr), Ansi.LIGHT_MAGENTA)
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

    # compress with gzip if enabled.
    if glob.config.gzip['web'] > 0:
        resp = gzip.compress(resp, glob.config.gzip['web'])
        await conn.add_resp_header('Content-Encoding: gzip')

    # add headers and such
    await conn.add_resp_header('Content-Type: text/html; charset=UTF-8')
    #await conn.add_resp_header('Connection: keep-alive')

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
        await plog(conn.path, Ansi.LIGHT_MAGENTA)

        # call our handler with the connection obj.
        if resp := await glob.web_map[handler](conn):
            # there's data to send back, compress & log.
            if glob.config.debug:
                await plog(resp, Ansi.LIGHT_GREEN)

            # gzip if enabled.
            if glob.config.gzip['web'] > 0:
                resp = gzip.compress(resp, glob.config.gzip['web'])
                await conn.add_resp_header('Content-Encoding: gzip')

        # attach headers & send response.
        await conn.add_resp_header('Content-Type: text/html; charset=UTF-8')
        #await conn.add_resp_header('Connection: keep-alive')

        await conn.send(200, resp if resp else b'')

    elif handler.startswith('maps/'):
        # this connection is a map update request.
        await plog(f'Beatmap update request.', Ansi.LIGHT_MAGENTA)

        if resp := await web.updateBeatmap(conn):
            # map found, send back the data.
            await conn.send(200, resp)

    else:
        # we don't have a handler for this connection.
        await plog(f'Unhandled: {conn.path}.', Ansi.YELLOW)

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
    """Handle a map download request (osu.ppy.sh/dl/*)."""
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
    # which gulag will save into a file.. we'll need a var in
    # the db to store whether a map has been disabled, i guess.

    if glob.config.mirror_cache: # cache maps from the mirror on disk.
        if os.path.exists(filepath := f'.data/osz/{set_id}.osz'):
            # we have the map in cache.
            async with aiofiles.open(filepath, 'rb') as f:
                content = await f.read()

        else: # get the map for our mirror & client.
            bmap_url = f'{glob.config.mirror}/d/{set_id}'
            async with glob.http.get(bmap_url) as resp:
                if not resp or resp.status != 200:
                    return

                content = await resp.read()

            # save to disk.
            async with aiofiles.open(filepath, 'wb') as f:
                await f.write(content)

        await conn.send(200, content)

    else: # don't use gulag as a mirror, just reflect another.
        bmap_url = f'{glob.config.mirror}/d/{set_id}'
        await conn.add_resp_header(f'Location: {bmap_url}')
        await conn.send(302, None)

default_avatar = f'.data/avatars/default.jpg'
async def handle_avatar(conn: AsyncConnection) -> None:
    """Handle an avatar request (a.ppy.sh/*)."""
    _path = f'.data/avatars/{conn.path[1:]}.jpg'
    path = (os.path.exists(_path) and _path) or default_avatar

    async with aiofiles.open(path, 'rb') as f:
        await conn.send(200, await f.read())

async def handle_api(conn: AsyncConnection) -> None:
    """Handle an api request (osu.ppy.sh/api/*)."""
    handler = conn.path[5:] # cut off /api/

    if handler in glob.api_map:
        await plog(conn.path, Ansi.LIGHT_MAGENTA)

        if resp := await glob.api_map[handler](conn):
            # we have data to send back to the client.
            if glob.config.debug:
                await plog(resp, Ansi.LIGHT_GREEN)

            await conn.send(200, resp)

    else: # handler not found.
        await plog(f'Unhandled: {conn.path}.', Ansi.YELLOW)
