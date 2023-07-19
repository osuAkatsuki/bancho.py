# Setting up (Docker)

for ease of use, we recommend you to use this method.

all the dependencies are all retrieved by and contained within docker containers. all you need to install on your system is docker and docker-compose, and ensure that your user is a member of the docker group. if your package manager doesn't do that for you, you may need to log out and back in.

## installing bancho.py's requirements

```sh
# install docker and docker-compose
sudo apt install -y docker \
                    docker-compose
```

## download the osu! server codebase onto your machine

```sh
# clone bancho.py's repository
git clone https://github.com/osuAkatsuki/bancho.py

# enter bancho.py's new directory
cd bancho.py
```

## configuring bancho.py

all configuration for the osu! server (bancho.py) itself can be done from the
`.env` file. we provide an example `.env.example` file which you can use as a base.

```sh
# create a configuration file from the sample provided
cp .env.example .env

# you'll want to configure *at least* the three marked (XXX) variables,
# as well as set the OSU_API_KEY if you need any info from osu!'s v1 api
# (e.g. beatmaps).

# open the configuration file for editing
nano .env
```

## congratulations! you just set up an osu! private server

if everything went well, you should be able to start your server up:

```sh
# start all containers in detached mode (running in the background)
docker-compose up -d
# done!
```

additionally, these commands could help you in case you need to know the status of the containers

```sh
# list containers
docker container ls

# fetch logs of a container
# replace <container_name> with the name of the container
# examples:
# - docker container logs banchopy-bancho-1
# - docker container logs banchopy-mysql-1
docker container logs <container_name>
```

for more information, see the [docker-cli documentation](https://docs.docker.com/engine/reference/commandline/cli/).
