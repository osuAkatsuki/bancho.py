FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /srv/root

RUN apt update && apt install --no-install-recommends -y \
    git curl build-essential=12.12 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install -U pip uv==0.8.12
RUN UV_PROJECT_ENVIRONMENT=/usr/local uv sync --frozen --no-install-project --inexact

RUN apt update && \
    apt install -y default-mysql-client redis-tools

# NOTE: done last to avoid re-run of previous steps
COPY . .

ENTRYPOINT [ "scripts/start_server.sh" ]
