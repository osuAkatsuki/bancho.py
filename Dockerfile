FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /srv/root

RUN apt update && apt install --no-install-recommends -y \
    git curl build-essential=12.9 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -U pip setuptools poetry
RUN poetry config virtualenvs.create false
RUN poetry install --no-root

# NOTE: done last to avoid re-run of previous steps
COPY . .

ENTRYPOINT [ "scripts/start_server.sh" ]
