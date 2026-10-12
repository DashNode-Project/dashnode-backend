.PHONY: install env lint format typecheck arch secrets test test-unit test-integration audit check hooks-install verify run migrate seed docker-up docker-down

install:
	pip install -e .[dev]

env:
	python scripts/generate_env.py

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy .

arch:
	lint-imports

secrets:
	python scripts/scan_secrets.py --all

test-unit:
	pytest tests/unit tests/application --cov=app --cov-fail-under=80

# Needs a reachable PostgreSQL server in TEST_POSTGRES_URL (see docs/README or .env.example).
test-integration:
	pytest tests/integration tests/api --cov=app --cov-append

test:
	pytest --cov=app --cov-fail-under=80

audit:
	pip-audit --skip-editable

check: secrets lint typecheck arch test

hooks-install:
	git config core.hooksPath .githooks

verify: install lint typecheck arch test

run:
	uvicorn app.main:app --reload

migrate:
	alembic upgrade head

seed:
	python -m app.cli.seed

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
