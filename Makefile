#!/usr/bin/env make

COMPOSE = docker compose --env-file .env
TEST_COMPOSE = docker compose --env-file .env.test -f docker-compose.test.yml

.PHONY: build run run-bg run-cfd run-cfd-bg run-caddy logs shell test utest lint type-check install install-dev uninstall bump

build:
	if [ -d ".dbdata" ]; then sudo chmod -R 755 .dbdata; fi
	docker build -t bancho:latest .

run:
	$(COMPOSE) up bancho mysql redis

run-bg:
	$(COMPOSE) up -d bancho mysql redis

run-cfd:
	$(COMPOSE) -f docker-compose.cloudflared.yml up

run-cfd-bg:
	$(COMPOSE) -f docker-compose.cloudflared.yml up -d

run-caddy:
	caddy run --envfile .env --config ext/Caddyfile

last?=1
logs:
	$(COMPOSE) logs -f bancho mysql redis --tail ${last}

shell:
	uv run ${SHELL}

test:
	set -e; \
		trap '$(TEST_COMPOSE) down --volumes --remove-orphans' EXIT; \
		$(TEST_COMPOSE) up --detach --wait --wait-timeout 30 bancho-test mysql-test redis-test; \
		$(TEST_COMPOSE) exec -T bancho-test /srv/root/scripts/run-tests.sh

utest:
	uv run --frozen --env-file .env.test pytest tests/unit

lint:
	uv run pre-commit run --all-files

type-check:
	uv run mypy .

install:
	uv sync --no-install-project

install-dev:
	uv sync --no-install-project --all-groups
	uv run pre-commit install

uninstall:
	rm -rf .venv

# To bump the version number run `make bump version=<major/minor/patch>`
# (DO NOT USE IF YOU DON'T KNOW WHAT YOU'RE DOING)
# https://docs.astral.sh/uv/reference/cli/#uv-version
bump:
	uv version $(version)
