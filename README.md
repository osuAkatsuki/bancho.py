[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

DISCLAIMER: gulag is still in a beta stage - the server is certainly getting quite
stable & useable now, but don't let it fool you too much.. there are still large
portions of the underlying systems that have yet to be implemented completely correctly.

gulag is my implementation of an osu! server's backend (bancho protocol, /web endpoints,
avatars/assets, and a devevloper rest api). it's designed for relatively experienced devs
looking for an osu! server with more bells and whistles than many other implementations.

note that in it's current stage, gulag is not nescessarily user-friendly..
dev-friendly is much better wording; please remember that this is not one of my
current goals with the project. perhaps eventually the focus will shift, but not
in the foreseeable future. making small prs to try to fix this is also not a great
idea, i'm not in the business of trying to make people think it's made to be
user-friendly when it's not really lol. the time may come eventually.

please don't feel like you need to contribute. this is mostly a one man project and
this is the way i like it; gulag is my baby and i can probably tell you about any
portion of code off the top of my head. bugfixes and small improvements are welcome,
but i think with the average osu developer age being quite low, there will be lots
more newer devs than older devs :P (i myself am still quite new in the grand scheme).
if you're making large scale changes, do it for learning rather than clout, and
i promise the long-term game will this kind of behaviour nicely :)

there is currently no official frontend project for gulag, but members of the community
have made significant headway with [gulag-web](https://github.com/Yo-ru/gulag-web).
please note that this project is not maintained by me, and that my focus remains on the
osu! server itself.

Installation Guide
-------------
important notes:
- ubuntu 20.04 & nginx have unknown issues? i recommend using 18.04
- i will not help with the creation of a fake *.ppy.sh cert for switcher support.

```sh
# add ppa for py3.9 (required since it's new)
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

# build oppai-ng's binary
cd oppai-ng && ./build && cd ..

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
    └── domains    # the route-continaing domains accessible to the public web.
        ├── cho    # (ce|c4|c5|c6).ppy.sh/* routes (bancho connections)
        ├── osu    # osu.ppy.sh/* routes (mainly /web/ & /api/)
        └── ava    # a.ppy.sh/* routes (avatars)
