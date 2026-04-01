# POI Curator

Route-aware, culturally informed POI backend.

The service is designed to answer:

> What stop along or near this route would help a traveler read the landscape more deeply?

## Current Scaffold

This repository includes:

- FastAPI application scaffold
- shared domain and scoring packages
- Postgres/PostGIS local development stack
- Alembic migration scaffold
- ingestion and enrichment CLI stubs
- unit and golden-route test skeletons
- planning docs in `docs/planning`

## Quickstart

1. Copy `.env.example` to `.env`.
2. Install dependencies:

```bash
python3 -m pip install -e ".[dev]"
```

3. Start PostGIS:

```bash
make db-up
```

4. Run migrations:

```bash
make migrate
```

5. Start the API:

```bash
make api
```

## Useful Commands

```bash
make install
make db-up
make db-down
make migrate
make api
make test
make lint
make typecheck
make ingest-osm
make enrich
```

## Repository Layout

```text
apps/api
apps/admin
packages/domain
packages/ingestion
packages/enrichment
packages/scoring
packages/editorial
tests/unit
tests/integration
tests/golden_routes
infra/docker
docs/planning
```

## Next Build Steps

- replace fixture-backed scoring with PostGIS-backed candidate retrieval
- implement OSM ingestion into raw/source-link tables
- wire enrichment jobs and signal computation
- add editor-facing review persistence
