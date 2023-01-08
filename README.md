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

# Prerequisites
knowledge of linux, python, and databases will certainly help, but are by no
means required.

(lots of people have installed this server with no prior programming experience!)

if you get stuck at any point in the process - we have a public discord above :)

this guide will be targetted towards ubuntu - other distros may have slightly
different setup processes.

# Requirements
bancho.py is a ~15,000 line codebase built on the shoulder of giants.

we aim to minimize our dependencies, but still rely on ones such as
- python (programming language)
- rust (programming language)
- mysql (relational database)
- redis (in memory database)
- nginx (http(s) reverse proxy)
- certbot (ssl certificate tool)
- build-essential (build tools for c/c++)

as well as some others.

# Docker installation
for ease of use, we recommend you to use this method.

all the dependencies are all retrieved by and contained within docker containers. all you need to install on your system is docker and docker-compose, and ensure that your user is a member of the docker group. if your package manager doesn't do that for you, you may need to log out and back in.
## installing bancho.py's requirements
```sh
# install docker and docker-compose
sudo apt install -y docker \
                    docker-compose
```
## download the osu! server codebase onto your machine
```sh
# clone bancho.py's repository
git clone https://github.com/osuAkatsuki/bancho.py

# enter bancho.py's new directory
cd bancho.py
```
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
## configuring a reverse proxy (we'll use nginx)
```sh
# copy the example nginx configuration file
cp ext/nginx.conf.example ext/nginx.conf

# now, you can edit the config file.
# the spots you'll need to change are marked.
nano ext/nginx.conf
```

## congratulations! you just set up an osu! private server

if everything went well, you should be able to start your server up:

```sh
# start the server. note: you may have to start the services
# one-by-one until some future update does it automatically:

docker-compose up -d mysql
# wait about a minute or two the first time to wait for mysql to init

docker-compose up -d redis
docker-compose up -d bancho
# maybe wait a minute here too

docker-compose up -d nginx
# done!
```

