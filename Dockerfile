FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /srv/root

RUN apt update && apt install -y git curl build-essential=12.9

COPY Makefile Pipfile Pipfile.lock ./
RUN pip install -U pip setuptools pipenv
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install

RUN mkdir /home/bpyuser/.data

# NOTE: done last to avoid re-run of previous steps
COPY . .

ENTRYPOINT [ "/scripts/start_server.sh" ]
