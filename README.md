# gulag - A dev-friendly osu! server written in modern python.

Looking for an easy to use, completely open-source osu! server implementation undergoing rapid development?

## There are many other osu! server implementations, what makes this any different?

Well.. Back in 2017, I decided to [start an osu! server](https://akatsuki.pw), and as you may know, it became relatively successful.
We've always used the [Ripple](https://github.com/osuripple) source, and it's great; however, it's quite different from my programming style.

All projects will have their flaws, and while I now heavily prefer working with this server over any other, you may see things in another way.
This is simply the result of my programming values and time thrown together; I'd recommend you try gulag out and see what you actually think!

### Features

- Fully functional multiplayer, spectator, leaderboards, score submission, and most other features of an osu! server.
- Undergoing active development; an osu! server has always been a large goal of mine, so motivation is very high.
- Clean and concise code, easy to make small modifications & add to the codebase; designed around this idea.

### Project focuses & goals

1. Developer sanity. Many other osu! server implementations are far too complicated for the job; either in an
   overkill sense, or sometimes through poor abstraction. With this project I aim to keep the code as simple
   and concise as possible, while still maintaining high performance in times which matter - critical loops,
   and expensive/common handlers - not all situations are created equal, and nor should they be treated this way.

## Setup

Setup is pretty simple, install mysql & nginx if you haven't already, and the commands below should basically be pastable.

If you have any difficulties setting up gulag, you can contact me via Discord @ cmyui#0425 for support.

```sh
# Clone gulag from github.
git clone https://github.com/cmyui/gulag.git
cd gulag

# Install pipenv and requirements.
python3 -m pip install pipenv --user
python3 -m pipenv install

# Import the database structure.
# NOTE: create an empty database before doing this.
# This will also insert basic osu! channels & the bot.
mysql -u your_sql_username -p your_db_name < db.sql

# Add gulag's nginx config to your nginx/sites-available.
# NOTE: default unix socket location is `/tmp/gulag.sock`.
ln nginx.conf /etc/nginx/sites-enabled/gulag.conf

# Reload nginx after adding new config.
nginx -s reload

# Configure gulag.
mv config.sample.py config.py
nano config.py

# Start the server.
python3.8 gulag.py
```
