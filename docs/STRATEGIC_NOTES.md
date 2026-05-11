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

---

## 2026-05-02 — GNIS and NMOSE sprint broadens official-name and water-system coverage

The GNIS and NMOSE acequia/POD sprint added 128 source-primary canonical POIs in the live Santa Fe database: 117 `gnis` canonicals and 11 `nmose_pod` canonicals, bringing active canonicals to 686. GNIS contributed 120 official-name evidence rows and 108 variant-name rows, while NMOSE contributed 66 water-system evidence rows across POD, acequia membership, and acequia association evidence. The strongest coverage improvement is official geographic-name coverage and water/acequia context rather than immediately polished traveler-facing stops.

### Why this matters for POI Curator

This sprint confirms that official-name and infrastructure agencies are useful source layers, but they are not interchangeable with editorially curated POIs. GNIS broadens the spatial/name corpus and exposes variant names; NMOSE makes water-system relationships visible while reinforcing the need for permission-aware acequia handling. The product value comes when these source facts are reviewed, contextualized, and connected to route-plausible interpretation.

### Implications if revisited

- For source posture: official geographic-name sources are good candidate generators and provenance layers, but broad civil/populated-place records should remain review-heavy before Detour surfacing.
- For water-theme coverage: NMOSE evidence strengthens the acequia/water layer without requiring private steward records; future enrichment should preserve the public/private boundary explicitly.
- For conflict policy: GNIS variant names are expected conflicts and should be treated as alternates unless editorial review promotes one to canonical display.
- For operations: parallel source sprints work, but shared live database writes make before/after counts harder to interpret; future sub-agent sprints should isolate operational DB runs or coordinate write windows.

---

## 2026-05-11 — HPD and DCA sprint matures institutional coverage

The NM HPD and NM DCA sprint adds two institutional corroboration layers to the Santa Fe corpus.
HPD is primarily an evidence and diagnostic layer: the public State Register workbook is not
coordinate-bearing, so it attached 78 State Register evidence rows and retained 136 current
no-coordinate diagnostics rather than creating synthetic canonicals. DCA is a small institutional
network layer: it attached six museum/historic-site membership evidence rows and created one
missing DCA-primary canonical for `New Mexico Museum of Art - Vladem Contemporary`.

### Why this matters for POI Curator

The source ecology now has seven implemented non-synthetic source families around the OSM spatial
spine: Wikidata, City GIS/historic districts, NRHP, NM HPD, NM DCA, GNIS, and NMOSE. This confirms
the layered model: official register and institutional sources mostly strengthen existing
canonicals through evidence, while only source records with stop-shaped geometry should create new
canonicals. The remaining gap is not source discovery alone; it is editorial capacity for retained
diagnostics, demoted broad geographies, and field-level naming conflicts.

### Implications if revisited

- For source maturity: federal/state/city/institutional corroboration is now reasonably represented
  for central Santa Fe anchors; vernacular, Indigenous/community-authored, and time-depth narrative
  layers remain thinner.
- For architecture: canonical-vs-evidence-only policy must remain explicit in every adapter.
  Institutional recognition is not equivalent to a traveler-facing POI.
- For editorial planning: backlog pages should drive the next work selection more than new source
  acquisition; HPD no-coordinate diagnostics and GNIS-demoted records are now the largest queues.
- For multi-city expansion: this sprint reinforces that structured institutional sources vary
  sharply by geography and may need bootstrap lists or retained diagnostics rather than forced
  canonical creation.
