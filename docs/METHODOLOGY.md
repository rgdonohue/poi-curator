# POI Curator Methodology

## Purpose

This document describes the methodology implemented in the repository today for discovering, normalizing, enriching, ranking, reviewing, and evaluating meaningful points of interest (POIs). It is not a speculative product plan. It reflects the actual code paths, data model, and operating workflow currently built in the project.

The system is designed to answer a narrow question:

> What stop along or near this route would help a traveler read the landscape more deeply?

That posture drives several core choices:

- The system is region-first, not globally generic. Santa Fe is the current reference geography.
- Discovery is source-aware and provenance-preserving.
- Ranking is deterministic, rule-based, and explainable.
- Editorial review is explicit rather than hidden inside score tweaks.
- The runtime API stays thin; heavy work happens in ingestion and enrichment jobs.

## Methodological Principles

### 1. Interpretive value over generic popularity

The project is not trying to be a general attraction engine. It prefers places that reveal history, culture, infrastructure, landscape, public memory, or local identity under realistic route constraints.

### 2. Slow data work, fast runtime queries

The methodology separates:

- slow, source-heavy work: ingestion, normalization, enrichment, evidence linking, diagnostics
- fast request-time work: candidate prefiltering, route/nearby scoring, explanation assembly

### 3. Explicit provenance and source trust

Raw source records, canonical POIs, evidence rows, and editorial decisions are stored separately. This allows the system to distinguish:

- existence and geometry evidence
- identity and description evidence
- official corroboration
- editorial overrides

### 4. Deterministic scoring with diagnostics

The current ranking methodology uses explicit weights, guardrails, and factor breakdowns. Every surfaced candidate can be explained in terms of route fit, category fit, corroboration, and interpretive signals.

### 5. Human review remains first-class

Editors can suppress, alias, reclassify, boost, or theme-review a candidate without erasing the underlying machine-generated record of how it was produced.

## Current System Shape

The built system consists of five implemented layers plus one lightweight UI/testing layer:

1. Ingestion
2. Canonicalization and signal initialization
3. Enrichment and evidence linking
4. Scoring and explanation
5. Editorial review and diagnostics
6. API plus local map test UI

There is also a full evaluation layer used to regression-test ranking behavior.

## Data Model

The schema uses Postgres + PostGIS as the primary operational store. The current methodology depends on spatial indexing and proximity operations, so PostGIS is not incidental infrastructure.

### Core tables

- `ingest_run`: run-level bookkeeping for source jobs
- `poi_source_raw`: immutable-ish raw source snapshots with hashes, timestamps, and current/non-current status
- `poi`: canonical normalized POIs used at query time
- `poi_signals`: recomputable derived signals used in ranking
- `poi_editorial`: human review state and override fields
- `source_registry`: normalized registry of enrichment/evidence sources
- `poi_evidence`: evidence rows attached to POIs from official or semi-official sources
- `poi_alias`: alias records used for reconciliation and editorial correction
- `official_match_diagnostic`: unresolved or reviewed diagnostics for unmatched register rows
- `theme_definition`: queryable theme registry
- `poi_theme_membership`: automated theme assignments
- `poi_theme_membership_evidence`: evidence links that support theme assignment
- `poi_theme_editorial`: editorial force-include / force-exclude review state for themes

### Practical modeling consequences

- Raw imports do not write directly into the canonical POI model.
- Official evidence is additive and auditable.
- Theme assignment is treated as its own derived layer, not folded into the base category.
- Editorial review metadata is stored separately from automated inference.

## End-to-End Methodology

## 1. Source Acquisition

### OSM / Overpass discovery

The ingestion pipeline fetches OSM elements through Overpass using a region bounding box and a deliberately narrow filter set. The current query targets element families likely to carry interpretive value:

- `historic`
- `tourism` values such as `museum`, `gallery`, `artwork`, `viewpoint`
- `amenity` values such as `theatre`, `marketplace`, `place_of_worship`
- `place=neighbourhood`
- `man_made`
- `waterway`
- `natural`
- `leisure=park`
- `highway=pedestrian`

This is a recall-oriented discovery pass, not a direct publication step. The assumption is that source selection should err toward plausible candidates, while normalization and scoring remove noise later.

### Raw persistence rules

Each fetched OSM element is written into `poi_source_raw` with:

- source-specific record id
- raw payload JSON
- geometry
- fetched timestamp
- content hash
- `is_current` version flag
- source URL
- license
- ingest run foreign key

If the content hash has changed, the prior current row is marked non-current and a new raw row is inserted. This makes source changes visible instead of silently overwriting them.

## 2. Canonicalization and Initial Signal Creation

