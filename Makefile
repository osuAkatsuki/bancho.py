build:
	if [ -d ".dbdata" ]; then sudo chmod -R 755 .dbdata; fi
	docker build -t bancho:latest .

run:
	docker-compose up bancho mysql redis

run-bg:
	docker-compose up -d bancho mysql redis

run-caddy:
	caddy run --envfile .env --config ext/Caddyfile

logs:
	docker-compose logs -f bancho mysql redis

shell:
	poetry shell

test:
	docker-compose -f docker-compose.test.yml up -d bancho mysql redis
	docker-compose -f docker-compose.test.yml exec -T bancho /srv/root/scripts/run-tests.sh

test-local:
	poetry run pytest -vv tests/

test-dbg:
	poetry run pytest -vv --pdb -s tests/

lint:
	poetry run pre-commit run --all-files

type-check:
	poetry run mypy .

install:
	POETRY_VIRTUALENVS_IN_PROJECT=1 poetry install --no-root

install-dev:
	POETRY_VIRTUALENVS_IN_PROJECT=1 poetry install --no-root --with dev
	poetry run pre-commit install

uninstall:
	poetry env remove python

# To bump the version number run `make bump version=<major/minor/patch>`
# (DO NOT USE IF YOU DON'T KNOW WHAT YOU'RE DOING)
# https://python-poetry.org/docs/cli/#version
bump:
	poetry version $(version)
