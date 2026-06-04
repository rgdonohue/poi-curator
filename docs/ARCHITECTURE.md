# Architecture

POI Curator is the curated backend for Detour, a route-aware mapping prototype that asks a narrower
question than ordinary local search:

> What stop along or near this route would help a traveler read the landscape more deeply?

The system is not trying to become a complete directory of nearby businesses, a replacement for a
routing engine, or a generic attractions API. Its domain is place-aware recommendation grounded in
cultural geography. A good result is not merely close, open, popular, or commercially useful. A good
result helps explain why a corridor, plaza, acequia, railroad edge, museum campus, district, or
landscape feature matters in context.

That product stance shapes the architecture. The backend separates slow source work from fast
runtime queries. It ingests official and open datasets, preserves source evidence, logs matching
decisions, exposes conflicts, and computes deterministic scores. Runtime endpoints can then answer
route, nearby, and point suggestion requests from a prepared corpus instead of improvising source
interpretation during a user interaction.

## The Problem

Most POI systems optimize for utility: food, fuel, lodging, reviews, hours, or commercial
prominence. Those signals are useful, but they are not enough for a traveler trying to understand a
place. In Santa Fe, for example, a stop can be relevant because it reveals a water system, a
railroad corridor, a civic memory site, a museum institution, a State Register property, a historic
district, or a locally significant landscape form. Some of those places are obvious in OSM. Some
are present only as official register rows. Some are broad geographies that should not surface as
stops until a curator decides how to frame them.

POI Curator treats that as a data-quality and editorial problem first. Source records are not
assumed to be equal, and official recognition is not treated as automatic traveler-facing
importance. The system keeps canonical POIs, source evidence, derived signals, editorial review,
and generated drafts distinct. That distinction is what lets the project be transparent about what
it knows, what it inferred, and what still needs human judgment.

## Layered Source Ecology

The core model is a layered source ecology. Each layer has a bounded job.

The spatial spine answers basic identity and geometry questions: where is the place, what is it
called, and what kind of thing is it? In the Santa Fe deployment, OSM/Overpass is the working spine.
City GIS and official spatial sources can also contribute geometry. In future geographies, a
national conflated dataset such as OpenPOIs could be a candidate spine, especially before a
second-city deployment. The strategic point is that spine selection is not the same as editorial
interpretation.

Institutional corroboration answers whether a place is recognized by a public or cultural
institution. Current Santa Fe examples include the National Register of Historic Places, the New
Mexico Historic Preservation Division State Register, City of Santa Fe historic districts, New
Mexico Department of Cultural Affairs institutions, GNIS names, and NMOSE water-system records.
These sources strengthen the evidentiary basis of canonical POIs, but they do not all create POIs.
A State Register district, an acequia line, or a broad GNIS civil geography may be important
evidence without being a stop-shaped feature.

Interpretive texture answers what story a place helps a traveler read. This layer is thinner today
than the institutional layer. It includes theme hints, museum and agency descriptions, route
context, local bibliography notes, and future editorial packs. It is where water, rail, public
memory, settlement, religious practice, art corridors, and infrastructure become reusable
interpretive frames rather than one-off tags.

Editorial judgment is the top layer. It answers whether a place should surface, be suppressed,
renamed, grouped, rewritten, or held for review. This layer is explicit because cultural geography
cannot be fully delegated to source presence. A dataset can identify a historic register row, but
only editorial review can decide whether the display name is readable, whether a broad geography is
too vague for a stop, or whether a derived coordinate is good enough to promote.

## Canonical POIs And Evidence

Canonical POIs are source-agnostic normalized records used by query paths. A canonical row carries
fields such as name, geometry, category, short description, flags, review status, and scoring
signals. Source records remain separate. They attach to canonicals as evidence and field
provenance.

This distinction is deliberate. When a new source matches an existing POI, it does not silently
overwrite canonical fields. It attaches evidence. For example, an NRHP row may corroborate a house,
an HPD row may add a State Register name, a DCA row may verify museum membership, and GNIS may add
variant names. The canonical display value remains stable until policy or editorial review changes
it.

Per-field provenance makes that rule inspectable. For canonical fields such as `name`,
`primary_category`, `coordinates`, and `short_description`, the database records which source
contributed which value, its confidence, when it was observed, and whether that row is the current
display-canonical value. Alternate values are preserved. The admin viewer can therefore show that a
traveler sees `A. M. Bergere House`, while NRHP preserves `Bergere, Alfred M., House` and HPD
preserves `Bergere, A. M., House`.

Conflict visibility is part of the model, not an error state. If sources disagree, the system
surfaces the disagreement. A conflict can be a normalization case, a legitimate two-name case, a
coordinate placement difference, a source taxonomy difference, or a real unresolved disagreement.
Bulk policy can resolve known patterns by marking exactly one provenance row canonical, but it
does not erase alternates.

## Matching Pipeline