### Canonicalization philosophy

Normalization converts messy source elements into a stable POI contract. The methodology is intentionally rule-based:

- require a name
- classify using explicit OSM tag rules
- derive a single primary public category
- preserve secondary public readings in `display_categories`
- build a canonical slug from name plus source id
- preserve a summarized raw tag subset for later reasoning

Elements without names or without a supported classification are skipped, and the audit tooling records why.

### Geometry handling

The normalization layer accepts points, lines, polygons, center points, and bounds-derived polygons from Overpass. Every canonical POI gets:

- a stored geometry
- a stored centroid

The centroid is the main query-time spatial anchor for current ranking.

### Category and subcategory mapping

The system uses:

- public categories: `history`, `culture`, `art`, `scenic`, `food`, `civic`, `mixed`
- internal types such as `historic_site`, `historic_district`, `mural_public_art`, `infrastructure_landmark`, `overlook_vista`, `trail_river_access`

Classification is driven by explicit OSM tag rules plus a few targeted overrides. Examples:

- named plaza parks can be treated as civic plazas
- acequia-named artwork can be interpreted as infrastructure first, with art as a secondary reading
- railway traces outrank generic historical readings when both appear

This means the methodology prefers a strong local reading over a mechanically literal tag match when that produces better interpretive behavior.

### Multi-category methodology

Each POI gets:

- one primary public category
- ordered secondary display categories where appropriate

This allows the ranking layer to distinguish:

- true primary matches
- legitimate secondary matches
- mixed-category queries

That distinction is critical because the scorer uses soft penalties and bonuses around secondary matches rather than a binary include/exclude model.

### Description hygiene

Short descriptions are chosen in this order:

1. editorial override if it is not low quality
2. stored source/enriched description if it is not low quality
3. fallback template by internal subtype

Descriptions are treated as low quality if they are too short, obviously maintenance-like, or look like mapper notes rather than traveler-facing interpretive copy.

### Initial scoring hints

Normalization assigns the first generation of ranking inputs:

- walk affinity hint
- drive affinity hint
- base significance score
- quality score
- boolean interpretive flags

These are deterministic heuristics based on internal type and tags, not learned features.

### Initial signal initialization

On canonical POI upsert, the pipeline initializes `poi_signals` with:

- source count
- Wikidata / Wikipedia presence from raw tags
- OSM tag richness
- description quality
- entity type confidence
- local identity score
- interpretive value score
- genericity penalty
- editorial priority seed

At this stage, official corroboration is still zero until enrichment evidence arrives.

## 3. Enrichment and Evidence Methodology

The enrichment layer does not replace canonicalization. It supplements it with identity, corroboration, and official context.

### Wikidata enrichment

The current Wikidata methodology:

- extracts `wikidata` and `wikipedia` tags from the latest current raw source
- batches entity fetches from the Wikidata API
- writes back `wikidata_id`, `wikipedia_title`, and optionally description text
- updates signal fields such as `has_wikidata`, `has_wikipedia`, and `entity_type_confidence`

Description replacement is conservative. Wikidata only replaces the current short description if the existing description is missing or still a generic template.

### City GIS evidence

The city GIS pipeline ingests a curated set of Santa Fe GIS layers that act as corroborating evidence, not canonical truth. Current layers include museums, public art, places of worship, historic districts, historic building status, plaza park boundary, and railyard boundary.

Matching methodology varies by geometry type:

- point layers: fuzzy name similarity + proximity + category bonus
- polygon layers: centroid-in-polygon or centroid intersection

The resulting evidence rows feed official corroboration, district membership, and institutional identity signals.

### National and state historic register evidence

The historic register pipelines use two official-ish sources:

- NRHP listed properties CSV
- New Mexico HPD workbook

The methodology for matching register rows to POIs is deliberately staged:

1. exact canonical-name match after historic-name normalization
2. exact alias match
3. fuzzy fallback against best candidate similarity

Historic-name normalization removes noise such as articles, register boilerplate, and some variant forms, while preserving enough structure to avoid reckless collapse.

If a row does not clear the auto-link threshold, the system does not silently guess. It creates a diagnostic record in `official_match_diagnostic` for later editorial review.

### Source registry

Every evidence-producing source is normalized into `source_registry` with:

- organization
- source type
- trust class
- access URL
- ingest method

This is part of the methodology, not just metadata. Ranking and editorial reasoning depend on the idea that “official corroboration” is a meaningful class of evidence.

### Evidence signal rollup

After enrichment, the system recomputes evidence-derived signals. The current rollup logic maps evidence types into:

- `has_official_heritage_match`
- `official_corroboration_score`
- `district_membership_score`
- `institutional_identity_score`

