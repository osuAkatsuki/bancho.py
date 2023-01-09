shell:
	pipenv shell

test:
	pipenv run pytest

install:
	PIPENV_VENV_IN_PROJECT=1 pipenv install

install-dev:
	PIPENV_VENV_IN_PROJECT=1 pipenv install --dev

uninstall:
	pipenv --rm

update:
	pipenv update --dev
	make test
	pipenv requirements > requirements.txt
	pipenv requirements --dev > requirements-dev.txt

clean:
	pipenv clean

run:
	pipenv run python main.py

run-prod:
	pipenv run ./scripts/start_server.sh
