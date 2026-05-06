# POI Curator

Route-aware, culturally informed POI backend.

The service is designed to answer:

> What stop along or near this route would help a traveler read the landscape more deeply?

This repository is the curated backend for the Detour frontend mapping prototype. Detour owns
map interaction, baseline route drawing, and final rerouting through a selected stop. POI Curator
owns the harder curation problem: source discovery, normalization, evidence, editorial state,
and deterministic ranking of meaningful stops under route or nearby constraints.

Data quality is the primary project constraint. Source records, derived signals, editorial
interpretation, generated drafts, and app-facing exports must remain distinguishable. See
`docs/DATA_QUALITY_GOVERNANCE.md` before changing ingestion, enrichment, description generation,
exports, or scoring behavior.

## Current Status

This is no longer just a scaffold. The repository currently includes:

- FastAPI public and admin APIs
- Postgres/PostGIS schema with Alembic migrations
- OSM/Overpass ingestion and canonicalization pipeline
- multi-source NRHP, GNIS, NMOSE POD/acequia, and City of Santa Fe source ingestion alongside OSM
- Wikidata, City GIS, NRHP, and New Mexico HPD enrichment paths
- evidence, alias, diagnostic, field-provenance, match-log, query-log, and theme-membership tables
- deterministic route and nearby scoring with score breakdowns
- editorial mutation paths for review state, aliases, match diagnostics, and theme overrides
- fixture fallback scoring for tests and local API resilience
- grouped check-suite runner and saved Santa Fe QA reports
- local MapLibre map tester served at `/map-test`
- minimal read-only admin viewer served at `/admin`
- temporary frontend seed and description-enrichment export workflow

The current reference geography is Santa Fe. The implemented public categories are `history`,
`culture`, `art`, `scenic`, `food`, `civic`, and `mixed`. Query-active themes are `water` and
`rail`; `public_memory` is modeled but intentionally not public-query-active yet.

## Quickstart

1. Copy `.env.example` to `.env`.
2. Create or activate a Python environment, then install dependencies:

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

6. Open the map tester:

```text
http://localhost:8000/map-test
```

The tester is served by the same FastAPI app and talks to the local backend on the same origin, so no extra frontend config is required. It uses MapLibre GL JS plus OpenStreetMap raster tiles from public CDNs.

## Public API Shape

The frontend-facing API is under `/v1`:

- `GET /v1/health`: service health and scoring profile version
- `GET /v1/config`: supported region, categories, detour defaults, scoring profile
- `GET /v1/categories`: public category metadata
- `POST /v1/route/suggest`: rank stops near a supplied route geometry
- `POST /v1/nearby/suggest`: rank stops near a center point
- `POST /v1/point/suggest`: compatibility wrapper around nearby suggestions
- `GET /v1/poi/{poi_id}`: detail, evidence, themes, provenance, and extended place context

Admin-only endpoints expose POI inventory, map features, detail views, source conflicts, per-field
provenance, coverage counts, match logs, query logs, diagnostics, aliases, and theme-review
workflows for curation review. Mutating review actions are API-backed; the browser admin viewer is
currently read-only.

