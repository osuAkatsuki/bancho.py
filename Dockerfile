FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /srv/root

COPY . /srv/root

# install apps dependencies
RUN apt update && apt install -y git curl build-essential=12.9

# install python dependencies
COPY Makefile Pipfile Pipfile.lock ./
RUN pip install -U pip setuptools pipenv
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install

# create data directory
RUN mkdir /home/bpyuser/.data

# copy the source code in last, so that it doesn't
# repeat the previous steps for each change
COPY . .

# start bancho.py
ENTRYPOINT [ "/scripts/start_server.sh" ]