These scores are capped at `1.0` and then used directly by the ranking layer. Evidence does not bypass ranking; it modifies the score inputs in explicit ways.

## 4. Theme Methodology

Themes are not just tags or alternate categories. They are route-queryable interpretive frames built on top of the base POI model.

### Current themes

- `water`
- `rail`
- `public_memory` is defined but not currently query-active

### Automated assignment

Theme evaluation currently uses:

- raw tag signals
- canonical naming
- alias naming
- selected evidence text and labels
- subtype guardrails

Examples:

- water: canal traces, waterways, acequia naming, water-linked evidence
- rail: railway tags, historic railway stations, depot/railyard naming, rail-linked evidence

The methodology is intentionally conservative about name-only matches. A name-only art POI like a mural should not automatically become a water or rail theme match just because it contains a token like “acequia” or “railyard”.

### Status and review model

Automated theme memberships are written as:

- `accepted`
- `candidate`

Editors can then:

- force include
- force exclude
- review without override

The review state is tracked as:

- `unreviewed`
- `reviewed`
- `stale`

`stale` is a real methodological concept here: if the automated membership changes after review, the system treats the prior review as needing re-checking.

## 5. Ranking Methodology

The ranking layer is split between:

- route-aware suggestion
- point/nearby suggestion

Both use the same broad scoring philosophy, with different spatial metrics.

### Candidate prefiltering

The database path uses PostGIS prefilters before in-Python scoring:

- nearby: `ST_DWithin` between POI centroid and query point
- route: `ST_DWithin` between POI centroid and route geometry

This keeps the expensive full scoring pass bounded to plausible spatial candidates.

### Query-time gating

A POI must pass:

- active status
- category compatibility
- theme compatibility if a theme is requested
- spatial budget/radius checks

Theme queries are only allowed for themes marked query-active.

### Route scoring

Route scoring combines:

- route proximity
- detour fit
- budget fit
- significance
- quality
- travel-mode affinity
- official corroboration
- district membership
- institutional identity
- editorial boost
- genericity penalty
- category-specific context bonuses/penalties
- theme-specific context bonuses/penalties
- category match bonus
- category-intent guardrail

Important methodological detail: secondary-category matches are allowed to win, but only if the spatial advantage is strong enough to justify them. This prevents the system from surfacing weakly related POIs just because they happen to carry the requested category secondarily.

The current default non-spatial weights are:

- significance: `30`
- quality: `10`
- mode affinity: `8`
- official corroboration: `8`
- district membership: `5`
- institutional identity: `4`
- genericity penalty multiplier: `10`

The current route-space score ranges are:

- route proximity: up to `15`
- detour fit: up to `15`
- budget fit: up to `5`

### Nearby scoring

Nearby scoring uses the same non-spatial methodology, but replaces route metrics with:

- point proximity
- radius fit

It also uses a similar secondary-match guardrail to stop loose secondary matches from overwhelming the query intent.

The current nearby-space score ranges are:

- point proximity: up to `18`
- radius fit: up to `12`

### Category context logic

The scorer includes explicit domain-specific category behavior, for example:

- scenic requests penalize generic park-like candidates unless they behave like true overlooks or landscape features
- art requests reward stronger art anchors such as murals and gallery spaces
- civic requests can reward hybrid history/civic anchors such as rail depots

This is one of the key ways the methodology avoids becoming a generic local-search engine.

### Theme context logic

The current theme-specific scoring logic is intentionally modest. For example, mixed-category rail queries reward strong depot/station anchors and apply a guardrail against weak rule-only trace matches.

### Explanation generation

Runtime responses include:

- `score_breakdown`
- `why_it_matters`
- `badges`

These are derived from the actual winning components, not hardcoded marketing copy. Explanation text is intentionally short and tied to the score context, route context, theme context, and evidence context.

## 6. Editorial Methodology

The editorial layer is designed to correct machine output without destroying the audit trail.

### Current editorial controls

For base POIs:

- status override
- title override
- description override
- category override
- boost
- notes

For diagnostics:

- resolve a register row to a chosen POI
- create an alias from a diagnostic
- suppress a diagnostic

For themes:

- review without override
- force include
- force exclude

### Alias methodology

Aliases are treated as durable reconciliation infrastructure, not a one-off fix. When editors create aliases from unresolved diagnostics, those aliases become reusable matching aids for future historic register imports.

### Diagnostic methodology

Unmatched official rows are never silently dropped. They are preserved with:

- normalized external name
- best candidate
- similarity
- attempted match strategy
- status
- review metadata

This is central to the project’s methodology: unresolved ambiguity is surfaced for review rather than hidden.