The shared source matcher follows a conservative sequence: identifier-first, then spatial plus
name. If an incoming record carries a Wikidata identifier and that identifier matches the canonical
POI or existing Wikidata evidence, the system matches by identifier. This catches high-confidence
identity links even when names differ.

If there is no identifier match, the matcher uses a 100 meter spatial window and normalized name
similarity. Names are lowercased, punctuation is stripped, common affixes such as articles and
local terms are removed, and similarity is compared against the current 0.85 threshold. If exactly
one candidate in range passes, the source record attaches to that canonical. If multiple candidates
pass, the record is marked ambiguous and routed to review. If no candidate passes, the source
adapter decides whether to create a new canonical, attach evidence only, or retain a diagnostic.

This pipeline catches straightforward cases: the same historic building in OSM and NRHP, a museum
campus with DCA corroboration, or a GNIS spring near an existing canonical. It intentionally misses
some plausible matches. Formal register names, address-only HPD rows, campus-scale geocodes, and
broad district labels often need human review because automatic attachment would be too risky. The
system logs every match, new-canonical decision, ambiguous result, and policy demotion in
`poi_match_log` or diagnostics so these misses become visible work queues rather than hidden data
loss.

## Editorial Layer

The editorial layer is how the system refuses to guess. Review states distinguish active,
needs-review, demoted, candidate, superseded, and diagnostic records. Broad GNIS Civil and
Populated Place records, for example, were demoted with date-stamped policy notes rather than
deleted. They remain discoverable, but they do not surface in scoring until reviewed. HPD
address-geocoded rows are queued as candidate canonicals because Nominatim coordinates are derived
from addresses, not source-published geometry.

The naming policy is also editorial infrastructure. It encodes repeatable decisions: common
person-name building form beats register order; accented local spelling is canonical when sourced;
leading articles are dropped unless integral; GNIS variants are alternates; OSE labels are
provisional; HPD and NRHP register names remain sourced alternates; DCA institutional names should
preserve visitor-facing campus branding. Recent policy also covers common-use descriptions,
coordinate offsets, and primary-category differences between current use and register taxonomy.

These rules reduce repetitive review without pretending the source conflict disappeared. The admin
viewer still exposes conflicts, provenance rows, evidence, match logs, and diagnostics. The goal is
not to hide disagreement; it is to distinguish known normalization patterns from cases that require
real editorial judgment.

## Santa Fe Reference Deployment

The current reference deployment is Santa Fe County. It has 743 active canonical POIs in the live
local database, backed by PostGIS and exposed through FastAPI public and admin APIs. The implemented
source ecology includes the OSM spatial spine plus seven source families around it: Wikidata, City
of Santa Fe historic districts, NRHP, NM HPD, NM DCA, GNIS, and NMOSE POD/acequia records.

The source distribution reflects the architecture. OSM still provides the broadest spatial spine.
NRHP and HPD mostly corroborate existing historic canonicals. DCA attaches institutional evidence
to museum and historic-site canonicals, with rare DCA-primary creation for a missing campus record.
GNIS creates canonical POIs only for stop-shaped feature classes such as canals, springs, summits,
valleys, churches, cemeteries, parks, trails, and historic schools; broad administrative
geographies are demoted or evidence-only. NMOSE POD points can create narrow water-network
canonicals, while acequia conveyance lines attach membership evidence to nearby POIs.

The editorial backlog is now explicit. There are 104 GNIS-demoted records awaiting review, 64
geocoded HPD candidates awaiting promotion or rejection, 72 HPD no-coordinate diagnostics retained,
73 legacy HPD diagnostics retained, 19 retained NRHP diagnostics, and 35 short-description
residuals needing prose review. Field conflicts remain visible by design, but known name,
description, coordinate, and category patterns have a single highlighted canonical provenance value.

Runtime scoring is deterministic and route-aware. Public endpoints rank stops for supplied route
geometries, nearby centers, and point suggestions. Scores include proximity, detour fit, category
intent, significance, quality, mode affinity, institutional identity, district membership, and
theme-specific bonuses. The backend does not compute turn-by-turn routes; it estimates detour cost
geometrically and expects a frontend or routing provider to compute final route-through-stop
geometry.

## What This Is Not

POI Curator is not a Google Places competitor. It does not aim to index every business, maintain
hours, rank by popularity, or optimize commercial discovery. It is narrower and slower: a curated
source-aware corpus for meaningful stops.

It is also not an OpenPOIs competitor. OpenPOIs and similar datasets solve the national spatial
spine problem by conflating large POI feeds and modeling staleness. POI Curator can sit above that
kind of spine. Its differentiator is editorial interpretation, multi-source provenance, contested
or alternate naming, time-depth, institutional corroboration, and route-plausible cultural
geography. The two systems are complementary: one can provide broad spatial coverage, while POI
Curator decides what a traveler should understand and why.
