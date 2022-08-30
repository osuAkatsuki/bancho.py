# bancho.py
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/osuAkatsuki/bancho.py/master.svg)](https://results.pre-commit.ci/latest/github/osuAkatsuki/bancho.py/master)
[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

bancho.py is an in-progress osu! server implementation for developers of all levels
of experience interested in hosting their own osu private server instance(s).

the project is developed primarily by the [Akatsuki](https://akatsuki.pw/) team,
and our aim is to create the most easily maintainable, reliable, and feature-rich
osu! server implementation available.

# Setup
knowledge of linux, python, and databases will certainly help, but are by no
means required.

(lots of people have installed this server with no prior programming experience!)

if you get stuck at any point in the process - we have a public discord above :)

this guide will be targetted towards ubuntu - other distros may have slightly
different setup processes.

## download the osu! server codebase onto your machine
```sh
# clone bancho.py's repository
git clone https://github.com/osuAkatsuki/bancho.py.git

# enter bancho.py's new directory
cd bancho.py

# clone bancho.py's dependencies' repositories
git submodule update --recursive --init
```

## installing bancho.py's requirements

bancho.py is a ~15,000 line codebase built on the shoulder of giants.

we aim to minimize our dependencies, but still rely on ones such as
- python (programming language)
- mysql (relational database)
- redis (in memory database)
- nginx (http(s) reverse proxy)
- certbot (ssl certificate tool)
- cmake and build-essential (build tools for c/c++)

these dependencies are all retrieved by and contained within docker containers.
all you need to install on your system is `docker` and `docker-compose`, and ensure
that your user is a member of the `docker` group if your package manager doesn't do
that for you. you may need to log out and back in.

## configuring bancho.py
all configuration for the osu! server (bancho.py) itself can be done from the
`.env` file. we provide an example `.env.example` file which you can use as a base.
```sh
# create a configuration file from the sample provided
cp .env.example .env

# you'll want to configure *at least* the three marked (XXX) variables,
# as well as set the OSU_API_KEY if you need any info from osu!'s v1 api
# (e.g. beatmaps).

# open the configuration file for editing
nano .env
```

you also probably want to modify or remove the `web` service from the `docker-compose.yml`
depending on whether you have a front-facing website for your osu server.

## creating an ssl certificate (to allow https traffic)
```sh
# you'll need to change:
# - YOUR_EMAIL_ADDRESS
# - YOUR_DOMAIN

# generate an ssl certificate for your domain
sudo certbot certonly \
    --manual \
    --preferred-challenges=dns \
    --email YOUR_EMAIL_ADDRESS \
    --server https://acme-v02.api.letsencrypt.org/directory \
    --agree-tos \
    -d *.YOUR_DOMAIN
```

put the key and certificate somewhere on your server, and then
modify the two `SSL_..._PATH` variables in `.env` for them.

## configuring a reverse proxy (we'll use nginx)
bancho.py relies on a reverse proxy for tls (https) support, and for ease-of-use
in terms of configuration. nginx is an open-source and efficient web server we'll
be using for this guide, but feel free to check out others, like caddy and h2o.

```sh
# copy the example nginx configuration file
cp ext/nginx.conf.example ext/nginx.conf

# now, you can edit the config file.
# the spots you'll need to change are marked.
nano ext/nginx.conf
```

## congratulations! you just setup an osu! private server

if everything went well, you should be able to start your server up:

```sh
# start the server. note: you may have to start the services
# one-by-one until some future update does it automatically:

docker-compose up -d mysql
# wait about a minute or two the first time to wait for mysql to init

docker-compose up -d redis
docker-compose up -d bancho
# maybe wait a minute here too

docker-compose up -d web
# the above is not needed if you removed web before

docker-compose up -d nginx
# done!
```

and you should see something along the lines of:

![tada](https://cdn.discordapp.com/attachments/616400094408736779/993705619498467369/ld-iZXysVXqwhM8.png)

# Directory Structure
    .
    ├── app                   # the server - logic, classes and objects
    |   ├── api                 # code related to handling external requests
    |   |   ├── domains           # endpoints that can be reached from externally
    |   |   |   ├── api.py        # endpoints available @ https://api.ppy.sh
    |   |   |   ├── ava.py        # endpoints available @ https://a.ppy.sh
    |   |   |   ├── cho.py        # endpoints available @ https://c.ppy.sh
    |   |   |   ├── map.py        # endpoints available @ https://b.ppy.sh
    |   |   |   └── osu.py        # endpoints available @ https://osu.ppy.sh
    |   |   |
    |   |   ├── init_api.py       # logic for putting the server together
    |   |   └── middlewares.py    # logic that wraps around the endpoints
    |   |
    |   ├── constants           # logic & data for constant server-side classes & objects
    |   |   ├── clientflags.py    # anticheat flags used by the osu! client
    |   |   ├── gamemodes.py      # osu! gamemodes, with relax/autopilot support
    |   |   ├── mods.py           # osu! gameplay modifiers
    |   |   ├── privileges.py     # privileges for players, globally & in clans
    |   |   └── regexes.py        # regexes used throughout the codebase
    |   |
    |   ├── objects             # logic & data for dynamic server-side classes & objects
    |   |   ├── achievement.py    # representation of individual achievements
    |   |   ├── beatmap.py        # representation of individual map(set)s
    |   |   ├── channel.py        # representation of individual chat channels
    |   |   ├── clan.py           # representation of individual clans
    |   |   ├── collection.py     # collections of dynamic objects (for in-memory storage)
    |   |   ├── match.py          # individual multiplayer matches
    |   |   ├── menu.py           # (WIP) concept for interactive menus in chat channels
    |   |   ├── models.py         # structures of api request bodies
    |   |   ├── player.py         # representation of individual players
    |   |   └── score.py          # representation of individual scores
    |   |
    |   ├── state               # objects representing live server-state
    |   |   ├── cache.py          # data saved for optimization purposes
    |   |   ├── services.py       # instances of 3rd-party services (e.g. databases)
    |   |   └── sessions.py       # active sessions (players, channels, matches, etc.)
    |   |
    |   ├── bg_loops.py           # loops running while the server is running
    |   ├── commands.py           # commands available in osu!'s chat
    |   ├── packets.py            # a module for (de)serialization of osu! packets
    |   └── settings.py           # manages configuration values from the user
    |
    ├── ext                   # external entities used when running the server
    ├── migrations            # database migrations - updates to schema
    ├── tools                 # various tools made throughout bancho.py's history
    └── main.py               # an entry point (script) to run the server
