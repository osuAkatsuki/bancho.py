FROM python:3.11-slim AS python-deps

ENV PYTHONUNBUFFERED=1

WORKDIR /srv/root

RUN apt-get update && apt-get install --no-install-recommends -y \
    gcc \
    libc6-dev \
    linux-libc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install -U pip uv==0.11.23
RUN UV_PROJECT_ENVIRONMENT=/usr/local uv sync --frozen --no-install-project --inexact

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /srv/root

COPY --from=python-deps /usr/local /usr/local

RUN apt-get update && apt-get install --no-install-recommends -y \
    default-mysql-client \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# NOTE: done last to avoid re-run of previous steps
COPY . .

ENTRYPOINT [ "scripts/start_server.sh" ]
