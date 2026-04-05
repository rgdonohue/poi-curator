# Source Ecology And Anchor Plan

## Purpose

This document defines the next source-expansion phase for POI Curator after the initial OSM + Wikidata spine is working.

It answers two practical needs:

1. make culturally obvious anchors reliably present and rank well
2. expand beyond OSM/Wikidata without turning the backend into a scrape-and-pray junk drawer

Core decision:

> Build a layered source ecology where each source class has a bounded job.

The system should not treat every source as equally true. Some sources define geometry, some corroborate significance, some provide interpretive texture, and some only generate editorial leads.

## Current State

As of April 3, 2026:

- live OSM ingestion is working for Santa Fe
- canonical POIs are persisted in PostGIS
- route and point suggestion endpoints score DB-backed POIs
- Wikidata enrichment is working for OSM records that already carry explicit `wikidata=*` tags
- score diagnostics, category-intent handling, and route evaluation harnesses exist

This is enough to demonstrate the product idea, but not enough to guarantee that culturally central anchors surface consistently or that interpretive texture is rich enough.

Current weakness:

- anchor reliability still depends too heavily on OSM coverage and current weighting
- official city/state/federal corroboration is not yet modeled as first-class evidence
- interpretive themes exist implicitly in category logic, not explicitly as reusable overlays
- crawler-like discovery is not yet separated from truth-bearing evidence

## Strategic Model

The dataset should be treated as four stacked layers.

### 1. Spatial spine

Use to answer:

- where is the place?
- what is it called?
- what type is it?
- what neighborhood, corridor, district, or watershed does it sit in?

Primary sources:

- OSM / Overpass
- City of Santa Fe GIS / ArcGIS REST layers
- official state/federal heritage spatial data where available

### 2. Institutional corroboration

Use to answer:

- is the place recognized by a trusted public or cultural institution?
- is it part of a district, register, or museum/historic-site network?

Primary sources:

- National Register of Historic Places spatial data
- New Mexico State Register / Historic Preservation Division records
- City historic status / district layers
- New Mexico Department of Cultural Affairs museum and historic-site network

### 3. Interpretive texture

Use to answer:

- what story does the place help a traveler read?
- does it illuminate water, labor, colonization, trade, art, religion, settlement, migration, public memory, or infrastructure?

Primary sources:

- city cultural-planning documents
- city/partner StoryMaps
- museum and institutional descriptions
- manual bibliography notes

### 4. Editorial judgment

Use to answer:

- should this actually surface?
- should it be pinned, suppressed, rewritten, or grouped into a thematic pack?

Primary sources:

- editor review
- local packs
- anchor sets
- curated bibliographic notes

## Anchor Reliability Program

This is the proposal for making culturally obvious anchors reliably present and ranked well.

### Goal

Ensure central places such as plazas, acequia corridors, the Palace of the Governors, San Miguel Chapel, the Railyard, Museum Hill, and major neighborhood corridors do not disappear or under-rank simply because one source is weak or one weighting pass drifts.

### Principle

Anchors should survive on evidence, not romance.

That means a place becomes reliable when multiple source layers point at it:

- geometry and name from OSM or city GIS
- formal historic or civic corroboration from city/state/federal layers
- institution or interpretive corroboration from DCA or museum systems
- editorial confirmation where needed

### Implementation

#### A. Add explicit anchor evidence, not a magic anchor flag

Do not create a vague `is_anchor` boolean and call it done.

Instead, create an evidence trail that can justify anchor-like treatment:

- city historic district membership
- city historic building status
- NRHP / State Register presence
- DCA museum/historic-site membership
- city boundary or corridor layer membership
- editorial pack inclusion

#### B. Add anchor-sensitive ranking signals

New scoring inputs should be explicit and diagnosable:

- `official_corroboration_score`
- `district_membership_score`
- `institutional_identity_score`
- `theme_density_score`
- `editorial_anchor_boost`

These should supplement, not replace:

- route fit / point proximity
- category intent
- base significance
- quality