## 7. API and Runtime Behavior

### Public API

The public API exposes:

- `/v1/health`
- `/v1/config`
- `/v1/categories`
- `/v1/route/suggest`
- `/v1/point/suggest`
- `/v1/nearby/suggest`
- `/v1/poi/{poi_id}`

The API returns a stable query contract with explanations, badges, and score breakdowns.

### Admin API

The admin API exposes:

- editorial queue
- POI patching
- evidence drilldown
- theme summaries and review queues
- theme membership detail and review
- match diagnostic list and resolution actions
- alias creation

### Hybrid backend behavior

One important current implementation detail: the default backend is hybrid.

- It tries the database-backed query path first.
- If that path errors or returns nothing and fixture fallback is allowed, it falls back to fixture-backed behavior.

This is useful during active development, but it also means methodology discussions should distinguish between:

- the intended steady-state DB-backed workflow
- the current safety-net fixture behavior used for scaffolding and local testing

## 8. Validation and Evaluation Methodology

The project uses three layers of validation.

### Unit tests

Unit tests cover:

- OSM tag classification and overrides
- normalization behavior
- description hygiene
- scoring component behavior
- theme evaluation and review-state logic
- enrichment parsing and evidence rollups
- evaluation report generation

These tests protect the methodology itself: category rules, theme guardrails, scoring tradeoffs, and evidence semantics.

### Database-backed integration tests

Integration tests verify that the PostGIS-backed query path actually uses:

- DB-persisted POIs
- theme membership persistence
- evidence visibility
- editorial override persistence

This is important because a lot of the methodology only matters if the database-backed path behaves the way the in-memory logic says it should.

### Golden evaluation fixtures

The repository includes combined route and nearby evaluation fixtures for Santa Fe. These cases encode:

- purpose of each query
- expected names
- forbidden names
- expected empty behavior where appropriate
- preferred top names

This evaluation layer is the main regression harness for ranking changes. It tests not just “does the code run” but “does the ranking still express the intended local logic”.

The current report in `reports/santa_fe_eval_report.md` shows the present evaluation state for the fixture set.

## 9. Operational Workflow

The current intended workflow is:

1. Ingest OSM raw data for a supported region.
2. Normalize into canonical POIs and initialize baseline signals.
3. Run enrichment jobs:
   - Wikidata
   - City GIS
   - NRHP
   - New Mexico state register
4. Recompute evidence-linked signals and theme memberships.
5. Review unmatched diagnostics and theme queues.
6. Validate ranking behavior with evaluation fixtures.
7. Expose results through the API and local map test UI.

### Current CLI entry points

- `poi-curator-ingest osm`
- `poi-curator-ingest audit-osm`
- `poi-curator-ingest rebuild-osm`
- `poi-curator-ingest refresh-osm`
- `poi-curator-enrich wikidata`
- `poi-curator-enrich city-gis`
- `poi-curator-enrich nrhp`
- `poi-curator-enrich state-register`
- `poi-curator-eval routes`
- `poi-curator-eval cases`

## 10. What Is Built vs. Scaffolded

### Built now

- FastAPI public and admin endpoints
- PostGIS-backed canonical POI querying
- OSM ingestion and normalization
- Wikidata enrichment
- City GIS evidence enrichment
- NRHP and state-register reconciliation
- evidence signal recomputation
- water and rail theme automation plus editorial review
- editorial patching, aliases, and diagnostics workflows
- route and nearby evaluation harness
- local map-test UI

### Present but still scaffolded or partial

- dedicated admin frontend app
- public-memory theme automation
- Wikipedia extract hydration job
- real ingest-run admin triggering beyond scaffold response
- broader multi-region support

## 11. Known Methodological Limits

- The current geography is Santa Fe-first and should be treated that way.
- Category classification is explicit and understandable, but not exhaustive.
- Centroid-based spatial reasoning is a pragmatic simplification for now.
- Theme logic is intentionally narrow and should not be mistaken for a general ontology layer.
- Historic reconciliation still depends heavily on name matching, even with aliases and diagnostics.
- Hybrid fixture fallback is helpful during development but can obscure whether a response came from the fully operational DB-backed path unless checked carefully.

## 12. Decision Standard for Future Changes

Future changes should be evaluated against the methodology already encoded here:

- Does the change improve interpretive place selection rather than generic search?
- Does it preserve provenance, diagnostics, and editorial control?
- Does it keep runtime ranking explainable?
- Does it strengthen regression safety through evaluation fixtures or tests?
- Does it generalize the right layer, rather than flattening Santa Fe-specific logic into fake universals?

If a change weakens those properties, it is working against the current methodology even if it adds features.
