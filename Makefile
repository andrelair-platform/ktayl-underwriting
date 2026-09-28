.PHONY: install run test test-contract test-integration smoke lint fmt migrate

# Install the service + test/dev extras into the active environment.
install:
	pip install -e ".[test]"

# Run the API locally (uvicorn, autoreload). DATABASE_URL from env or the dev default.
run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# L1: unit tests with coverage. No Docker, no network (SQLite in-memory).
test:
	pytest tests/unit --cov --cov-report=term-missing --cov-fail-under=70

# L3: contract tests — the request the app sends vs the vendored policy-service OpenAPI, + own
# OpenAPI. No Docker, no network.
test-contract:
	pytest tests/contract -q

# L2: integration — the full flow against a REAL Postgres (testcontainers). Needs Docker; skips
# cleanly when Docker is unavailable.
test-integration:
	pytest tests/integration -q

# L4: QA-gate smoke against a RUNNING service (BASE_URL, default http://localhost:8000). Not unit CI.
smoke:
	python tests/qa/smoke.py

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
