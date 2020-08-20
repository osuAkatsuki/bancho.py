import packets
from os.path import exists
from cmyui.web import Connection
from requests import get as req_get

from objects import glob

from events.bancho import login as loginEvent
from console import *

from events.web import updateBeatmap

__all__ = (
    'handle_bancho',
    'handle_web',
    'handle_ss',
    'handle_dl',
    #'registration'
)

def handle_bancho(conn: Connection) -> None:
    if 'User-Agent' not in conn.req.headers:
        return

    if conn.req.headers['User-Agent'] != 'osu!':
        # Most likely a request from a browser.
        conn.resp.send(b'<!DOCTYPE html>' + '<br>'.join((
            f'Running gulag v{glob.version}',
            f'Players online: {len(glob.players) - 1}',
            '<a href="https://github.com/cmyui/gulag">Source code</a>',
            '',
            '<b>Bancho Handlers</b>',
            '<br>'.join(f'{int(x)}: {str(x)[9:]}' for x in glob.bancho_map.keys()),
            '',
            '<b>/web/ Handlers</b>',
            '<br>'.join(glob.web_map.keys())
        )).encode(), 200)
        return

    resp = bytearray()

    if 'osu-token' not in conn.req.headers:
        # Login is a bit of a special case,
        # so we'll handle it separately.
        login_data = loginEvent(conn.req.body, conn.req.headers['X-Real-IP'])

        resp.extend(login_data[0])
        conn.resp.add_header(f'cho-token: {login_data[1]}')

    elif not (p := glob.players.get(conn.req.headers['osu-token'])):
        printlog('Token not found, forcing relog.')
        resp.extend(
            packets.notification('Server is restarting.') +
            packets.restartServer(0) # send 0ms since the server is already up!
        )

    else: # Player found, process normal packet.
        pr = packets.PacketReader(conn.req.body)

        # Bancho connections can send multiple packets at a time.
        # Iter through packets received and them handle indivudally.
        while not pr.empty():
            pr.read_packet_header()
            if pr.packetID == -1:
                continue # skip, data empty?

            if pr.packetID in glob.bancho_map:
                # Server is able to handle the packet.
                printlog(f'Handling {pr!r}', Ansi.LIGHT_MAGENTA)
                glob.bancho_map[pr.packetID](p, pr)
            else: # Packet reading behaviour not yet defined.
                printlog(f'Unhandled: {pr!r}', Ansi.LIGHT_YELLOW)
                pr.ignore_packet()

        while not p.queue_empty():
            # Read all queued packets into stream
            resp.extend(p.dequeue())

    if glob.config.debug:
        printlog(bytes(resp), Ansi.LIGHT_GREEN)

    # Even if the packet is empty, we have to
    # send back an empty response so the client
    # knows it was successfully delivered.
    conn.resp.send(bytes(resp), 200)

def handle_web(conn: Connection) -> None:
    handler = conn.req.uri[5:] # cut off /web/

    # Connections to /web/ only send a single request
    # at a time; no need to iterate through received data.
    if handler not in glob.web_map:
        if handler.startswith('maps/'):
            printlog(f'Handling beatmap update.', Ansi.LIGHT_MAGENTA)
            # Special case for updating maps.
            if (resp := updateBeatmap(conn.req)):
                conn.resp.send(resp, 200)
            return

        printlog(f'Unhandled: {conn.req.uri}.', Ansi.YELLOW)
        return

    printlog(f'Handling {conn.req.uri}', Ansi.LIGHT_MAGENTA)
    if (resp := glob.web_map[handler](conn.req)):
        # XXX: Perhaps web handlers should return
        # a bytearray which could be cast to bytes
        # here at the end? Probably a better soln.

        if glob.config.debug:
            printlog(resp, Ansi.LIGHT_GREEN)

        conn.resp.send(resp, 200)

def handle_ss(conn: Connection) -> None:
    if len(conn.req.uri) != 16:
        conn.resp.send(b'No file found!', 404)
        return

    path = f'screenshots/{conn.req.uri[4:]}'

    if not exists(path):
        conn.resp.send(b'No file found!', 404)
        return

    with open(path, 'rb') as f:
        conn.resp.send(f.read(), 200)

def handle_dl(conn: Connection) -> None:
    if not all(x in conn.req.args for x in ('u', 'h', 'vv')):
        conn.resp.send(b'Method requires authorization.', 401)
        return

    if not (p := glob.players.get_from_cred(conn.req.args['u'], conn.req.args['h'])):
        return

    if not conn.req.uri[3:].isnumeric():
        # Set ID requested is not a number.
        return

    set_id = int(conn.req.uri[3:])

    if exists(filepath := f'mapsets/{set_id}.osz'):
        with open(filepath, 'rb') as f:
            content = f.read()
    else:
        # Map not cached, get from a mirror
        # XXX: I'm considering handling this myself, aswell..
        if not (r := req_get(f'https://osu.gatari.pw/d/{set_id}')):
            conn.resp.send(b'ERROR: DOWNLOAD_NOT_AVAILABLE')
            return

        content = r.content

        # Save to disk.
        with open(filepath, 'wb+') as f:
            f.write(content)

    conn.resp.send(content, 200)

# XXX: This won't be completed for a while most likely..
# Focused on other parts of the design (web mostly).
# username_regex = re_comp(r'^[\w \[\]-]{2,15}$')
# email_regex = re_comp(r'^[\w\.\+\-]+@[\w\-]+\.[\w\-\.]+$')
#def registration(data: bytes) -> None:
#    split = [i for i in data.decode().split('--') if i]
#    headers = split[0]
#    name, email, password = [i.split('\r\n')[3] for i in split[2:5]]
#    # peppy sends password as plaintext..?
#
#    if len(password) not in range(8, 33):
#        return printlog('Registration: password does not meet length reqs.')
#
#    if not re_match(username_regex, name):
#        return printlog('Registration: name did not match regex.', Ansi.YELLOW)
#
#    if not re_match(email_regex, email) or len(email) > 254: # TODO: add len checks to regex
#        return printlog('Registration: email did not match regex.', Ansi.YELLOW)
#
#    name_safe = Player.ensure_safe(name)
#
#    if glob.db.fetch('SELECT 1 FROM users WHERE name_safe = %s', [name_safe]):
#        return printlog(f'Registration: user {name} already exists.', Ansi.YELLOW)
#
#    user_id = glob.db.execute(
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
#    glob.db.execute('INSERT INTO stats (id) VALUES (%s)', [user_id])
#    printlog(f'Registration: <name: {name} | id: {user_id}>.', Ansi.GREEN)
