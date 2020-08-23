# A dev-friendly osu! server written in modern python

Looking for an easy to use, async & completely open-source osu! server implementation undergoing rapid development?

## There are many other osu! server implementations, what makes this any different?

Well.. Back in 2017, I decided to [start an osu! server](https://akatsuki.pw), and as you may know, it became relatively successful.
We've always used the [Ripple](https://github.com/osuripple) source, and it's great; however, it's quite different from my programming style.

All projects will have their flaws, and while I now heavily prefer working with this server over any other, you may see things in another way.
This is simply the result of my programming values and time thrown together; I'd recommend you try gulag out and see what you actually think!

### Features

- Asynchronous server design, allowing for high efficiency along with many cool features unavailable on most other servers.
- Fully functional multiplayer, spectator, leaderboards, score submission, osu!direct and most other features that you'd expect.
- Undergoing active development; an osu! server has always been a large goal of mine, so motivation is very high.
- Clean and concise code, easy to make small modifications & add to the codebase; designed around this idea.

### Project focuses & goals

1. Developer sanity. Many other osu! server implementations are far too complicated for the job; either in an
   overkill sense, or sometimes through poor abstraction. With this project I aim to keep the code as simple
   and concise as possible, while still maintaining high performance in times which matter (critical loops,
   common/expensive handlers, etc.).

   Developing features for the server should be an enjoyable and thought-provoking experience of finding new ideas;
   when the codebase makes that difficult, programming loses the aspect of fun and everything becomes an activity
   that requires effort - I'm trying my best to never let this code get to that state.

## Setup

Setup is pretty simple, the commands below should basically be copy-pastable.

If you have any difficulties setting up gulag, you can contact me via Discord @ cmyui#0425 for support.

```sh
# Install our database & reverse proxy, if not already installed.
sudo apt install mysql-server nginx

# Clone gulag from github.
git clone https://github.com/cmyui/gulag.git
cd gulag

# Create empty data directories.
mkdir certs screenshots replays logs pp/maps mapsets

# Install pipenv and requirements.
python3.8 -m pip install pipenv --user
python3.8 -m pipenv install

# Import the database structure.
# NOTE: create an empty database before doing this.
# This will also insert basic osu! channels & the bot.
mysql -u your_sql_username -p your_db_name < db.sql

# Create certificate.
# When filling this out, set 'Common Name' to '*.ppy.sh', the rest are unimportant.
# You'll need to install this on windows like after creating it.
# You'll also need to edit nginx.conf's certificate paths to the ones created here.
openssl req -newkey rsa:4096 -x509 -sha256 -days 3650 -nodes -out certs/server.crt -keyout certs/server.key

# Edit the nginx config to match the path of the cert and key you created.
nano nginx.conf

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
