.PHONY: help install lint format test run precommit

help:
	@echo "make install|lint|format|test|run|precommit"

install:
	poetry install
	poetry run pre-commit install

lint:
	poetry run black --check .
	poetry run isort --check-only .
	poetry run flake8 .
	poetry run mypy src

format:
	poetry run isort .
	poetry run black .

test:
	poetry run pytest -q

run:
	poetry run uvicorn spectorr_backend.app:app --host 0.0.0.0 --port 8000

precommit:
	poetry run pre-commit run --all-files
