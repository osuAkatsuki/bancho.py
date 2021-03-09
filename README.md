[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

DISCLAIMER: gulag is an unfinished project; there is still a ways to go. i work on
this mostly for fun in my spare time; if you're planning on using this for your
live server, that's great, but remember i'm not working for you lol. development
will continue at whatever pace depending on how much time & effort i wish to allocate.

gulag is my implementation of an osu! server's backend (bancho protocol, avatars &
/web/* endpoints, and a dev rest api). it's designed with the experienced developer
in mind; whether you're a current server owner or an experienced developer coming into
the community, programming gulag should be about the ideas rather than the code, and
the codebase should reflect that. try it out for yourself and see what you think!

note that in it's current stage, gulag is not nescessarily user-friendly; please
remember that this is not my primary goal with the project - making the 'best'
server does not nescessarily mean making the most user friendly one :PP. perhaps
eventually the focus will shift, but not in the near future.

please don't feel like you need to contribute. this is mostly a one man project and
this is the way i like it; bugs and small improvements are welcome but the chances
of you coming into the community and being able to write a whole system better than
i could (with my >10k lines of exp and years of osu! server development) is unlikely..
if you're making large scale changes, do it for learning rather than clout, and the long
term game will treat you nicely :)

there is currently no official frontend project for gulag, but members of the community
have made significant headway with [gulag-web](https://github.com/Yo-ru/gulag-web).
please note that this project is not maintained by me, and that my focus remains on the
osu! server itself.

Installation Guide
-------------
important notes:
- ubuntu 20.04 & nginx have unknown issues? i recommend using 18.04
- i will not help with the creation of a fake ssl cert; -devserver support coming soon.

```sh
# add ppa for py3.9 (required since it's new)
sudo add-apt-repository ppa:deadsnakes/ppa

# install requirements (py3.9, mysql, nginx, build tools)
sudo apt install python3.9 python3.9-dev python3.9-distutils mysql-server nginx build-essential

# install pip for py3.9
wget https://bootstrap.pypa.io/get-pip.py
python3.9 get-pip.py && rm get-pip.py

# install gulag requirements w/ pip
python3.9 -m pip install -r ext/requirements.txt

# clone the repo & init submodules
git clone https://github.com/cmyui/gulag.git && cd gulag
git submodule init && git submodule update

# build oppai-ng's binary
cd oppai-ng && ./build && cd ..

######################################
# NOTE: before continuing, create an #
# empty database in mysql for gulag  #
######################################

# import gulag's mysql structure
mysql -u your_sql_username -p your_db_name < ext/db.sql

########################################################
# NOTE: before continuing, generate an ssl cert & edit #
# the certificate paths nginx config (ext/nginx.conf)  #
########################################################

# symlink our nginx config to /etc/nginx/sites-enabled
sudo ln ext/nginx.conf /etc/nginx/sites-enabled/gulag.conf
sudo nginx -s reload

# copy configuration file from /ext/ & configure it
cp ext/config.sample.py config.py
nano config.py

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
