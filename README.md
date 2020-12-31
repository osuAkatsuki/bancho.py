[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

## A dev-friendly osu! server written in modern python

gulag is my take on the abstraction of an osu! server; it's native
async and relatively low-level design allows for many features not seen
in other server implementations (especially for python), and it should
be more than packed enough with performance-driven programming for any
realistic private server use-case™️.

I'm mainly writing this as it's by-far the subject I'm currently the most
educated in.. I started [Akatsuki](https://akatsuki.pw/) (and programming
alltogether) back in October of 2017, and I've been managing it since..

If you're only in it for performance and don't mind using a lower-level
language, consider checking out [Peace](https://github.com/Pure-Peace/Peace),
a somewhat similar modern implementation written in Rust.

The server is already nearly on-par with competing servers and is already likely
production-capable; however there's not currently an official finished frontend
for the project. The central db structure's (users, maps, scores) core elements
are obviously similar on both ripple and gulag's db setup, so it should not be too
difficult to get this project working with [Hanayo](https://github.com/osuripple/hanayo),
though I haven't tried myself. There are also some partially comlpete implementations
of a frontend for gulag, such as [gulag-web](https://github.com/Yo-ru/gulag-web).

If you're just looking for a standalone osu! server, this is likely one of your
best bets on the current market, though. Hopefully that will become true on a
much larger scale with some time ;).

## Plans/Ideas

### Beatmap submission system (medium difficulty & effort)

This one is pretty self-explanatory - be able to submit maps to the server
using osu!'s normal in-game beatmap submission system. For this, I'm pretty
sure the id is constrained to being an int32 and negative numbers won't work
(and i'm already using them for buttons anyways), so we'll probably have to
count down from 2147483647.. or start from 1b or something lol..

### Tournament host commandset (low/medium difficulty & effort) [almost complete]

Basically the idea for this one is a set of commands for event managers to be
able to set up things like mappools with the server before the matches, so that
referees have a set of commands to automatically pick maps/mods, keep score,
and post updates to the chat and stuff. Could also make it so players are
automatically moved into the right slots for their team and for team names to
be gotten from the regex of the tourney match name.. Most of this abstraction
is also independant of the osu! implementation, so I pretty much have free reign
on how I do things, so this sounds pretty fun.

### Bound chat embeds that run code server-side (medium? difficulty & effort)

This might not make a hell of a lot of sense, but it's actually already mostly
working.. Basically, I want clickable embeds in the osu! chat that when clicked,
run some pre-allocated function server-side that's bound to the player (security).
This is a really abstract idea so it can be expanded to pretty much everything,
like in-game admin panels and maybe even interactive menus with some higher-order
abstraction? We'll see lol.. Credits go to rumoi for the original idea on this one,
as they tried to implement something similar back in [ruri](https://github.com/rumoi/ruri).

## Requirements

- Some know-how with Linux (tested on Ubuntu 18.04), python, and general-programming knowledge.
- An osu! account (or more specifically, an osu! api key). This is technically optional, but is required for full usage.
- An SSL Certificate for c(e4-6).ppy.sh (such as [this](https://github.com/osuthailand/ainu-certificate)).

## Setup

Setup should be pretty simple - the commands below should set you right up.

Notes:

- Ubuntu 20.04 is known to have issues with nginx and osu for unknown reasons?
- I will not be able to help you out with creating a custom certificate of your own.
- If you have any difficulties setting up gulag, feel free to join the Discord server at the top of the README, we now have a bit of a community!

```sh
# Install python3.9 (requires ppa).
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.9 python3.9-dev python3.9-distutils

# Install pip for 3.9.
wget https://bootstrap.pypa.io/get-pip.py
python3.9 get-pip.py && rm get-pip.py

# Install our db, reverse-proxy, and build tools.
sudo apt install mysql-server nginx build-essential

# Clone gulag from github.
git clone https://github.com/cmyui/gulag.git && cd gulag

# Init & update submodules.
git submodule init && git submodule update

# Build oppai-ng's binary.
cd oppai-ng && ./build && cd ..

# Install project requirements.
python3.9 -m pip install -r ext/requirements.txt

# Import the database structure.
# NOTE: create an empty database before doing this.
# This will also insert basic osu! channels & the bot.
mysql -u your_sql_username -p your_db_name < ext/db.sql

# Add gulag's nginx config to your nginx/sites-enabled.
# NOTE: default unix socket location is `/tmp/gulag.sock`,
# and you will have to change the certificate pathes in
# the nginx config file to your own certificate pathes.
sudo ln ext/nginx.conf /etc/nginx/sites-enabled/gulag.conf
sudo nginx -s reload

# Configure gulag.
cp ext/config.sample.py config.py
nano config.py

# Start the server.
./main.py
```
