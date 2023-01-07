shell:
	@pipenv shell

test:
	@pipenv run pytest

install:
	@pipenv install

install-dev:
	@pipenv install --dev

update:
	@pipenv update --dev
	@make test
	@pipenv requirements >> requirements.txt
	@pipenv requirements --dev >> requirements-dev.txt

run:
	@pipenv run python main.py
