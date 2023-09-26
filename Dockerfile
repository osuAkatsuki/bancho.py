FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /srv/root

RUN apt update && apt install --no-install-recommends -y \
    git curl build-essential=12.9 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -U pip setuptools
RUN pip install -r requirements.txt

# NOTE: done last to avoid re-run of previous steps
COPY . .

ENTRYPOINT [ "tools/start_server.sh" ]
