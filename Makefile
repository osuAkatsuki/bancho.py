shell:
	pipenv shell

test:
	pipenv run pytest

lint:
	pipenv run pre-commit run --all-files

install:
	PIPENV_VENV_IN_PROJECT=1 pipenv install

install-dev:
	PIPENV_VENV_IN_PROJECT=1 pipenv install --dev
	pipenv run pre-commit install

uninstall:
	pipenv --rm

update: # THIS WILL NOT RUN ON WINDOWS DUE TO UVLOOP; USE WSL
	pipenv update --dev
	# make test ; disabled as it fails for now
	pipenv requirements > requirements.txt
	pipenv requirements --dev > requirements-dev.txt

clean:
	pipenv clean

run:
	pipenv run python main.py

run-prod:
	pipenv run ./scripts/start_server.sh

run-caddy: # Use `make run-caddy domain=<domain>`
	DOMAIN=${domain} caddy run
