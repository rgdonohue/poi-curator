# Implementation Plan

## Delivery Strategy

Build the service as a sequence of narrow, testable layers. Do not try to solve discovery, enrichment, ranking, editorial tooling, and app integration simultaneously.

The implementation program should be organized across four workstreams:

- platform foundation
- data acquisition and normalization
- scoring and evaluation
- editorial operations and integration

## Phase 0: Foundation

### Objective

Stand up the repo, database, core schema, and basic fixtures so later work is grounded in real contracts rather than notebooks or ad hoc scripts.

### Deliverables

- repo scaffold and local dev environment
- Docker Compose with Postgres + PostGIS
- migration system and initial schema
- domain enums and category map
- seed data fixture set
- scoring stub with deterministic output
- baseline golden-route fixture format

### Exit criteria

- a developer can boot the stack locally in one command
- schema migrations run cleanly from zero
- a sample `POST /v1/route/suggest` request returns fixture-backed data

### Risks

- overbuilding abstractions before real source data exists
- spending too long on admin UI before core logic stabilizes

## Phase 1: OSM Discovery and Canonicalization

### Objective

Build candidate discovery for Santa Fe and normalize it into canonical POIs.

### Deliverables

- Overpass extraction job for Santa Fe region
- raw source ingestion into `poi_source_raw`
- source provenance model and ingest run tracking
- taxonomy mapping for MVP categories
- canonical `poi` creation flow
- initial dedupe heuristics and manual-review flags

### Exit criteria

- at least 500 candidate records imported for Santa Fe region
- canonical POI table populated with reviewable records
- generic business noise materially reduced by normalization and filtering

### Risks

- OSM tag chaos
- duplicate collapse errors
- early temptation to overfit the taxonomy

## Phase 2: Enrichment Layer

### Objective

Improve identity, type confidence, and interpretive context without pretending enrichment solves editorial judgment.

### Deliverables

- Wikidata linking flow
- Wikipedia extract enrichment
- NRHP/SHPO overlay import
- `poi_signals` computation
- confidence scoring for type and source agreement

### Exit criteria

- meaningful share of strong candidates linked to at least one enrichment source
- derived signals recompute cleanly from canonical data
- enrichment never blocks route queries when absent

### Risks

- sparse or noisy matches
- brittle name-based linking
- overtrusting article existence as significance

## Phase 3: Route-Aware Ranking

### Objective

Turn the data spine into a useful service by ranking candidates against real route geometry and detour budgets.

### Deliverables

- corridor selection query path
- distance-from-route and detour calculations
- weighted scoring profiles for driving and walking
- top-N suggestion endpoint
- factor breakdown diagnostics
- golden-route evaluation harness

### Exit criteria

- route suggestions return within target latency on Santa Fe-scale data
- scoring changes can be regression-tested against golden routes
- at least 50 curated route cases reviewed internally

### Risks

- detour math oversimplified enough to mis-rank candidates
- weighting brittleness
- route explanations sounding generic or inflated

## Phase 4: Editorial Workflow

### Objective

Create a low-friction way for humans to shape the corpus and correct the ranking.

### Deliverables

- review queue for `needs_review`
- approve, suppress, feature, and boost actions
- title, description, and category overrides
- duplicate merge tooling
- admin diagnostics showing provenance and score breakdowns

### Exit criteria

- reviewers can process candidates without database access
- 100 to 250 reviewed POIs exist for Santa Fe
- suppressed junk stays suppressed across recomputes

### Risks

- review tooling too slow or opaque
- too much state hidden in free-form notes
- curation becoming dependent on engineering intervention

## Phase 5: App Integration

### Objective

Integrate the service into the main app without exposing unstable internals.

### Deliverables

- stable app-facing contract
- replacement path for static `places.ts` or equivalent app fixtures
- badges and explanation text integrated into UI
- feature-flagged rollout
- feedback loop from app usage to editorial review queue

### Exit criteria

- app integration depends only on documented API fields
- service can be disabled or rolled back without breaking the app
- user-visible copy remains concise and interpretable

### Risks

- frontend starts depending on unstable diagnostics
- pressure to add generic POI features
- too-early expansion beyond Santa Fe

## Phase 6: Stabilization and Second-City Readiness

### Objective

Decide whether the service is ready to generalize.

### Deliverables

- review of score performance on Santa Fe golden routes
- portability audit separating Santa Fe-specific logic from reusable logic
- source coverage and editorial effort estimate for city two
- go/no-go recommendation for expansion

### Exit criteria

- stable editorial workflow
- clear evidence of what transfers and what does not
- expansion plan includes local review capacity, not just engineering capacity

## Critical Path

1. Repo scaffold and schema
2. OSM ingestion
3. Canonical normalization and dedupe
4. Enrichment joins
5. Route scoring and diagnostics
6. Editorial review loop
7. App integration

If any step is skipped, later layers will accumulate false confidence.

## First 30/60/90 Days

### First 30 days

- bootstrap repo and database
- implement initial schema and migrations
- ingest Santa Fe OSM candidates
- establish taxonomy v1
- create first raw-to-canonical pipeline

### First 60 days

- add Wikidata/Wikipedia enrichment
- compute derived signals
- build route suggestion endpoint
- define scoring profiles and golden routes

### First 90 days

- add review queue and overrides
- curate first 100 to 250 POIs
- integrate behind app feature flag
- measure editorial precision and route usefulness

## Team / Agent Decomposition

### Human roles

- product/editorial lead: category philosophy, review standards, copy quality
- backend/platform engineer: service, schema, API, ops
- data engineer or generalist: source adapters, normalization, enrichment

### Agent-friendly work splits

- ingestion agent: source adapters, payload fixtures, provenance plumbing
- taxonomy agent: category mapping, false-positive filters, dedupe heuristics
- scoring agent: route-fit math, profile tuning, diagnostics
- evaluation agent: golden-route cases, regression harness, metrics
- editorial tooling agent: admin endpoints and lightweight review UI

Keep write scopes disjoint when parallelizing implementation.

## Decision Gates

### Gate 1: After Phase 1

Question:

Do OSM candidates in Santa Fe contain enough meaningful coverage to justify the service?

### Gate 2: After Phase 3

Question:

Does weighted ranking plus explanations produce credible route suggestions without editorial rescue on every query?

### Gate 3: After Phase 4

Question:

Is the editorial workflow fast enough to maintain quality as the corpus grows?

### Gate 4: Before city two

Question:

Do we have proof that the framework can adapt without flattening local specificity?

## What Not To Build Early

- ML ranking
- giant admin CMS
- food/reviews/events expansion
- generalized nationwide ingestion
- public query builder for raw source exploration
- excessive caching before real latency evidence

## Definition of Success

The MVP succeeds if a traveler can request route-aware suggestions in Santa Fe and receive a small set of culturally meaningful, route-plausible options that survive editorial review and feel materially better than generic nearby search.
