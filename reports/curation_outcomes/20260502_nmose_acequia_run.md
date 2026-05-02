# NMOSE Acequia and POD Curation Outcome Report

Generated: 2026-05-02

Scope: live local database after executing the public NM OSE Points of Diversion and acequia
conveyance run for Santa Fe County.

## 1. Coverage Summary

Canonical POI count before this NMOSE run: **675**.

Canonical POI count after this NMOSE run: **686**.

Net canonical POI growth from NMOSE POD ingestion: **11**.

The full Santa Fe County POD layer contains **22,421** records. This run intentionally limited
canonical creation to active PODs tied to meaningful named conveyances: **14** source candidates
from the REST query, **11** after local name-quality filtering.

Raw NMOSE effects from this run: 11 `nmose_pod` raw rows, 692 `nmose_acequia` raw conveyance rows,
66 total NMOSE evidence rows, 110 `nmose_pod` field-provenance rows, and 22 raw `nmose_pod`
match-log rows.

| Source basis containing NMOSE | POI count |
|---|---:|
| nmose_acequia + nmose_pod | 11 |
| nmose_acequia + nrhp | 6 |
| city_gis_historic_districts + nmose_acequia + osm | 5 |
| city_gis_historic_districts + nmose_acequia + osm + wikidata | 1 |
| city_gis_historic_districts + nm_hpd_register_workbook + nmose_acequia + osm | 1 |
| gnis + nmose_acequia + nrhp | 1 |
| nmose_acequia + osm | 1 |

Active POIs now carrying any NMOSE evidence: **26**.

## 2. New Canonical POIs From NMOSE POD

| Name | OSE POD ID | Coordinates | Plausible OSM node nearby missed by matching | Editorial note |
|---|---|---|---|---|
| OAK DITCH A.K.A. DITCH #14 | 238107 | 35.853120, -105.921315 | No OSM canonical within 150 m | Useful water-infrastructure addition, but display value depends on future acequia context and naming review. |
| Point of Diversion - Acequia De La Cienega | 146902 | 35.575016, -106.100831 | No OSM canonical within 150 m | Valuable as an official acequia/POD anchor; needs editorial context before high-visibility presentation. |
| Point of Diversion - Acequia De La Mesilla | 156544 | 35.985441, -106.036016 | No OSM canonical within 150 m | Valuable coverage outside the OSM-heavy urban core; keep source limitations visible. |
| Point of Diversion - Acequia De La Puebla | 155915 | 36.001535, -105.967086 | No OSM canonical within 150 m | Valuable as a water-system trace; likely needs local review before traveler-facing copy. |
| Point of Diversion - Acequia De Las Joyas | 141840 | 35.893330, -105.995885 | No OSM canonical within 150 m | Useful official anchor for acequia geography; avoid over-interpreting beyond source evidence. |
| Point of Diversion - Acequia Del Llano | 156994 | 35.986413, -106.011997 | No OSM canonical within 150 m | Adds rural water-infrastructure coverage with clear provenance. |
| Point of Diversion - Alto Ditch | 100128 | 35.821162, -105.891832 | No OSM canonical within 150 m | Useful as low-level infrastructure evidence; needs curation to decide whether it should surface in Detour. |
| Point of Diversion - Cano | 2673 | 35.894879, -106.001072 | No OSM canonical within 150 m | Valuable only with caution: the very short name may be source shorthand and needs review. |
| Point of Diversion - Mccune Ditch | 145847 | 35.762806, -105.934820 | No OSM canonical within 150 m | Adds official water-system coverage; normalize capitalization if promoted. |
| RICHARDS RANCH DITCH | 238110 | 35.861236, -105.940080 | No OSM canonical within 150 m | Useful official POD, but all-caps source naming should become an alternate if a reviewed display name is chosen. |
| UNCLE MOE DITCH | 238109 | 35.872071, -105.954184 | No OSM canonical within 150 m | Interesting local water-infrastructure anchor; needs human review before interpretive use. |

## 3. Top 10 Conflicts

No NMOSE field-level conflicts surfaced in this run. All matched POD candidates became new
canonical POIs, and acequia conveyance lines attach evidence only; they do not write canonical
field provenance for existing POIs. Future conflicts are most likely to come from reviewed/common
acequia names differing from OSE conveyance labels.

## 4. Match Log Statistics

Decision buckets are de-duplicated by NMOSE POD external record ID.

| Decision bucket | Count |
|---|---:|
| match-identifier | 0 |
| match-spatial | 0 |
| ambiguous | 0 |
| new-canonical | 11 |

Raw `poi_match_log` rows:

| Decision | Strategy | Raw rows |
|---|---|---:|
| new | spatial_name | 22 |

Ambiguous cases: none were logged by the real NMOSE run.

## 5. Acequia Membership Coverage

NMOSE acequia/conveyance evidence now touches **26** active POIs. The run created **24**
`acequia_membership` evidence rows and **31** `acequia_association` evidence rows.

| Acequia or conveyance association | POI count |
|---|---:|
| Acequia Madre de Santa Fe | 7 |
| Acequia Del Llano | 2 |
| Acequia Barranca | 1 |
| Acequia De La Cienega | 1 |
| Acequia De La Mesilla | 1 |
| Acequia De La Puebla | 1 |
| Acequia De Las Joyas | 1 |
| Acequia Del Alto Ditch No 7 | 1 |
| Acequia Del Cajon Grande | 1 |
| Acequia De Los Indios | 1 |
| Acequia De Los Joyas | 1 |
| Acequia Larga De Jacona | 1 |
| Acequia Madre | 1 |
| Alto Ditch | 1 |
| Ancon | 1 |
| Cano | 1 |
| Community | 1 |
| Cono | 1 |
| Henry Carrillo Ditch No 2 | 1 |
| Las Cuevas Ditch | 1 |

## 6. What This Run Does Not Cover

This run does not ingest private steward records, unpublished acequia names, steward-collected
maps, or local knowledge that has not been explicitly cleared for public use. It also does not turn
the full 22,421 Santa Fe County POD records into POIs; most of that layer is water-rights or well
infrastructure that would overwhelm the curated corpus. Unnamed OSE conveyances are excluded from
association evidence, consistent with Source New Mexico's 2023 reporting that many omitted names
reflect reporting and privacy concerns rather than absence of local knowledge.

## 7. Honest Assessment

This run materially improves water-system coverage, but mostly as provenance and context rather
than as high-confidence traveler-facing POIs. The 11 new POD canonicals are official anchors for
acequia geography that OSM does not cover, while the stronger near-term value is the 26 active POIs
now carrying NMOSE acequia evidence. The main gap is editorial, not technical: acequias need local
review, naming sensitivity, and permission-aware context before Detour should treat them as rich
interpretive stops.
