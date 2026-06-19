#!/usr/bin/env make

build:
	if [ -d ".dbdata" ]; then sudo chmod -R 755 .dbdata; fi
	docker build -t bancho:latest .

run:
	docker compose up bancho mysql redis

run-bg:
	docker compose up -d bancho mysql redis

run-cfd:
	docker compose -f docker-compose.cloudflared.yml up

run-cfd-bg:
	docker compose -f docker-compose.cloudflared.yml up -d

run-caddy:
	caddy run --envfile .env --config ext/Caddyfile

last?=1
logs:
	docker compose logs -f bancho mysql redis --tail ${last}

shell:
	uv run ${SHELL}

test:
	docker compose -f docker-compose.test.yml up -d bancho-test mysql-test redis-test
	docker compose -f docker-compose.test.yml exec -T bancho-test /srv/root/scripts/run-tests.sh

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
