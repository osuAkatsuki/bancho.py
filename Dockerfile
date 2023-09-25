FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /srv/root

RUN apt update && apt install -y git curl build-essential=12.9

COPY requirements.txt ./
RUN pip install -U pip setuptools
RUN pip install -r requirements.txt

# NOTE: done last to avoid re-run of previous steps
COPY . .

ENTRYPOINT [ "scripts/start_server.sh" ]
