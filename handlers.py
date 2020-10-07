import packets
import aiofiles
import os
import gzip

from cmyui import AsyncConnection

from objects import glob

from console import *

# NOTE: these also load the handler
# maps for each of the event categories.
from events import web, api, bancho
from packets import BanchoPacket

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
    BanchoPacket.c_userStatsRequest
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
            '<br>'.join(f'{h.name} ({h.value})' for h in glob.bancho_map),
            '',
            '<b>/web/ Handlers</b>',
            '<br>'.join(glob.web_map),
            '',
            '<b>/api/ Handlers</b>',
            '<br>'.join(glob.api_map)
        )).encode())
        return

    resp = bytearray()

    if 'osu-token' not in conn.headers:
        # login is a bit of a special case,
        # so we'll handle it separately.
        login_data = await bancho.login(
            conn.body, conn.headers['X-Real-IP']
        )

        resp.extend(login_data[0])
        await conn.add_resp_header(f'cho-token: {login_data[1]}')

    elif not (p := glob.players.get(conn.headers['osu-token'])):
        #plog('Token not found, forcing relog.')
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
        blocked_packets: list[BanchoPacket] = []

        # bancho connections can send multiple packets at a time.
        # iter through packets received and them handle indivudally.
        while not pr.empty():
            await pr.read_packet_header()
            if pr.current_packet is None:
                continue # skip, packet empty or corrupt?

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
                    plog(repr(pr.current_packet), Ansi.LMAGENTA)

                await glob.bancho_map[pr.current_packet](p, pr)
            else: # Packet reading behaviour not yet defined.
                plog(f'Unhandled: {pr!r}', Ansi.LYELLOW)
                pr.ignore_packet()

        while not p.queue_empty():
            # Read all queued packets into stream
            resp.extend(await p.dequeue())

    resp = bytes(resp)

    if glob.config.debug:
        plog(resp, Ansi.LGREEN)

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
        if glob.config.debug:
            plog(conn.path, Ansi.LMAGENTA)

        # call our handler with the connection obj.
        if resp := await glob.web_map[handler](conn):
            # there's data to send back, compress & log.
            if glob.config.debug:
                plog(f'Response: {resp}', Ansi.LGREEN)

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
        if glob.config.debug:
            plog(f'Beatmap update request.', Ansi.LMAGENTA)

        if resp := await web.updateBeatmap(conn):
            # map found, send back the data.
            await conn.send(200, resp)

    else:
        # we don't have a handler for this connection.
        plog(f'Unhandled: {conn.path}.', Ansi.YELLOW)

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

async def handle_api(conn: AsyncConnection) -> None:
    """Handle an api request (osu.ppy.sh/api/*)."""
    handler = conn.path[5:] # cut off /api/

    if handler in glob.api_map:
        if glob.config.debug:
            plog(conn.path, Ansi.LMAGENTA)

        if resp := await glob.api_map[handler](conn):
            # we have data to send back to the client.
            if glob.config.debug:
                plog(resp, Ansi.LGREEN)

            await conn.send(200, resp)

    else: # handler not found.
        plog(f'Unhandled: {conn.path}.', Ansi.YELLOW)
