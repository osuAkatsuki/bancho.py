# Setting up (Manual)

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

# optionally, install the nginx geoip2 module if you would like to use it in bancho.py
cd tools && ./enable_geoip_module.sh && cd ..

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

this base state of the database is stored in `migrations/base.sql`; it's a bunch of
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
cp manual.env.example .env

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
