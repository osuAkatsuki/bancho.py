# Setting up

## download and install the osu! server codebase onto your machine

```sh
# clone bancho.py's repository onto your machine
git clone https://github.com/osuAkatsuki/bancho.py

# enter bancho.py's new directory
cd bancho.py

# install docker for building the application image
# install docker-compose for running the application & dependencies
sudo apt install -y docker docker-compose
```

## configuring bancho.py

all configuration for the osu! server (bancho.py) itself can be done from the
`.env` file. we provide an example `.env.example` file which you can use as a base.

```sh
# create a configuration file from the sample provided
cp .env.example .env

# configure the application to your needs
# this is required to move onto the next steps
nano .env
```

## configuring a reverse proxy (we'll use nginx)

bancho.py relies on a reverse proxy for tls (https) support, and for ease-of-use
in terms of configuration. nginx is an open-source and efficient web server we'll
be using for this guide, but feel free to check out others, like caddy and h2o.

```sh
# install nginx
sudo apt install nginx

# install nginx configuration using values from your .env
./scripts/install-nginx-config.sh
```

## congratulations! you just set up an osu! private server

if everything went well, you should be able to start your server up:

```sh
# build the application
make build

# run the application
make run
```

additionally, the following commands are available for your introspection:

```sh
# run the application in the background
make run-bg

# view logs of all running containers
make logs

# run all automated tests
make test

# run formatters and linters
make lint

# run static type checking
make type-check

# all update dependencies
make update

# remove all unused dependencies
make clean
```