additionally, these commands could help you in case you need to know the status of the containers
```sh
# list containers
docker container ls

# fetch logs of a container
# replace <container_name> with the name of the container
# examples:
# - docker container logs bpy_bancho
# - docker container logs bpy_mysql
docker container logs <container_name>
```
for more information, see the [docker-cli documentation](https://docs.docker.com/engine/reference/commandline/cli/).
# Manual installation
## installing bancho.py's requirements
```sh
# python3.9 is often not available natively,
# but we can rely on deadsnakes to provide it.
# https://github.com/deadsnakes/python3.9
sudo add-apt-repository -y ppa:deadsnakes

# install required programs for running bancho.py
sudo apt install -y python3.9-dev python3.9-distutils \
                    build-essential \
                    mysql-server redis-server \
                    nginx certbot

# install rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# install python's package manager, pip
# it's used to install python-specific dependencies
wget https://bootstrap.pypa.io/get-pip.py
python3.9 get-pip.py && rm get-pip.py

# make sure pip and setuptools are up to date
python3.9 -m pip install -U pip setuptools pipenv

# install bancho.py's python-specific dependencies
# (if you plan to work as a dev, you can use `make install-dev`)
make install
```

## creating a database for bancho.py
you will need to create a database for bancho.py to store persistent data.

the server uses this database to store metadata & logs, such as user accounts
and stats, beatmaps and beatmapsets, chat channels, tourney mappools and more.

```sh
# start your database server
sudo service mysql start

# login to mysql's shell with root - the default admin account

# note that this shell can be rather dangerous - it allows users
# to perform arbitrary sql commands to interact with the database.

# it's also very useful, powerful, and quick when used correctly.
sudo mysql
```

from this mysql shell, we'll want to create a database, create a user account,
and give the user full permissions to the database.

then, later on, we'll configure bancho.py to use this database as well.
```sql
# you'll need to change:
# - YOUR_DB_NAME
# - YOUR_DB_USER
# - YOUR_DB_PASSWORD

# create a database for bancho.py to use
CREATE DATABASE YOUR_DB_NAME;

# create a user to use the bancho.py database
CREATE USER 'YOUR_DB_USER'@'localhost' IDENTIFIED BY 'YOUR_DB_PASSWORD';

# grant the user full access to all tables in the bancho.py database
GRANT ALL PRIVILEGES ON YOUR_DB_NAME.* TO 'YOUR_DB_USER'@'localhost';

# make sure privilege changes are applied immediately.
FLUSH PRIVILEGES;

# exit the mysql shell, back to bash
quit
```

## setting up the database's structure for bancho.py
we've now created an empty database - databases are full of 2-dimensional
tables of data.

bancho.py has many tables it uses to organize information, for example, there
are tables like `users` and `scores` for storing their respective information.

the columns (vertical) represent the types of data stored for a `user` or `score`.
for example, the number of 300s in a score, or the privileges of a user.

the rows (horizontal) represent the individual items or events in a table.
for example, an individual score in the scores table.

this base state of the database is stored in `ext/base.sql`; it's a bunch of
sql commands that can be run in sequence to create the base state we want.
```sh
# you'll need to change:
# - YOUR_DB_NAME
# - YOUR_DB_USER

# import bancho.py's mysql structure to our new db
# this runs the contents of the file as sql commands.
mysql -u YOUR_DB_USER -p YOUR_DB_NAME < migrations/base.sql

```
## configuring a reverse proxy (we'll use nginx)
bancho.py relies on a reverse proxy for tls (https) support, and for ease-of-use
in terms of configuration. nginx is an open-source and efficient web server we'll
be using for this guide, but feel free to check out others, like caddy and h2o.

```sh
# copy the example nginx config to /etc/nginx/sites-available,
# and make a symbolic link to /etc/nginx/sites-enabled
sudo cp ext/nginx.conf.example /etc/nginx/sites-available/bancho.conf
sudo ln -s /etc/nginx/sites-available/bancho.conf /etc/nginx/sites-enabled/bancho.conf

# now, you can edit the config file.
# the spots you'll need to change are marked.
sudo nano /etc/nginx/sites-available/bancho.conf

# reload config from disk
sudo nginx -s reload
```

## configuring bancho.py
all configuration for the osu! server (bancho.py) itself can be done from the
`.env` file. we provide an example `.env.example` file which you can use as a base.
```sh
# create a configuration file from the sample provided
cp .env.example .env

# you'll want to configure *at least* all the database related fields (DB_*),
# as well as set the OSU_API_KEY if you need any info from osu!'s v1 api
# (e.g. beatmaps).

# open the configuration file for editing
nano .env
```

## congratulations! you just set up an osu! private server

if everything went well, you should be able to start your server up:

```sh
# start the server
make run
```

and you should see something along the lines of:

![tada](https://cdn.discordapp.com/attachments/616400094408736779/993705619498467369/ld-iZXysVXqwhM8.png)

# enabling https traffic
## using cloudflare (flex)
first of all you need a cloudflare account, to create one go to https://dash.cloudflare.com/sign-up, enter your email and password and click on `create account`

![Step 1](https://i.imgur.com/mEhxCgO.png)

now you have to enter your domain. this has to be your actual domain (e.g. `banchopy.com` or `banchopy.net`) and mustn't include any domain-specific hostnames (e.g. `www.banchopy.com` or similar)

![Step 2](https://i.imgur.com/dIHdmza.png)

then you have to choose your plan, for us it should be enough with the `Free plan`, you can also upgrade later if you need it

![Step 3](https://i.imgur.com/ZpV2SvS.png)

now you'll have to copy the nameservers required by Cloudflare to your domain registrar. once you've done this, click on `check nameservers`

![Step 4](https://i.imgur.com/GMqVXsF.png)

once you have finished the above you'll have to add some dns records (A records) so that the necessary domains are being pointed to the ip where bancho.py is running

<table>
    <tr>
        <th>
        <ul>
            <li>a.yourdomain.com</li>
            <li>api.yourdomain.com</li>
            <li>assets.yourdomain.com</li>
            <li>c1.yourdomain.com</li>
            <li>c2.yourdomain.com</li>
            <li>c3.yourdomain.com</li>
            <li>c4.yourdomain.com</li>
            <li>c5.yourdomain.com</li>
            <li>c6.yourdomain.com</li>
            <li>ce.yourdomain.com</li>
            <li>cho.yourdomain.com</li>
            <li>c.yourdomain.com</li>
            <li>yourdomain.com</li>
            <li>i.yourdomain.com</li>
            <li>map.yourdomain.com</li>
            <li>osu.yourdomain.com</li>
            <li>s.yourdomain.com</li>
            <li>web.yourdomain.com</li>   
        </ul>
        <th>
            <img src="https://i.imgur.com/2NUyEQJ.png" alt="Step 5">
        </th>
    </tr>
</table>

then go to SSL/TTL > overwiew and activate SSL flex

![Step 6](https://i.imgur.com/txfPE1o.png)

it's also recommended to activate the option to always use HTTPS, you can enable it in SSL/TTL > edge certificates

![Step 7](https://i.imgur.com/1Q7ybLd.png)
## using an own ssl certificate

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
# Directory Structure
    .
    ├── app                   # the server - logic, classes and objects
    |   ├── api                 # code related to handling external requests
    |   |   ├── domains           # endpoints that can be reached from externally
    |   |   |   ├── api.py        # endpoints available @ https://api.ppy.sh
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
