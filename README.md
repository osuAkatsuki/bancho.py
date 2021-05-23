[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

gulag is my implementation of an osu! server's backend (bancho protocol, /web/
endpoints, avatars, static assets, and a devevloper rest api). it's designed as
a modern substitution for existing osu! server projects who've become inactive
or who've gone closed-source. i aim to make this project the ideal choice for
running osu! private servers, and to fully support osu!'s protocol, while
abusing it a little to get as much as we safely can out of it. :)

i'll set the stage with a brief introduction; i've been playing actively on osu!
private servers since early 2016, and founded [akatsuki](https://akatsuki.pw) in
late 2017 using [ripple](https://github.com/osuripple)'s source with no prior
development experience. i spent nearly all of my spare time learning more about
the wonderful world of (osu!) programming by working on their codebase, until
i had eventually learned enough to try writing a server from scratch.

gulag was my third attempt to write an osu! server, and based on my previous
failures i didn't believe i had what it took to write a competitive server; but
after months of development and gradual progress it's seemed more and more
likely that it'd really become the replacement for akatsuki's existing stack.

in my (pretty qualified) opinion (as someone who's really dove deep into most
competing implementations), i'd definitely say gulag is currently the most
maintainable, thoughtfully efficient and well suited for the operation of an
osu! private server of anything i've seen. i think there are some great
projects out there (especially some of the more modern ones), but frankly
i've spent countless hours thinking about how i can improve the server and
make it superior in a wide variety of different ways, not being scared to
tear down & refactor large structures in the codebase as i learn more.
i really think it's paid off, and i can say without a doubt that i plan to
use this software for akatsuki. of course everyone has their biases and values
so i recommend you take a good look at all the options and come to an informed
decision if you're planning on running a server!

the project has also seemingly increased activity in the osu! private server
development community over the last year and many other open source osu! server
projects have popped up, such as [peace](https://github.com/Pure-Peace/Peace),
[kuriso](https://github.com/osukurikku/kuriso), and many other attempts have
been made by less experienced developers to write servers as a means to learn
more about programming as a whole, which has thankfully become more possible
due to the increased amount of documentation & examples (such as gulag) available.

at the moment, gulag's still in development and if you're running a serious
instance of a private server in production, i wouldn't yet recommend switching
your stack as there is still work to be done; but take a look around and see
what you think. it's certainly fine for little friends-only servers or if
you're just looking to play around; if you're running one of these, please
consider joining our discord, we really need all the testing we can get. :D

contributions are welcome but please don't feel like they're required; gulag's
mostly my baby and i really want to get the master implementation as close to
perfection as i can. if you're a dev and want to contribute, i'd strongly
recommend forking the repository and playing around on a server of your own,
this is how all previous high quality contributions have come into fruitition.

there is currently no official frontend project for gulag. the most serious
attempt to date is [gulag-web](https://github.com/Varkaria/gulag-web), though
there is a pretty decent chance that [varkaria](https://github.com/Varkaria) and
i will be doing some major refactoring in the future before moving akatsuki onto
the new stack; the code will need to be of comparable quality to what you see here.

Installation Guide
-------------
important notes:
- ubuntu 20.04 & nginx have unknown issues? i recommend using 18.04
- i will not help with the creation of a fake *.ppy.sh cert for switcher support.

```sh
# add ppa for py3.9 (i love anthonywritescode)
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
