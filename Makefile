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
	pipenv shell

test:
	pipenv run pytest -vv tests/

test-dbg:
	pipenv run pytest -vv --pdb tests/

lint:
	pipenv run pre-commit run --all-files

type-check:
	pipenv run mypy .

install:
	PIPENV_VENV_IN_PROJECT=1 pipenv install

install-dev:
	PIPENV_VENV_IN_PROJECT=1 pipenv install --dev
	pipenv run pre-commit install

uninstall:
	pipenv --rm

update: # THIS WILL NOT RUN ON WINDOWS DUE TO UVLOOP; USE WSL
	pipenv update --dev
	make test
	pipenv requirements > requirements.txt
	pipenv requirements --dev > requirements-dev.txt

clean:
	pipenv clean
