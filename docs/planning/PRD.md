# Product Requirements Document

## Product Name

POI Curator

## Product One-Liner

A route-aware, culturally informed POI service that recommends stops which help a traveler read the landscape more deeply under real route constraints.

## Product Thesis

Most place APIs answer a commerce or convenience question: what is popular, nearby, or highly rated. This service answers a different question:

**What stop along or near this route reveals something meaningful about the landscape that the route alone would not?**

The service exists as its own backend because the difficult problem is not routing. The difficult problem is place selection: finding, normalizing, enriching, scoring, and reviewing place records so the app can consume a stable contract while the curation logic evolves independently.

## Guiding Principles

1. Find places that are legible, meaningful, and route-plausible.
2. Treat places as evidence of history, ecology, labor, settlement, infrastructure, and identity.
3. Keep editorial control explicit. The model proposes; humans decide.
4. Prefer diagnostics over mystique. Every surfaced place should be explainable.
5. Optimize for interpretive value under detour budgets, not generic popularity.
6. Preserve ambiguity in the data model even if the UI shows a single primary reading.

## Users

### Primary end user

A curious traveler using the main app who wants one or a few meaningful stops that fit the trip already underway.

### Secondary user

An editor or curator reviewing machine-ranked candidates, rewriting blurbs, suppressing junk, and creating local packs.

### Internal platform user

An app developer integrating route suggestions through a stable API without inheriting source-level messiness.

## Jobs To Be Done

- When I am already going somewhere, help me notice a meaningful place I can plausibly stop at.
- When I surface a stop, tell me briefly why it matters in terms the traveler can grasp quickly.
- When the algorithm is uncertain or wrong, let an editor correct it cleanly and durably.
- When we expand into a new city, let us adapt the logic without rewriting the whole app.

## Product Scope

### In scope for MVP

- Santa Fe-focused discovery and curation
- Route-aware top-N stop suggestions
- Limited categories: History, Culture, Art, Scenic
- OSM-based candidate discovery
- Wikidata/Wikipedia enrichment
- NRHP/SHPO overlay where useful and available
- Editorial approve, suppress, boost, rewrite, and pin controls
- Score diagnostics for internal review

### Explicit non-goals for MVP

- Generic nearby search
- Full food and venue recommendation engine
- Event discovery
- Full CMS
- Machine-learned ranking
- City-agnostic logic that pretends Santa Fe rules transfer automatically
- Public-facing exposure of raw source records or ontologies

## Product Requirements

### Functional requirements

1. The system must accept a route geometry and ranking constraints, then return the top N route-plausible suggestions.
2. The system must support travel mode differences at least for driving and walking.
3. The system must expose concise explanation fields for why a place was surfaced.
4. The system must store raw imports separately from canonical records and editorial overrides.
5. The system must support human suppression, pinning, score adjustment, text overrides, and category overrides.
6. The system must log score factor breakdowns for both selected and rejected candidates.
7. The public API must remain stable even when source integrations or scoring weights change internally.

### Data requirements

1. Every canonical POI must retain provenance back to its source records.
2. The system must preserve multi-category membership internally.
3. Enrichment should improve identity, type confidence, and interpretive context, not replace editorial review.
4. Source trust should be differentiated:
   OSM for existence and geometry, Wikidata for identity and typing, Wikipedia for readable context, official heritage data for formal significance.

### Editorial requirements

1. Editors must be able to identify and suppress generic false positives quickly.
2. Editors must be able to rewrite descriptions to avoid romanticized or generic prose.
3. Featured and city-pack curation must be stored explicitly, not hidden in code.
4. Editorial changes must be auditable.

## User Experience Requirements

The API should return concise, composable outputs rather than long prose. The traveler should experience:

- a small number of plausible options
- reasons that feel grounded and locally specific
- detours that respect the trip budget
- diversity across surfaced meanings, not five interchangeable museums

## Public Category Model

- History
- Culture
- Art
- Scenic
- Food
- Civic / Infrastructure

Food is kept in the public model because identity-bearing food may later matter, but it is not an MVP priority and generic commerce must be aggressively down-ranked.

## MVP Geography

Santa Fe urban area plus the immediate regional landscape. The MVP should prove that the system can surface:

- plazas and civic cores
- acequia and water infrastructure
- historic districts and built traces
- scenic overlooks and landscape features
- murals, public art, and cultural corridors
- infrastructural landmarks that reveal settlement or labor history

## Success Metrics

### Product quality

- `Precision@5`: at least 70% of suggested results in curated test routes are deemed “worth surfacing” by reviewers
- `Top-1 acceptability`: at least 60% of golden-route queries have an acceptable first result
- `Low-junk rate`: fewer than 10% of reviewed surfaced results are suppressed as generic false positives
- `Route compliance`: at least 95% of returned results stay within configured detour and extra-minute budgets

### Editorial health

- Median review time per candidate under 2 minutes
- At least 100 reviewed POIs before app rollout beyond internal use
- Less than 5% of editorial overrides caused by missing provenance or opaque scoring

### System performance

- P95 `POST /v1/route/suggest` under 500 ms for Santa Fe-scale data
- Daily ingestion/enrichment runs complete reliably with audit logs

## Risks

- OSM tagging inconsistency creates noisy candidate pools.
- Wikidata and Wikipedia coverage privileges already documented places.
- Heritage overlays overrepresent officially recognized histories.
- Poorly written autogenerated blurbs could drift into tourism sludge or romanticization.
- Scoring brittleness can bury subtle but important places.
- Expansion pressure could force premature generalization.

## Strategic Mitigations

- Build a review queue early instead of treating editorial tooling as phase-two polish.
- Maintain golden-route evaluation fixtures before changing scoring weights.
- Keep source-specific trust signals separate from final canonical fields.
- Require score diagnostics for both positive and negative decisions.
- Expand to a second city only after Santa Fe review workflows and evaluation stabilize.

## Open Product Questions

1. Should “Scenic” include streetscape sequence and walkable corridor feel, or only discrete viewpoints, in the first public release?
2. How much narrative voice should the backend own versus leaving to the app?
3. Should the first editorial workflow live in a real admin screen or a CSV/review export loop?
4. When Food enters scoring, what hard criteria distinguish identity-bearing places from generic businesses?

## Decision Standard

Every new feature should answer:

**Does this make the service better at surfacing places that reveal the landscape under route constraints, or is it just making it more like a generic attraction engine?**