#### C. Add anchor regression sets

Maintain route and point fixture sets for culturally obvious places.

Examples for Santa Fe:

- plaza-core routes and pings
- acequia/water corridor routes
- railyard/infrastructure routes
- civic/history downtown routes
- sparse-result cases where the right answer is empty or thin

The question is not “does Plaza always rank first?”

The question is:

- is Plaza present when it should be?
- do official/history/civic anchors vanish too often?
- do route-fit heuristics drown category intent or corroborated significance?

#### D. Treat anchors as a review queue, not just a score output

Any place with strong official corroboration but weak runtime surfacing should be routed into editorial review.

That lets the team decide whether the model is wrong, the category mapping is wrong, or the source record is incomplete.

## Source Strategy

### Tier A: ingest and link as structured evidence

These are the first sources to actively ingest.

#### City of Santa Fe GIS / ArcGIS REST

Use for:

- museums
- public art
- places of worship
- galleries
- point-of-interest cross-checking
- historic districts / historic building status / corridor layers

Why it matters:

- city-maintained geometry and district membership can directly improve anchor reliability
- boundary and overlay layers can define corridor and district context without scraping prose

Current verified reference:

- [City of Santa Fe Public Viewer MapServer](https://gis.santafenm.gov/server/rest/services/Public_Viewer/MapServer)

#### National Register of Historic Places

Use for:

- formal historic significance corroboration
- district and landmark membership
- history-oriented confidence boosts

Current verified reference:

- [NPS National Register data downloads](https://www.nps.gov/subjects/nationalregister/data-downloads.htm)

#### New Mexico Historic Preservation Division / State Register

Use for:

- state-level register membership
- local historic properties underrepresented in OSM
- spreadsheet- or registry-based corroboration

Current verified reference:

- [NM Historic Preservation Division: Registers of Cultural Properties](https://www.nmhistoricpreservation.org/programs/registers.html)

#### New Mexico Department of Cultural Affairs

Use for:

- museums
- historic sites
- institution naming
- official institutional descriptions

Current verified reference:

- [New Mexico Department of Cultural Affairs](https://www.newmexicoculture.org/)

### Tier B: ingest as evidence or editorial lead material

These sources are rich, but often not clean source-of-record tables.

#### City cultural-planning documents

Use for:

- corridor definitions
- neighborhood-level significance hints
- recurring interpretive themes

Example:

- [Acequia Madre document](https://santafenm.gov/Acequia-Madre.pdf)

#### StoryMaps and similar place narratives

Use for:

- editorial leads
- theme extraction
- candidate corridor/story associations

Important rule:

- never let StoryMaps directly create canonical POIs

### Tier C: whitelisted crawler inputs

These sources should feed `poi_evidence`, not canonical place creation.

Candidate domains:

- `santafenm.gov`
- `santafecountynm.gov`
- `newmexicoculture.org`
- `santafe.org`
- selected museum, preservation, and corridor organizations

Crawler jobs:

1. harvest entity-like mentions and institutional pages
2. link them to existing canonical POIs
3. store claims and snippets as evidence

Hard rule:

- crawler output may create review leads
- crawler output may not create canonical POIs automatically

## Proposed Schema Additions

### `source_registry`

Purpose:

- one registry of all external sources and harvest targets

Suggested fields:

- `source_id`
- `source_name`
- `domain_or_org`
- `source_type`
- `trust_class`
- `license_notes`
- `crawl_allowed`
- `ingest_method`
- `refresh_policy`
- `notes`

### `poi_evidence`

Purpose:

- store corroborating claims and hints without pretending they are canonical truth

Suggested fields:

- `evidence_id`
- `poi_id`
- `source_id`
- `evidence_type`
- `evidence_text`
- `evidence_url`
- `confidence`
- `source_record_ref`
- `theme_tags`
- `extracted_at`

Example `evidence_type` values:

- `official_name`
- `description`
- `historic_designation`
- `district_membership`
- `institution_membership`
- `theme_hint`
- `address`

### `poi_theme_membership`

Purpose:

- assign reusable themes explicitly instead of smuggling them through prose

Suggested fields:

- `poi_id`
- `theme_slug`
- `source_of_assignment`
- `confidence`
- `assigned_at`

### `bibliographic_references`

Purpose:

- support manual scholarly memory without full-text ingestion

Suggested fields:

- `reference_id`
- `poi_id`
- `work_title`
- `author`
- `year`
- `page_reference`
- `theme_slug`
- `editor_note`
- `created_at`

## Theme System

Thematic overlays are the most important way to make the dataset richer without turning it into generic POI search.

Initial Santa Fe themes should include:

- `water_acequia`
- `colonial_contested_histories`
- `rail_trade_labor`
- `craft_folk_art`
- `pueblo_native_institutions`
- `public_memory_reconciliation`
- `museum_hill`
- `canyon_road_art_economy`
- `route66_auto_landscape`
- `railyard_adaptive_reuse`

Each theme should support multiple assignment paths:

- rules from structured sources
- editorial assignment
- crawler evidence
- bibliography notes

## Crawl And Evidence Rules

### What the crawler may do

- discover candidate institutions or place pages
- collect official names and URLs
- collect theme hints
- collect institutional self-descriptions
- seed review queues

### What the crawler may not do

- define canonical significance
- create canonical POIs without human or structured-source corroboration
- override formal geometry
- rewrite history through page frequency

## Books And Scholarly Sources

Books should be treated as editorial reference inputs, not as crawl targets.

Use them to create:

- citation-linked notes
- named-place references
- theme associations
- alias discovery

Do not:

- scrape or ingest copyrighted book text into the product
- generate product blurbs by paraphrasing books without editorial review

## Implementation Sequence

### Phase 1: official geometry and corroboration layers

Deliverables:

- ArcGIS REST harvester for city layers
- NRHP import adapter
- NM register import adapter or spreadsheet parser
- evidence linking into `poi_evidence`

Success criteria:

- Santa Fe anchors gain official corroboration coverage
- district memberships and historic-status evidence are queryable

### Phase 2: anchor reliability and evaluation

Deliverables:

- anchor evidence scoring inputs
- anchor-oriented route and point fixture sets
- regression checks for missing or weakly surfaced anchors

Success criteria:

- Plaza / Palace / Chapel / Railyard / Acequia-style anchors remain present in appropriate queries
- empty or sparse cases remain honest

### Phase 3: whitelisted harvester

Deliverables:

- `source_registry`
- whitelisted domain harvester
- entity linking into `poi_evidence`

Success criteria:

- crawler produces evidence and review leads without polluting canonical POIs

### Phase 4: theme overlays and editorial views

Deliverables:

- `poi_theme_membership`
- theme-aware filters and diagnostics
- editorial review views for theme gaps

Success criteria:

- routes and points can surface not just categories but meaningful landscape themes

### Phase 5: bibliography layer

Deliverables:

- citation-backed editorial reference system
- manual note entry tied to POIs and themes

Success criteria:

- editorial memory persists without copyright problems

## What To Build Next

If the next two weeks must stay tight, do this in order:

1. ingest City of Santa Fe GIS layers into evidence tables
2. ingest NRHP and New Mexico register references into evidence tables
3. add anchor evidence scoring and anchor regression suites
4. build the first whitelisted evidence harvester

This is the shortest path to a backend that feels much smarter without losing rigor.

## Guardrails

- More sources do not automatically mean higher truth.
- No source may silently overwrite higher-trust evidence.
- Crawler output is evidence, not canon.
- Theme assignment must stay inspectable.
- Editorial judgment remains the final authority on what surfaces.

## Recommendation

Adopt the layered source ecology model and treat anchor reliability as its first concrete use case.

The correct next step is not “scrape more web.”

It is:

- ingest official city/state/federal corroboration layers
- encode anchor evidence explicitly
- widen evaluation breadth before widening feature scope

That is how the dataset gains depth without losing its soul.
