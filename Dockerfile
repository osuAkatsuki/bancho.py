FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /srv/root

RUN apt update && apt install --no-install-recommends -y \
    git curl build-essential=12.12 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock ./
RUN pip install -U pip poetry==2.2.1
RUN poetry config virtualenvs.create false
RUN poetry install --no-root

RUN apt update && \
    apt install -y default-mysql-client redis-tools

# NOTE: done last to avoid re-run of previous steps
COPY . .

ENTRYPOINT [ "scripts/start_server.sh" ]
