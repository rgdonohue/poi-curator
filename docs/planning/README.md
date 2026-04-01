# POI Curator Planning Docs

This directory defines the initial product and execution spine for the route-aware POI backend.

The core decision is fixed:

> Build a standalone service that selects places as evidence of landscape, not as generic attractions.

## Document Map

- `PRD.md`: product intent, scope, users, principles, MVP, and success measures
- `TECH_SPEC.md`: architecture, schema, ingestion, enrichment, scoring, API, and operational design
- `IMPLEMENTATION_PLAN.md`: phased roadmap, workstreams, exit criteria, and sequencing
- `TOOLING_AND_AGENTS.md`: recommended repo tooling, local/dev stack, CI, MCPs, agent roles, and Codex skills to add

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

## Immediate Next Build Sequence

1. Bootstrap the service repo and database schema.
2. Ingest Santa Fe OSM candidates into auditable raw tables.
3. Normalize and deduplicate canonical POIs.
4. Enrich with Wikidata/Wikipedia plus targeted heritage overlays.
5. Build route-aware scoring with logged factor breakdowns.
6. Add a lightweight editorial review loop before broad app integration.
