# FOR MAINTAINER NOTE:
Our code is public, but our database, package and website are and will be not public. If you want to use our source you most likely need to write stuff yourself unless I personally give you the code

[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

gulag is my implementation of an osu! server's backend; it handles connections
from the osu! client, and has a developer rest api for programmatic interaction.

it's asynchronous design allows it to very efficiently manage the io overhead of an
osu! private server (many external requests to osu!api, mirror, database, etc.),
and it implements much more effective caching than any competitive implementations.
it's written in modern, high-level python(3.9) from the transport (tcp/ip) socket
layer directly using my [lightweight web framework](https://github.com/cmyui/cmyui_pkg).

i aim to make this project the ideal choice for running osu! private servers,
in terms of it's featureset, efficiency, safety, development ease and simplicity.
when production-ready, it will be used on [Akatsuki](https://akatsuki.pw) which
is currently the most active private server; it should be an ideal test.

gulag seemed to re-spark interest in the osu! server development community,
so i decided to start a public [Discord](https://discord.gg/ShEQgUx) server where
more experienced (osu!-related) developers can help out some of the newer ones,
and i encourage you to join if that sounds interesting! :)

there is no current official frontend project for gulag, but [guweb](https://github.com/Varkaria/guweb)
is by-far the most serious attempt. the future is undecided in terms of frontend.

Contributing
-------------
contributions are welcome but please keep consistent with the overall style and
design choices from the project. i aim to keep all of the code to similar standards,
especially in performance-critical or code that will be referenced frequently
(either by the programmer or the system). the diff should be in it's simplest form.

Installation Guide
-------------
```sh
# add ppa for py3.9 (i love asottile)
sudo add-apt-repository ppa:deadsnakes/ppa

# install requirements (py3.9, mysql, nginx, build tools, certbot)
sudo apt install python3.9 python3.9-dev python3.9-distutils \
                 mysql-server nginx build-essential certbot

# install pip for py3.9
wget https://bootstrap.pypa.io/get-pip.py
python3.9 get-pip.py && rm get-pip.py

# clone the repo & init submodules
git clone https://github.com/cmyui/gulag.git && cd gulag
git submodule init && git submodule update

# install gulag requirements w/ pip
python3.9 -m pip install -r ext/requirements.txt

# build oppai-ng's static library
cd oppai-ng && ./libbuild && cd ..

######################################
# NOTE: before continuing, create an #
# empty database in mysql for gulag  #
######################################

# import gulag's mysql structure
mysql -u your_sql_username -p your_db_name < ext/db.sql

# generate an ssl certificate for your domain (change email & domain)
sudo certbot certonly \
    --manual \
    --preferred-challenges=dns \
    --email your@email.com \
    --server https://acme-v02.api.letsencrypt.org/directory \
    --agree-tos \
    -d *.your.domain

# copy our nginx config to `sites-enabled` & open for editing
sudo cp ext/nginx.conf /etc/nginx/sites-enabled/gulag.conf
sudo nano /etc/nginx/sites-enabled/gulag.conf

##########################################
# NOTE: before continuing, make sure you #
# have completely configured the file.   #
##########################################

# reload the reverse proxy's config
sudo nginx -s reload

# copy our gulag config to cwd & open for editing
cp ext/config.sample.py config.py
nano config.py

##########################################
# NOTE: before continuing, make sure you #
# have completely configured the file.   #
##########################################

# start the server
./main.py
```

Directory Structure
------
    .
    ├── constants  # code representing gamemodes, mods, privileges, and other constants.
    ├── ext        # external files from gulag's primary operation.
    ├── objects    # code for representing players, scores, maps, and more.
    ├── utils      # utility functions used throughout the codebase for general purposes.
    └── domains    # the route-containing domains accessible to the public web.
        ├── cho    # (ce|c4|c5|c6).ppy.sh/* routes (bancho connections)
        ├── osu    # osu.ppy.sh/* routes (mainly /web/ & /api/)
        └── ava    # a.ppy.sh/* routes (avatars)
