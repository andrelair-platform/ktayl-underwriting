.PHONY: install run test lint fmt migrate

# Install the service + test/dev extras into the active environment.
install:
	pip install -e ".[test]"

# Run the API locally (uvicorn, autoreload). DATABASE_URL from env or the dev default.
run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# L1: unit tests with coverage. No Docker, no network (SQLite in-memory).
test:
	pytest --cov --cov-report=term-missing --cov-fail-under=70

# L0: static gate — ruff (lint) + mypy (types).
lint:
	ruff check .
	mypy .

# Auto-fix formatting + lint.
fmt:
	ruff format .
	ruff check --fix .

# Apply DB migrations (needs DATABASE_URL pointing at a real Postgres).
migrate:
	alembic upgrade head
