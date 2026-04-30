# Tooling and Agent Operations

## Current Engineering Stack

### Language and framework

- Python 3.12+ project metadata; the local reviewed environment was running Python 3.14
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x + GeoAlchemy2
- `psycopg`

### Spatial/data libraries

- Postgres 16 + PostGIS 3.x
- Shapely
- PyProj
- `orjson` for fast JSON serialization
- `httpx` for source fetches

### Job and CLI layer

- Typer for job commands
- external scheduler first: cron, hosted scheduler, or CI-based scheduled runs
- no embedded scheduler in the web process

### Quality and developer workflow

- `pytest`
- `testcontainers` for PostGIS integration tests
- `ruff`
- `mypy`
- `pre-commit`
- `.env` management plus a typed settings layer

As of the latest repository review, tests, lint, and typecheck are configured but not all clean.
Do not describe the repository as fully green without rerunning the commands locally.

### Optional later additions

- OpenTelemetry for traces
- Prometheus-compatible metrics
- lightweight admin frontend with React if CSV/admin endpoints prove insufficient

## Recommended Monorepo Shape

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
data/fixtures
infra/docker
docs/planning
```

This layout maps cleanly onto parallel agent work and keeps the route-scoring core insulated from API churn.

## Local Environment

### Minimum setup

- Docker Compose for Postgres/PostGIS
- `make install`
- Alembic migrations through `make migrate`
- local `.env.example`

### Standard commands

- `make db-up`
- `make db-down`
- `make migrate`
- `make api`
- `make test`
- `make lint`
- `make typecheck`
- `make ingest-osm`
- `make enrich`
- `make check-suites`
- `.venv/bin/python scripts/run_check_suite.py --suite core-product`

Database-backed commands need PostGIS running on `localhost:5432` unless
`POI_CURATOR_DATABASE_URL` is overridden.

## CI/CD Recommendation

### Continuous integration

Run on every PR:

- lint
- type checks
- unit tests
- integration tests against ephemeral PostGIS
- golden-route regression tests

This is still a recommendation. The local project already has the command surface and tests, but
the current working state needs cleanup before these checks can serve as a clean release gate.

### Continuous delivery

For MVP keep deployment simple:

- build one API image
- build one jobs image or reuse same image with different entrypoints
- deploy migrations separately from app startup

## Source Operations

### OSM / Overpass

- use bounded regional queries only
- snapshot representative payload fixtures into tests
- record query definitions as versioned files

### Wikidata / Wikipedia

- isolate fetch and match logic from canonical schema updates
- store confidence on matches
- cache enrichment results to avoid repeat fetch cost

### Heritage overlays

- treat as partial, high-trust overlays
- preserve source metadata and load date
- never let absence imply insignificance

## Evaluation Tooling

The project needs evaluation infrastructure almost as much as it needs source connectors.

### Implemented now

- golden-route fixtures
- grouped check suites through `scripts/run_check_suite.py`
- per-suite JSON and Markdown reports under `reports/check_runs/`
- route and nearby cases over `data/fixtures/eval_santa_fe.json`
- expectation-based pass/fail checks

### Still useful

- `scripts/compare_scoring_profiles.py`
- `scripts/export_review_queue.py`
- `scripts/import_editorial_decisions.py`
- reviewer outcome capture for surfaced results
- scoring profile diff reports

## MCP Recommendations

The project will benefit from a few high-value MCP servers or equivalent interfaces.

### Set up early

- GitHub MCP: PR review, issue triage, CI status, and release workflow
- Postgres/PostGIS MCP: inspect schema, run safe read-only spatial queries, debug performance
- Filesystem/project MCP: code and fixture inspection
- Browser/fetch MCP: source docs and data portal verification when adapters change

### Add when admin UI begins

- Playwright/browser automation MCP for regression checks on the review UI

### Consider building later as project-specific MCPs

- `poi-diagnostics-mcp`: inspect a POI, its source links, signals, and score history in one call
- `scoring-eval-mcp`: run a route fixture against multiple scoring profiles and summarize deltas
- `source-catalog-mcp`: list source datasets, license metadata, freshness, and ingest status

Custom MCPs are valuable after the domain stabilizes, not before.

## Recommended Codex Skills To Add

This project is specialized enough to justify custom local skills.

### High-value skills

- `overpass-ingestion`: query patterns, rate-limit guidance, raw-to-canonical rules
- `wikidata-enrichment`: entity matching heuristics, class normalization, confidence rules
- `postgis-route-ranking`: spatial query patterns, explain-plan checklist, indexing guidance
- `editorial-review`: suppression standards, tone guardrails, false-positive taxonomy
- `dataset-provenance`: license handling, attribution, freshness and audit practices

### Why skills matter here

They reduce repeated prompt overhead and enforce domain-specific discipline in a codebase where bad assumptions can quietly corrupt the corpus.

## Agent Strategy

Use agents for bounded, disjoint tasks. Do not parallelize coupled edits in the same modules.

### Good parallel slices

- source adapter implementation vs scoring test harness
- taxonomy mapping updates vs admin API scaffolding
- golden-route fixture authoring vs observability setup

### Suggested agent roles

- explorer: inspect source schemas, docs, and existing fixtures
- worker: implement ingestion adapters
- worker: implement normalization and taxonomy mapping
- worker: implement scoring profiles and diagnostics
- worker: implement admin review endpoints/UI
- explorer: review spatial indexes and slow-query plans

### Ownership guidance

- `packages/ingestion`: ingestion worker
- `packages/enrichment`: enrichment worker
- `packages/scoring` and `tests/golden_routes`: scoring worker
- `apps/api` and `packages/domain`: platform worker
- `apps/admin` and editorial APIs: editorial tooling worker
- `docs`, `reports`, and `scripts`: documentation/export worker, with care not to overwrite
  generated handoff artifacts unless regeneration is the explicit task

## Logging and Diagnostics Standards

Every route suggestion should be traceable back to:

- scoring profile version
- filter counts
- selected candidate IDs
- factor breakdown for returned results
- provenance for displayed source-backed claims

Every ingest run should record:

- source
- time window
- query definition/version
- raw count
- canonical insert/update counts
- errors and skipped records

## Documentation Standards

Keep four document classes current:

- product intent
- technical architecture
- runbooks
- scoring profile change logs

Also keep `AGENTS.md` current. It is the shortest source of operational guidance for future coding
agents and should reflect actual command behavior, DB requirements, and current limitations.

Keep `docs/DATA_QUALITY_GOVERNANCE.md` current as the canonical governance layer. Any workflow
that creates exports, generated descriptions, or source-derived evidence should state how it
preserves provenance, draft status, and review state.

Scoring changes should be accompanied by:

- rationale
- affected categories/modes
- golden-route deltas
- reviewer notes if any

Export or description-generation changes should be accompanied by:

- whether generated text is present
- how generated text is labeled as draft or approved
- how claim basis is represented
- whether fixture-overlay rows are included
- source coverage or bias caveats affected by the change

## Historical First Setup Checklist

1. Create repo scaffold and `docs/planning`.
2. Add Docker Compose for PostGIS.
3. Add migrations, lint, type-check, and pytest setup.
4. Add fixture directories and golden-route test harness.
5. Configure GitHub CI for lint/test/golden routes.
6. Set up GitHub and Postgres MCP access.
7. Add custom Codex skills once source adapters and scoring patterns begin repeating.

## Strategic Rule

Optimize the build system for inspectability, not just speed. This project will succeed or fail based on whether humans can understand why a place was chosen, why another was not, and how to improve that outcome without guesswork.
