# Strategic Notes

Low-frequency log of ecosystem observations, positioning decisions, and external developments that inform future planning for POI Curator. Entries are not action items. Each entry has a date, a summary, and an "implications if revisited" section to make future re-reading useful.

---

## 2026-05-01 — OpenPOIs as candidate spatial-spine layer

[OpenPOIs](https://openpois.org) is a nationwide unified POI dataset published in late April 2026 by Henry Spatial Analysis. It contains 17.8M US POIs conflated from OpenStreetMap and Overture Maps, with a per-POI `conf_mean` confidence score from a Bayesian turnover model fit on OSM tag-edit history. That score estimates the probability that a POI currently exists and is published with a 90% uncertainty interval. The dataset is published as Parquet and PMTiles on [Source Cooperative](https://source.coop/henryspatialanalysis/openpois) under ODbL, refreshed monthly following the Overture Maps release schedule, and reproducible with an MIT-licensed Python toolkit at [github.com/henryspatialanalysis/openpois](https://github.com/henryspatialanalysis/openpois). The author is Nat Henry, DPhil, Director of Henry Spatial Analysis; a methods paper is forthcoming, and the work was presented at OSM US State of the Map in June 2026.

### Why this matters for POI Curator

OpenPOIs is solving the OSM-Overture conflation problem at national scale with quantified staleness. POI Curator's differentiator is not conflation; it is editorial interpretation, contested-history modeling, multi-voice provenance, scholarly depth, and time-depth. The two systems are complementary, not competing. OpenPOIs is a candidate spatial-spine layer for future deployments, while POI Curator is the editorial layer that lives on top.

### Implications if revisited

- For multi-city expansion: OpenPOIs is the obvious starting point for the spatial spine in a new geography. Reduces per-city deployment cost materially. Right time to consider switching is before a second-city deployment, not mid-stream for Santa Fe.
- For staleness modeling: `conf_mean` is a probabilistic alternative to the current binary stale-deactivation logic. Worth considering as a future upgrade to `packages/ingestion` stale-handling.
- For positioning: confirms layered-model thesis from `docs/planning/SOURCE_ECOLOGY_AND_ANCHOR_PLAN.md`. Spatial spine is commoditizing; editorial interpretation is the durable differentiator.
- For methods: methods paper, forthcoming, is recommended reading on conflation and confidence scoring approaches.

### What not to do now

- Do not refactor current OSM ingestion to consume OpenPOIs. Working ingestion exists; switching mid-stream is a multi-week refactor with uncertain payoff for the Santa Fe deployment.
- Do not add OpenPOIs as a Tier A source in the source ecology doc. It is not a corroboration source; it is a candidate replacement for the spatial spine itself, which is a different kind of decision.
