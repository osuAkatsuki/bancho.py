# -*- coding: utf-8 -*-

# The address which the server runs on.
# The server supports both INET4 and UNIX sockets.
# For INET sockets, set to (addr: str, port: int),
# For UNIX sockets, set to the path of the socket.
server_addr = '/tmp/gulag.sock'

# Your MySQL authentication info.
mysql = {
    'db': 'gulag',
    'host': 'localhost',
    'password': 'supersecure',
    'user': 'cmyui'
}

# Your osu!api key. This is required for fetching
# many things, such as beatmap information!
osu_api_key = ''

# The menu icon displayed on
# the main menu of osu! ingame.
menu_icon = (
    'https://link.to/my_image.png', # Image url
    'https://github.com/cmyui/gulag' # Onclick url
)

# Ingame bot command prefix.
command_prefix = '!'

# Displays additional information in the
# console, generally for debugging purposes.
debug = False

# Whether the server is running in 'production mode'.
# Having this as false will disable some features that
# aren't used during testing.
server_build = True
