# bancho.py
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/osuAkatsuki/bancho.py/master.svg)](https://results.pre-commit.ci/latest/github/osuAkatsuki/bancho.py/master)
[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

bancho.py is an in-progress osu! server implementation geared towards developers
of all levels of experience looking to host their own osu! server instances.

it is developed primarily by [Akatsuki](https://akatsuki.pw/) as a replacement
for pre-existing implementations that were either discontinued, or failed to
keep their codebases maintainable. the project has undergone extensive
refactoring as it's grown, and our aim is to create the most easily maintainable,
reliable, scalable, and feature-rich osu! server implementation on the market.

# Setup
knowledge of linux, python, and databases will certainly help, but are by no
means required.

(lots of people have installed this server with no prior programming experience!)

## cloning the required repositories to your machine
```sh
# clone bancho.py's repository
git clone https://github.com/osuAkatsuki/bancho.py.git && cd bancho.py

# clone bancho.py's submodule repositories
git submodule update --init
```

## installing bancho.py's requirements
```sh
# python3.9 is often not available natively,
# so we can use deadsnakes to provide it!
# https://github.com/deadsnakes/python3.9
sudo add-apt-repository ppa:deadsnakes

# install required programs for running bancho.py
sudo apt install python3.9-dev python3.9-distutils cmake build-essential \
                 mysql-server redis-server nginx certbot

# install python's package manager, pip
wget https://bootstrap.pypa.io/get-pip.py
python3.9 get-pip.py && rm get-pip.py

# install bancho.py's python requirements
python3.9 -m pip install -U pip setuptools
python3.9 -m pip install -r requirements.txt
```

## creating a database for bancho.py
```sh
# login to mysql as an root (default administrator account)
# this will put you into a shell where you can execute mysql commands
mysql -u root -p
```

```sql
# create a database for bancho.py to use
# (you can name this whatever you'd like)
CREATE DATABASE YOUR_DB_NAME;

# create a user to use the bancho.py database
CREATE USER 'YOUR_DB_USER'@'localhost' IDENTIFIED BY 'YOUR_DB_PASSWORD';

# grant the user full access to all tables in the bancho.py database
GRANT ALL PRIVILEGES ON YOUR_DB_NAME.* TO 'YOUR_DB_USER'@'localhost';

# exit the mysql shell, back to bash
quit
```

## setting up the database's structure for bancho.py
```sh
# import bancho.py's mysql structure
mysql -u YOUR_DB_USER -p YOUR_DB_NAME < migrations/base.sql
```

## creating an ssl certificate (to allow https traffic)
```sh
# generate an ssl certificate for your domain (change email & domain)
sudo certbot certonly \
    --manual \
    --preferred-challenges=dns \
    --email YOUR_EMAIL_ADDRESS \
    --server https://acme-v02.api.letsencrypt.org/directory \
    --agree-tos \
    -d *.YOUR_DOMAIN
```

## configuring a reverse proxy (we'll use nginx)
```sh
# copy our nginx config to /etc/nginx/sites-available,
# and make a symbolic link to /etc/nginx/sites-enabled
sudo cp ext/nginx.conf /etc/nginx/sites-available/bancho.conf
sudo ln -s /etc/nginx/sites-available/bancho.conf /etc/nginx/sites-enabled/bancho.conf

# edit the nginx configuration file
sudo nano /etc/nginx/sites-available/bancho.conf

# reload the reverse proxy's config
sudo nginx -s reload
```

## configuring bancho.py
```sh
# create a configuration file from the sample provided
cp .env.example .env

# open the configuration file for editing
nano .env
```

## profit?
```sh
# start the server
./main.py
```

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
