# POI Curator Planning Docs

This directory defines the product and execution spine for the route-aware POI backend. Some files
began as planning documents; where they describe future work, read them alongside the current
implementation notes in the root `README.md` and `docs/METHODOLOGY.md`.

The core decision is fixed:

> Build a standalone service that selects places as evidence of landscape, not as generic attractions.

## Document Map

- `PRD.md`: product intent, scope, users, principles, MVP, and success measures
- `TECH_SPEC.md`: architecture, schema, ingestion, enrichment, scoring, API, and operational design
- `IMPLEMENTATION_PLAN.md`: phased roadmap, workstreams, exit criteria, and sequencing
- `TOOLING_AND_AGENTS.md`: recommended repo tooling, local/dev stack, CI, MCPs, agent roles, and Codex skills to add
- `SOURCE_ECOLOGY_AND_ANCHOR_PLAN.md`: source expansion strategy, anchor reliability program, evidence schema, and phased curation roadmap

## Current Implementation Snapshot

The repository now has working implementations for most of the original MVP spine:

- FastAPI public and admin routers under `apps/api`
- Postgres/PostGIS ORM models and nine Alembic migrations
- OSM/Overpass ingestion into raw and canonical tables
- enrichment paths for Wikidata, Santa Fe City GIS, NRHP, and New Mexico HPD
- evidence, alias, theme-membership, and match-diagnostic tables
- DB-backed route and nearby scoring with fixture fallback
- grouped check-suite reports for Santa Fe route/nearby cases
- a local MapLibre map test UI at `/map-test`
- temporary frontend seed and description-enrichment exports

The main remaining gaps are hardening rather than basic scaffolding: true network detour
calculation lives outside this service, the admin UI is not yet built, local verification needs a
running PostGIS database, and lint/typecheck cleanup is still needed.

## Locked MVP Decisions

- Service boundary: standalone backend, separate from the main app
- Primary geography: Santa Fe urban area plus immediate region
- Primary sources: OSM/Overpass, Wikidata, Wikipedia, NRHP/SHPO overlays
- Storage: Postgres + PostGIS
- Ranking style: weighted, diagnosable rules with editorial overrides
- Editorial stance: humans retain final control over surfaced places
- Public categories: History, Culture, Art, Scenic, Food, Civic / Infrastructure

## Strategic Guardrails

- Do not let “POI” drift into generic commerce search.
- Do not add more datasets before ranking philosophy and review workflow stabilize.
- Do not ship black-box ranking before score diagnostics and golden-route evaluation exist.
- Do not expose raw source complexity directly to the app.

## Historical Initial Build Sequence

1. Bootstrap the service repo and database schema.
2. Ingest Santa Fe OSM candidates into auditable raw tables.
3. Normalize and deduplicate canonical POIs.
4. Enrich with Wikidata/Wikipedia plus targeted heritage overlays.
5. Build route-aware scoring with logged factor breakdowns.
6. Add a lightweight editorial review loop before broad app integration.

## Current Next Work

1. Restore clean local verification: pytest, ruff, mypy, and DB-backed check suites.
2. Keep frontend seed exports and description-enrichment artifacts reviewable and reproducible.
3. Decide whether Detour integration should use live API calls, a frozen seed export, or both.
4. Build only the admin surface needed for high-value editorial decisions.
5. Improve detour estimates only after the frontend routing provider contract is clear.

## Data Quality Governance Priorities

1. Enforce the distinctions in `docs/DATA_QUALITY_GOVERNANCE.md` across code and exports.
2. Label generated descriptions as drafts until reviewed.
3. Make fixture fallback and fixture-overlay rows visible in evaluation and handoff artifacts.
4. Add export checks for provenance, review status, claim basis, and synthetic/draft labeling.
5. Document source coverage limits whenever adding or changing a source adapter.
