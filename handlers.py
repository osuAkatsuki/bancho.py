import packets
from cmyui.web import Connection

from objects import glob

from events.events import login as ev_login
from console import *

# This has to be imported so
# that the events are loaded.
from events import web

__all__ = (
    'handle_bancho',
    'handle_web',
    #'registration'
)

def handle_bancho(conn: Connection) -> None:
    if 'User-Agent' not in conn.req.headers \
    or conn.req.headers['User-Agent'] != 'osu!':
        return

    resp = bytearray()

    if 'osu-token' not in conn.req.headers:
        # Login is a bit of a special case,
        # so we'll handle it separately.
        login_data = ev_login(conn.req.body)

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

            if pr.packetID not in glob.bancho_map:
                printlog(f'Unhandled: {pr!r}', Ansi.LIGHT_YELLOW)
                pr.ignore_packet()
                continue

            printlog(f'Handling {pr!r}', Ansi.MAGENTA)
            glob.bancho_map[pr.packetID](p, pr)

        while not p.queue_empty():
            # Read all queued packets into stream
            resp.extend(p.dequeue())

    if glob.config.debug:
        print(bytes(resp))

    # Even if the packet is empty, we have to
    # send back an empty response so the client
    # knows it was successfully delivered.
    conn.resp.send(bytes(resp), 200)

def handle_web(conn: Connection) -> None:
    handler = conn.req.uri[5:] # cut off /web/

    # Connections to /web/ only send a single request
    # at a time; no need to iterate through received data.
    if handler not in glob.web_map:
        printlog(f'Unhandled: {conn.req.uri}.', Ansi.YELLOW)
        return

    printlog(f'Handling {conn.req.uri}', Ansi.MAGENTA)
    if (resp := glob.web_map[handler](conn.req)):
        # XXX: Perhaps web handlers should return
        # a bytearray which could be cast to bytes
        # here at the end? Probably a better soln.
        conn.resp.send(resp, 200)

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
#            int(Privileges.Verified),
#            hashpw(md5(password.encode()).hexdigest().encode(), gensalt()).decode()
#        ])
#
#    glob.db.execute('INSERT INTO stats (id) VALUES (%s)', [user_id])
#    printlog(f'Registration: <name: {name} | id: {user_id}>.', Ansi.GREEN)