The backend does not compute turn-by-turn route geometry. For route suggestions it estimates
detour cost geometrically from the supplied route and POI anchor. A frontend or routing provider
should still compute the actual baseline route and actual route-through-stop geometry.

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
.venv/bin/poi-curator-ingest nrhp --region santa-fe
.venv/bin/poi-curator-ingest gnis --region santa-fe
.venv/bin/poi-curator-ingest sf-historic-districts --region santa-fe
.venv/bin/poi-curator-enrich city-gis --region santa-fe
.venv/bin/poi-curator-enrich nrhp --region santa-fe
.venv/bin/poi-curator-enrich state-register --region santa-fe
.venv/bin/python scripts/run_check_suite.py --suite core-product
```

Commands that hit the database require PostGIS on `localhost:5432` unless `POI_CURATOR_DATABASE_URL`
points elsewhere.

## Check Suite Runner

For grouped review output, use the Python suite runner on top of `poi-curator-check`:

```bash
.venv/bin/python scripts/run_check_suite.py --list-suites
.venv/bin/python scripts/run_check_suite.py --suite rail-smoke
.venv/bin/python scripts/run_check_suite.py --suite core-product --suite empty-result-guardrails --split-cases
```

It writes timestamped grouped outputs under `reports/check_runs/<timestamp>/`:

- one JSON report per suite
- one Markdown report per suite
- an `index.md` summary across the suite run
- optional per-case JSON and Markdown files with `--split-cases`

The latest committed full Santa Fe validation report after the GNIS/NMOSE source sprint is:

```text
reports/check_runs/20260502T_gnis_nmose_baseline/index.md
```

It records 28 passing case runs across `core-product`, `all-fixtures`,
`empty-result-guardrails`, and `rail-smoke`, with source-corpus drift documented in `REVIEW.md`.
Saved reports are artifacts, not proof of the current working tree; rerun the suite locally before
claiming a branch is clean.

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

Notable entry points:

- `apps/api/poi_curator_api/main.py`: FastAPI application factory
- `apps/api/poi_curator_api/routes/public.py`: frontend-facing API
- `apps/api/poi_curator_api/routes/admin.py`: editor/admin API
- `packages/domain/poi_curator_domain/db.py`: SQLAlchemy/PostGIS ORM model
- `packages/ingestion/poi_curator_ingestion/pipeline.py`: OSM ingest/canonicalization
- `packages/ingestion/poi_curator_ingestion/matching.py`: source-to-canonical matching
- `packages/ingestion/poi_curator_ingestion/sources`: NRHP, GNIS, NMOSE, and City GIS source adapters
- `packages/enrichment/poi_curator_enrichment/pipeline.py`: enrichment and evidence rollup
- `packages/scoring/poi_curator_scoring/query_service.py`: DB-backed query service
- `packages/scoring/poi_curator_scoring/backend.py`: hybrid DB/fixture scoring backend
- `scripts/run_check_suite.py`: grouped evaluation report runner

## Map Test UI

The repository now includes a minimal local testing interface at `/map-test` for:

- nearby suggestion testing from a clicked map center
- manual or sample route suggestion testing
- category and active theme filters (`water`, `rail`)
- score, explanation, badge, and POI detail inspection on a map

## Admin Viewer

The repository includes a minimal no-build admin viewer at `/admin` for curation review:

- POI list filtering by category, review state, source, theme, diagnostics, editorial overrides,
  active-only state, and free text
- POI detail inspection with canonical fields, editorial badges, aliases, evidence, themes, match
  diagnostics, external links, and a small map
- map browsing through `GET /v1/admin/pois/map`
- query-log browsing when `POI_CURATOR_QUERY_LOGGING=true`
- health/config inspection, including the current scoring source

Set `POI_CURATOR_ADMIN_KEY` and provide it in the viewer settings. The UI stores the key in
`localStorage` and sends it as `X-POI-Curator-Admin-Key`.

The viewer is intentionally read-only for now. Editorial mutation, alias creation, diagnostic
resolution, theme review, and ingest actions remain API/editorial-service workflows.

## Frontend Seed and Description Workflow

The repo includes a temporary export path for the Detour frontend seed inventory:

- `reports/query_capable_pois_frontend_seed.csv`: merged query-capable seed
- `reports/query_capable_pois_frontend_seed_described_v1.csv`: deterministic evidence-weighted
  description pass
- `docs/DESCRIPTION_ENRICHMENT_WORKFLOW.md`: optional extractor/writer/critic workflow for
  conservative description drafting
- `scripts/generate_frontend_seed_descriptions.py`: deterministic description generator

This workflow does not overwrite canonical POI descriptions. Treat these exports as handoff/review
artifacts until reviewed. Generated descriptions are drafts, not source data and not canonical
historical/cultural facts.

## Current Gaps

- True network detour calculation is still outside this backend.
- Admin viewer coverage is intentionally pragmatic and read-only; deeper resolution workflows remain
  API/editorial-service work.
- Admin ingest trigger/status endpoints are scaffold responses, not real job orchestration.
- Wikipedia extract hydration is still a placeholder.
- Santa Fe is the only actively modeled reference region.
- Local check suites require a running PostGIS database.
- The temporary description-enrichment scripts/reports are generated handoff artifacts.

## Governance Docs

- `docs/DATA_QUALITY_GOVERNANCE.md`: data classes, synthetic data policy, source-bias caveats,
  export governance, and review roadmap
- `docs/METHODOLOGY.md`: implemented source, processing, scoring, and review methodology
- `docs/SOURCES.md`: source URLs, scope, licensing notes, mappings, and match strategy notes
- `docs/PROVENANCE_MODEL.md`: field provenance schema and conflict policy
- `docs/DESCRIPTION_ENRICHMENT_WORKFLOW.md`: temporary generated-description workflow and review
  constraints

## Related Work

[OpenPOIs](https://openpois.org/) is a complementary national spatial-spine project that conflates OSM and Overture Maps with confidence/staleness scoring; POI Curator's role is the editorial, provenance, and interpretive layer above that kind of spine.
