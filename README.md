[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

Table of Contents
==================
- [Table of Contents](#table-of-contents)
  - [What is gulag?](#what-is-gulag)
  - [Currently supported player commands](#currently-supported-player-commands)
  - [Requirements](#requirements)
  - [Setup](#setup)
  - [Directory Structure](#directory-structure)

What is gulag?
------

gulag is my take on the abstraction of an osu! server; I use native async/await
syntax, and have written the server from the ground up from sockets using my
[python package](https://github.com/cmyui/cmyui_pkg)'s web server implementation.
This relatively low-level design allows for flexibility, cleanliness, and efficiency
not seen in other codebases - all while maintaining the simplicity of Python.

A primary goal of gulag is to keep our codebase a developer-friendly API, so
that programming remains about the logic and ideas, rather than the code itself.

I'm mainly writing this as it's by-far the subject I'm currently the most
educated in.. I started [Akatsuki](https://akatsuki.pw/) (and programming
alltogether) back in October of 2017, and I've been managing it since.

The server has come [a long way](https://cdn.discordapp.com/attachments/616400094408736779/799434379176574986/unknown.png),
and is in quite a usable state. We most likely handle every packet/handler
supported by any competing server implementation, and feature a very large
api and [commandset](#commands) for both developers and players alike, with
many unique features only available with gulag.

gulag's database structure is built from the ground up using no specific
references; this makes it incompatible with common stacks like Ripple's.
[gulag-web](https://github.com/Yo-ru/gulag-web) is a project being developed
primarily by the community members of our [Discord](https://discord.gg/ShEQgUx)
who are interested in the project; they aim to atleast create a fully
functional frontend, while the location of the API remains undecided.
Over the past few weeks the development effort has been growing and some
great progress is starting to be made; I'd recommend checking it out!

Currently supported player commands
------
gulag's commandset has been growing quite nicely.

```
Generic
------

!help: Show information of all documented commands the player can access.
!roll: Roll an n-sided die where n is the number you write (100 default).
!bloodcat: Return a bloodcat link of the user's current map (situation dependant).
!last: Show information about your most recent score.
!with: Specify custom accuracy & mod combinations with `/np`.
!map: Changes the ranked status of the most recently /np'ed map.
!notes: Retrieve the logs of a specified player by name.
!addnote: Add a note to a specified player by name.
!silence: Silence a specified player with a specified duration & reason.
!unsilence: Unsilence a specified player.
!ban: Ban a specified player's account, with a reason.
!unban: Unban a specified player's account, with a reason.
!alert: Send a notification to all players.
!alertu: Send a notification to a specified player by name.
!recalc: Performs a full PP recalc on a specified map, or all maps.
!switchserv: Switch your client's internal endpoints to a specified IP address.
!debug: Toggle the console's debug setting.
!setpriv: Set privileges for a specified player (by name).
!menu_preview: Temporary command to illustrate cmyui's menu option idea.


Multiplayer Management
------

!mp help: Show information of all documented mp commands the player can access.
!mp start: Start the current multiplayer match, with any players ready.
!mp abort: Abort the current in-progress multiplayer match.
!mp force: Force a player into the current match by name.
!mp map: Set the current match's current map by id.
!mp mods: Set the current match's mods, from string form.
!mp host: Set the current match's current host by id.
!mp randpw: Randomize the current match's password.
!mp invite: Invite a player to the current match by name.
!mp addref: Add a referee to the current match by name.
!mp rmref: Remove a referee from the current match by name.
!mp listref: List all referees from the current match.
!mp lock: Lock all unused slots in the current match.
!mp unlock: Unlock locked slots in the current match.
!mp teams: Change the team type for the current match.
!mp condition: Change the win condition for the match.
!mp scrim: Start a scrim in the current match.
!mp endscrim: End the current matches ongoing scrim.
!mp rematch: Restart a scrim with the previous match points, or roll back the most recent match point.
!mp loadpool: Load a mappool into the current match.
!mp unloadpool: Unload the current matches mappool.
!mp ban: Ban a pick in the currently loaded mappool.
!mp unban: Unban a pick in the currently loaded mappool.
!mp pick: Pick a map from the currently loaded mappool.


Mappool Management
------

!pool help: Show information of all documented pool commands the player can access.
!pool create: Add a new mappool to the database.
!pool delete: Remove a mappool from the database.
!pool add: Add a new map to a mappool in the database.
!pool remove: Remove a map from a mappool in the database.
!pool list: List all existing mappools information.
!pool info: Get all information for a specific mappool.


Clan Management
------

!clan help: Show information of all documented clan commands the player can access.
!clan create: Create a clan with a given tag & name.
!clan disband: Disband a clan (admins may disband others clans).
!clan info: Lookup information of a clan by tag.
!clan list: List all existing clans information.
```

Requirements
------

- Some know-how with Linux (tested on Ubuntu 18.04), python, and general-programming knowledge.
- An osu! account (or more specifically, an osu! api key). This is technically optional, but is required for full usage.
- An SSL Certificate for c(e4-6).ppy.sh (such as [this](https://github.com/osuthailand/ainu-certificate)).

Setup
------

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

# Install our database, reverse-proxy, and build tools.
sudo apt install mysql-server nginx build-essential

# Clone gulag from github.
git clone https://github.com/cmyui/gulag.git && cd gulag

# Init & update submodules.
git submodule init && git submodule update

# Build oppai-ng's binary.
cd oppai-ng && ./build && cd ..

# Install gulag's requirements.
python3.9 -m pip install -r ext/requirements.txt

# Import gulag's database structure.
# NOTE: create an empty database before doing this.
# This will also insert basic osu! channels & the bot.
mysql -u your_sql_username -p your_db_name < ext/db.sql

# Add gulag's nginx config to your nginx/sites-enabled.
# NOTE: default unix socket location is `/tmp/gulag.sock`,
# and you will have to change the certificate paths in
# the nginx config file to your own certificate paths.
sudo ln ext/nginx.conf /etc/nginx/sites-enabled/gulag.conf
sudo nginx -s reload

# Configure gulag.
cp ext/config.sample.py config.py
nano config.py

# Start the server.
./main.py
```

Directory Structure
------
    .
    ├── constants  # Code for representing gamemodes, mods, privileges, and other constants.
    ├── ext        # External files from gulag's primary operation.
    ├── objects    # Code for representing players, scores, maps, and more.
    ├── utils      # Utility functions used throughout the codebase for general purposes.
    └── domains    # The web routes available to the players.
        ├── cho    # (ce|c4|c5|c6).ppy.sh/* domains
        ├── osu    # osu.ppy.sh/* domains
        └── ava    # a.ppy.sh/* domains
