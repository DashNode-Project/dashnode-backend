.PHONY: install lint format typecheck arch test test-unit test-integration verify run migrate seed docker-up

install:
	pip install -e .[dev]

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy .

arch:
	lint-imports

test-unit:
	pytest tests/unit tests/application --cov=app --cov-fail-under=95

test-integration:
	pytest tests/integration tests/api --cov=app --cov-append

test: test-unit test-integration

verify: install lint typecheck arch test

run:
	uvicorn app.main:app --reload

migrate:
	alembic upgrade head

seed:
	python -m app.cli.seed

docker-up:
	docker compose up --build -d
