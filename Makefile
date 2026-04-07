.PHONY: install db-up db-down migrate api test lint typecheck ingest-osm enrich eval-routes check-suites

install:
	python3 -m pip install -e ".[dev]"

db-up:
	docker compose up -d db

db-down:
	docker compose down

migrate:
	alembic upgrade head

api:
	uvicorn poi_curator_api.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest

lint:
	ruff check .

typecheck:
	mypy apps packages tests

ingest-osm:
	poi-curator-ingest osm --region santa-fe

enrich:
	poi-curator-enrich wikidata --region santa-fe

eval-routes:
	poi-curator-eval routes --fixtures data/fixtures/routes_santa_fe.json

check-suites:
	python3 scripts/run_check_suite.py --suite core-product --suite empty-result-guardrails
