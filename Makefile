VENV := .venv
PY   := $(VENV)/bin/python
BIN  := $(VENV)/bin

.PHONY: install db-up db-down migrate api test lint typecheck ingest-osm enrich eval-routes check-suites

install:
	$(PY) -m pip install -e ".[dev]"

db-up:
	docker compose up -d db

db-down:
	docker compose down

migrate:
	$(BIN)/alembic upgrade head

api:
	$(BIN)/uvicorn poi_curator_api.main:app --reload --host 0.0.0.0 --port 8000

test:
	$(BIN)/pytest

lint:
	$(BIN)/ruff check .

typecheck:
	$(BIN)/mypy apps packages tests

ingest-osm:
	$(BIN)/poi-curator-ingest osm --region santa-fe

enrich:
	$(BIN)/poi-curator-enrich wikidata --region santa-fe

eval-routes:
	$(BIN)/poi-curator-eval routes --fixtures data/fixtures/routes_santa_fe.json

check-suites:
	$(PY) scripts/run_check_suite.py --suite core-product --suite empty-result-guardrails
