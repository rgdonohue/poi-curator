# Agent Operating Notes

This repository is the curated backend for the Detour mapping prototype. It is a Santa Fe-first
FastAPI/PostGIS service for source-aware POI curation and route-aware stop suggestions.

Read `docs/DATA_QUALITY_GOVERNANCE.md` before changing ingestion, enrichment, scoring, exports, or
description generation. Data quality and transparent provenance are stronger requirements than
surface-level feature completeness.

## Project Posture

- Do not treat this as a generic nearby-search or attractions project.
- The central product question is: what route-plausible stop helps a traveler read the landscape
  more deeply?
- Preserve the split between slow source work and fast runtime queries.
- Prefer explicit evidence, deterministic scoring, diagnostics, and editorial state over opaque
  ranking or invented narrative.
- Santa Fe-specific heuristics are acceptable when they are named and isolated.
- Generated text is never canonical data until reviewed.
- Synthetic data belongs only in tests, fixtures, mocks, or clearly labeled drafts.

## Current Architecture

- `apps/api`: FastAPI app, public routes, admin routes, static map tester.
- `packages/domain`: schemas, settings, category/theme definitions, SQLAlchemy/PostGIS models.
- `packages/ingestion`: OSM/Overpass source fetch, normalization, canonical POI upsert, audit.
- `packages/enrichment`: Wikidata, Santa Fe City GIS, NRHP, New Mexico HPD, evidence rollup.
- `packages/scoring`: fixture scoring, DB-backed scoring, route/nearby evaluation, check suites.
- `packages/editorial`: admin mutation services for aliases, diagnostics, and theme review.
- `migrations/versions`: Alembic schema history.
- `data/fixtures`: route/evaluation/source fixtures.
- `reports`: generated QA and frontend handoff artifacts.

## Runtime Contract

The frontend-facing API lives under `/v1`:

- `GET /health`
- `GET /config`
- `GET /categories`
- `POST /route/suggest`
- `POST /nearby/suggest`
- `POST /point/suggest`
- `GET /poi/{poi_id}`

Route suggestions consume a supplied route `LineString`. This backend estimates detour/access cost
geometrically; it does not compute turn-by-turn route geometry or replace a routing provider.

## Data And Curation Rules

- Raw source rows belong in `poi_source_raw`; source adapters should not write directly to `poi`.
- Canonical POIs keep geometry, centroid, public category, secondary categories, flags, scores, and
  provenance.
- Enrichment adds evidence and signals. It should not silently overwrite stronger identity or
  editorial decisions.
- Official register/GIS evidence is corroboration, not permission to invent dates, actors, or
  community claims.
- Description generation for frontend seed files is temporary and should stay outside canonical
  database descriptions until reviewed.
- Derived signals such as quality, significance, and interpretive value are review aids, not
  objective measures of cultural worth.
- Query-active themes are currently `water` and `rail`. `public_memory` is modeled but not active
  for public query use.

## Local Commands

Use the virtualenv when present:

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/mypy apps packages tests
.venv/bin/alembic upgrade head
.venv/bin/poi-curator-ingest osm --region santa-fe
.venv/bin/poi-curator-enrich wikidata --region santa-fe
.venv/bin/python scripts/run_check_suite.py --suite core-product
```

Database-backed commands require PostGIS on `localhost:5432` by default. Start it with:

```bash
make db-up
make migrate
```

Start the API with:

```bash
make api
```

Then open:

```text
http://localhost:8000/map-test
```

## Verification Notes

- The unit suite includes fixture-backed API tests and DB integration tests that skip when PostGIS
  is unavailable.
- `scripts/run_check_suite.py` uses the hybrid scoring backend and a real DB session. Expect it to
  fail if PostGIS is not running.
- Saved historical check outputs live under `reports/check_runs/`; do not confuse them with a fresh
  local verification run.
- Before claiming the project is clean, run pytest, ruff, mypy, and the relevant check suite.

## Editing Guidance

- Keep API routers thin; business logic belongs in domain, scoring, ingestion, enrichment, or
  editorial packages.
- Keep schema changes in Alembic migrations and ORM models together.
- Use structured JSON/CSV readers for generated artifacts; avoid ad hoc parsing when the standard
  library can parse the format.
- Do not bulk rewrite generated reports unless the task is explicitly about regenerating them.
- Do not remove untracked or modified report/script/doc files without explicit instruction; this
  repo often has local handoff artifacts in progress.
- Do not introduce synthetic POIs, synthetic evidence, or generated historical facts into corpus
  outputs.
- Keep documentation honest about current limitations, especially detour estimation, admin UI state,
  and local database requirements.

## Useful Documentation

- `README.md`: current project overview and quickstart.
- `docs/DATA_QUALITY_GOVERNANCE.md`: data-quality doctrine, synthetic data policy, source-bias
  caveats, and export governance.
- `docs/METHODOLOGY.md`: implemented methodology and operating workflow.
- `docs/DESCRIPTION_ENRICHMENT_WORKFLOW.md`: temporary frontend description workflow.
- `docs/planning/PRD.md`: product intent and guardrails.
- `docs/planning/TECH_SPEC.md`: architecture and schema reference.
- `docs/planning/IMPLEMENTATION_PLAN.md`: phase plan plus current status.
- `docs/planning/TOOLING_AND_AGENTS.md`: tooling and agent collaboration notes.
