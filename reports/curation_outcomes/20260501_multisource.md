# Multi-Source Ingestion Curation Outcome Report

Generated: 2026-05-01

Scope: local live database at `postgresql://poi_curator@localhost:5432/poi_curator`. The admin
API/browser was not required for the data extraction.

Important caveat: the schema and admin surfaces for this phase are present, but this live corpus
does not show a completed real NRHP canonical-ingestion run. There are no `primary_source = 'nrhp'`
canonical POIs, no `source_id = 'nrhp'` field-provenance rows, and no `poi_match_log` rows. Older
NRHP enrichment evidence is present under the legacy source id `nrhp_listed_properties`.

## 1. Coverage Summary

Canonical POI count before this phase, inferred from the current corpus before any NRHP-only
canonical additions: **515**.

Canonical POI count after this phase in the live database: **515**.

Net canonical POI growth from NRHP-only ingestion: **0**.

Source-basis breakdown, normalizing legacy `nrhp_listed_properties` evidence to `nrhp`:

| Source basis | POI count |
|---|---:|
| osm-only | 414 |
| osm + wikidata | 78 |
| osm + nrhp + wikidata | 20 |
| osm + nrhp | 2 |
| nrhp-only | 0 |
| nrhp + wikidata | 0 |
| no tracked source basis | 1 |

Raw provenance coverage currently records `osm` for 514 POIs and `wikidata` for 98 POIs. It does
not yet record `nrhp` field-level provenance in the live corpus.

## 2. New Canonical POIs From NRHP

No new canonical POIs from NRHP are present in the live database.

| Name | NRHP listing ID | Coordinates | Plausible missed OSM node nearby | Editorial note |
|---|---|---|---|---|
| None | n/a | n/a | n/a | The NRHP canonical-creation path has not produced persisted NRHP-only POIs in this corpus. |

There are 22 older NRHP evidence attachments to existing OSM-backed canonical POIs, including
Palace of the Governors, The Santa Fe Plaza, Barrio de Analco Historic District, and Digneo-Valdes
House. Those improve corroboration, but they are not new canonical POIs.

## 3. Top 10 Conflicts

Field-level provenance currently reports **0 conflict fields**. Because NRHP field provenance has
not been populated in the live corpus, there are no NRHP-vs-OSM or NRHP-vs-Wikidata conflicts to
rank.

| POI name | Conflicting field | Sources | Disagreeing values | Editorial note |
|---|---|---|---|---|
| None | n/a | n/a | n/a | No field-level conflict rows exist yet. This is a data-population gap, not proof that sources agree. |

Legacy NRHP evidence does show likely future conflict/review cases once backfilled into
`poi_field_provenance`, for example register-name variants such as `Bergere, Alfred M., House`
versus `A. M. Bergere House`, or `Crespin, Gregorio, House` versus `Gregorio Crespín House`. These
look mostly like normalization and register-name-order issues, not genuine source disagreement.

## 4. Match Log Statistics

`poi_match_log` contains no rows in the live database.

| Decision bucket | Count |
|---|---:|
| match-identifier | 0 |
| match-spatial | 0 |
| ambiguous | 0 |
| new-canonical | 0 |

Ambiguous cases: none logged.

Legacy `official_match_diagnostic` still has unreviewed rows from older enrichment paths:

| Source | Unreviewed diagnostics |
|---|---:|
| `nrhp_listed_properties` | 50 |
| `nm_hpd_register_workbook` | 91 |

Top legacy NRHP diagnostic examples by best fuzzy similarity:

| External record name | Best candidate | Similarity | Editorial read |
|---|---|---:|---|
| Immaculate Heart of Mary Seminary | The Founding of Santa Fe | 0.759 | likely false candidate; needs manual identity review |
| Las Acequias | Las Acequias Park | 0.737 | possible naming overlap; not enough evidence to auto-link |
| Santa Fe National Cemetery | Revival Center of Santa Fe | 0.735 | likely false candidate |
| Spiegelberg House | Ortiz y Ortiz Residence | 0.727 | likely missing canonical or weak candidate |
| Seton Village | Villa Sonata | 0.720 | likely false candidate |

These are not `poi_match_log` ambiguous decisions; they are older unreviewed diagnostics and should
not be treated as resolved multi-source matches.

## 5. District Membership Coverage

POIs carrying City of Santa Fe historic-district evidence: **275**.

Breakdown by district name from `raw_evidence_json.properties.HDSTNAM`:

| Historic district | POI count |
|---|---:|
| Downtown And Eastside HD | 223 |
| Historic Review HD | 28 |
| Westside-Guadalupe HD | 17 |
| Historic Transition HD | 5 |
| Don Gaspar Area HD | 2 |

The evidence label exposed in existing rows is the generic `Historic Districts`; the specific
district name is currently recoverable from raw City GIS properties.

## 6. Honest Assessment

This phase materially improved the backend infrastructure for Santa Fe curation: the schema,
matching logs, admin conflict surfaces, and provenance model now exist. It did not yet materially
change what surfaces in Detour in this live corpus, because there are zero NRHP-only canonical POIs,
zero new match-log decisions, and zero field-level NRHP conflicts populated. The real gap is
operational/data execution: the NRHP canonical-ingestion adapter needs to be run against a
coordinate-bearing Santa Fe County feed and its results reviewed. Until that happens, the phase is
mostly provenance and review infrastructure layered over the existing OSM/Wikidata/legacy evidence
corpus.
