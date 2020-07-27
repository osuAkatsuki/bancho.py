# gulag - A dev-friendly osu! server (bancho & /web) written in modern python.
Looking for an easy to use, completely open-source osu! server implementation undergoing rapid development?

### There are many other osu! server implementations, what makes this any different?
Well.. Back in 2017, I decided to [start an osu! server](https://akatsuki.pw/), and as you may know, it became relatively successful.
We've always used the [Ripple](https://github.com/osuripple) source, and it's done a lot for us; we wouldn't be where we are today without it.

Of course, with any project there will be drawbacks to some of the design choices made, and different people
will value things differently; I'm not here to sell you on how much better or worse this is in comparison to
others, this is simply how my implementation turned out, with my values - give it a try and see what you actually think!

## Features:
- Written completely from the ground up, starting from a unix socket; [all parsing done by me](https://github.com/cmyui/cmyui_pkg).
- Already has (nearly) fully functional multiplayer, fully functional spectator (and all other normal bancho features) complete.
- Undergoing quite active development; the majority of the code was written in the first 8 days.
- Using very modern python (3.8) features, constantly adding more features as I learn.

## Some focuses for this project:
1. Developer sanity. Many other osu! server implementations are far too complicated for the job; either in an
   overkill sense, or sometimes through poor abstraction. With this project I aim to keep the code as simple
   and concise as possible, while still maintaining high performance in times which matter - critical loops,
   and expensive/common handlers - not all situations are created equal, and nor should they be treated this way.

## Setup
If you have any difficulties setting up gulag, you can contact me via Discord @ cmyui#0425 for support.
```sh
# Clone gulag from github.
git clone https://github.com/cmyui/gulag.gitcd gulag
cd gulag

# Install python requirements.
pip3 install -r requirements.txt

# Import the database structure.
# NOTE: create an empty database before doing this.
mysql -u your_sql_username -p your_db_name < db.sql

# Add gulag's nginx config to your nginx/sites-available.
# NOTE: default unix socket location is `/tmp/gulag.sock`.
ln gulag.conf /etc/nginx/sites-enabled/gulag.conf

# Configure gulag.
mv config.sample.py config.py
nano config.py

# Start the server.
python3.8 gulag.py
```
