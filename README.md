[![Discord](https://discordapp.com/api/guilds/748687781605408908/widget.png?style=shield)](https://discord.gg/ShEQgUx)

# A dev-friendly osu! server written in modern python

Looking for a well-organized, async & completely open-source osu! server implementation undergoing rapid development?

Disclaimer: this is NOT a finished project; developement is underway, but the server will not be finished for a bit to come; probably about 80% of the way.

## There are many other osu! server implementations, what makes this any different?

Well.. Back in 2017, I decided to [start an osu! server](https://akatsuki.pw), and as you may know, it became relatively successful.
We've always used the [Ripple](https://github.com/osuripple) source, and it's great; however, it's quite different from my programming style.

All projects will have their flaws, and while I now heavily prefer working with this server over any other, you may see things in another way.
This is simply the result of my programming values and time thrown together; I'd recommend you try gulag out and see what you actually think!

### Features

- Asynchronous server design, allowing for high efficiency along with many cool features unavailable on many other implementations.
- Nearly full completion of multiplayer, spectator, leaderboards, score submission, osu!direct and most other features that you'd expect.
- A strong focus on keeping an accurate cache for many things (maps [with pp values], osu! updates, many more to come..) allowing for quick responses.
- Undergoing active development; an osu! server has always been a large goal of mine, so motivation is very high.
- Clean and concise code, easy to make small modifications & add to the codebase; designed around this idea.

### Project focuses & goals

1. A focus on the developer. Many other osu! server implementations are far too complicated for the job, either in an
   'overkill' sense, or through poor abstraction. With this project I aim to keep the code as simple and concise as
   possible, while still maintaining high performance and providing an accurate representation of osu!'s protocol.

   Developing features for the server should be an enjoyable and thought-provoking experience of finding new ideas;
   when the codebase makes that difficult, programming loses the aspect of fun and everything becomes an activity
   that requires effort - I'm trying my best to never let this code get to that state, as it's mostly what drove me to
   start this project to begin with.

## Requirements

- MySQL & Nginx (both installed in setup below)
- Some know-how with Linux (tested on Ubuntu 18.04), python, and general-programming knowledge.
- An osu! account (or more specifically, an osu! api key). This is technically optional, but is required for full feature-set.

## Setup

Setup is relatively simple, the commands below should basically be copy-pastable.

If you have any difficulties setting up gulag, feel free to join the Discord server at the top of the README, we now have a bit of a community!

NOTE: I will not be able to help you out with creating a certificate to connect on the latest osu! versions.

```sh
# Install our database & reverse proxy, if not already installed.
sudo apt install mysql-server nginx

# Clone gulag from github.
git clone https://github.com/cmyui/gulag.git
cd gulag

# Create empty data directories.
mkdir screenshots replays logs mapsets avatars pp/maps

# Install project requirements.
python3.8 -m pip install -r requirements.txt

# Import the database structure.
# NOTE: create an empty database before doing this.
# This will also insert basic osu! channels & the bot.
mysql -u your_sql_username -p your_db_name < db.sql

# Add gulag's nginx config to your nginx/sites-enabled.
# NOTE: default unix socket location is `/tmp/gulag.sock`.
sudo ln nginx.conf /etc/nginx/sites-enabled/gulag.conf

# Reload nginx to put the reverse proxy online.
sudo nginx -s reload

# Configure gulag.
mv config.sample.py config.py
nano config.py

# Start the server.
python3.8 main.py
```
