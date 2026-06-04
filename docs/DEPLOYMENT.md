# Deployment Template

This document is a practical starting point for adapting POI Curator to another city. It assumes
the product goal remains the same: route-aware stop recommendations that help a traveler read the
landscape, not a complete commercial POI directory.

## Per-City Decisions

Every deployment needs four decisions before source work starts.

First, choose the spatial spine. Santa Fe currently uses OSM/Overpass directly. A new city might
use OSM, OpenPOIs, a municipal GIS layer, a partner dataset, or a hybrid. This decision should be
made before ingestion work begins because it determines the baseline canonical inventory and the
staleness model. Do not switch spines mid-deployment unless the current spine is blocking the
project.

Second, choose the theme set. Santa Fe has query-active `water` and `rail` themes, with
`public_memory` modeled but not public-query-active. Tucson, Taos, or another city may need
different first-class themes: mining, borderlands, Indigenous placemaking, irrigation, military
landscapes, modernist architecture, pilgrimage, ecological restoration, or labor history. Themes
should be small enough to test with routes and explicit enough to audit.

Third, define hard-rule topics. These are subjects where the system must refuse to guess:
sensitive cultural sites, private community knowledge, burial places, Indigenous place names,
water-rights records, contested memorials, or locations where public mapping has known harms. The
NMOSE acequia caveat is the Santa Fe example: use public OSE data only and do not augment with
private steward records without permission.

Fourth, draft local naming conventions. The Santa Fe policy handles NRHP/HPD register order,
accents, articles, GNIS variants, acequia labels, DCA institution names, and register-description
boilerplate. Another city will have its own patterns: Spanish/English variants, tribal or community
names, mission names, courthouse/campus labels, park unit names, or local abbreviations.

## Source Adapter Pattern

The current source adapters follow a known shape. Use
`packages/ingestion/poi_curator_ingestion/sources/nrhp.py`, `gnis.py`, `nmose_acequia.py`,
`nm_hpd.py`, and `nm_dca.py` as references. Each adapter should:

- document source URL, format, license/access notes, acquisition date, refresh cadence, and scope in
  `docs/SOURCES.md`
- parse source records with structured readers rather than ad hoc strings
- filter to the deployment geography
- build an incoming source record for the shared matcher when coordinates exist
- use identifier-first, then spatial+name matching with current thresholds
- write source evidence, field provenance, raw source records where appropriate, match logs, and
  diagnostics
- be idempotent on re-run
- produce a curation outcome report under `reports/curation_outcomes/`

Most adapters should stay small. The useful reference size is roughly 150 to 300 lines for the core
source-specific logic, with tests for parsing, canonical-vs-evidence decisions, matching, and
idempotence.

## Canonical Vs Evidence Policy

Every source needs an explicit canonical-vs-evidence policy. Do not assume a source row is
canonical-worthy because it is official.

The GNIS refinement is the case study. The first GNIS pass created too many broad Civil and
Populated Place canonicals. The policy was tightened so stop-shaped classes such as Canal, Spring,
Summit, Valley, Church, Cemetery, Park, Trail, and historic School can create canonicals, while
Civil, Populated Place, Locale, and broad Building rows attach only as evidence or become review
leads. No data was deleted; broad records were demoted into a review queue.

Apply that lesson early. District polygons, administrative geographies, program memberships,
linear infrastructure, no-coordinate registers, and address-geocoded rows are usually evidence or
candidate-review material. Point records with meaningful geometry and stop-shaped identity are
better candidates for automatic canonical creation.

## Naming Policy As A Deployment Artifact

`docs/EDITORIAL_NAMING_POLICY.md` is a template, not a universal policy. Copy its structure for a
new city, but rewrite the examples and rules after inspecting actual conflicts. The goal is to
encode repeatable decisions:

- what form is canonical for display
- what source forms remain alternates
- when accents, articles, suffixes, and legal names matter
- when a source label is provisional
- when no automatic rule should apply

The policy should be applied through field provenance, not by deleting alternates. A resolved
normalization case should still show all sourced names in the admin viewer.

## Bootstrapping Editorial Pass

A fresh city deployment is not done after ingestion. Expect an editorial bootstrap pass before the
corpus is useful for public demos.

For a Santa Fe-sized first pass, plan roughly:

- 4 to 8 hours to inspect source coverage and reject noisy source classes
- 4 to 8 hours to resolve recurring naming/category/description conflicts
- 6 to 12 hours to review candidate canonicals, demoted geographies, and no-coordinate diagnostics
- 4 to 8 hours to run route fixtures, tune source policies, and write outcome notes

The total depends more on source quality than city size. A city with clean municipal GIS and a
small museum network can bootstrap quickly. A city with address-only registers, broad geographic
names, sensitive cultural sites, or fragmented public data will need more review time. The right
output of the bootstrap pass is not a perfect corpus; it is a transparent one with active
canonicals, visible evidence, explicit queues, and check-suite cases that protect the first useful
traveler experiences.
