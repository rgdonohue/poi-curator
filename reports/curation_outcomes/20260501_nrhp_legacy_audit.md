# NRHP Legacy Audit

Date: 2026-05-01

## Legacy Feed

The existing `nrhp_listed_properties` rows came from the older NRHP enrichment path, not the new canonical-ingestion adapter.

- Feed: NPS National Register listed-properties CSV
- URL: `https://www.nps.gov/common/uploads/sortable_dataset/nationalregister/53699964-0893-68AA-5273CB1C614B8BB3/nri-national-register-listed20250624.csv`
- Feed date: 2025-06-24, as encoded in the filename
- Format: listing-only CSV; no latitude/longitude columns
- Local run evidence: `poi_evidence.observed_at` ranges from 2026-04-04 13:18:44 UTC to 2026-04-04 13:18:46 UTC for the 22 rows under `source_id = 'nrhp_listed_properties'`

## Why Records Landed In Diagnostics

The legacy path was a human-review-first enrichment path. It filtered the listed-properties CSV to city/region rows and attempted conservative name-based matching against existing canonical POIs. Because the CSV lacked coordinates, it could not use the new spatial+name matching path and it did not create NRHP-only canonical POIs.

That explains the 50 unreviewed diagnostics: they were listed NRHP records whose best name-only candidate stayed below the legacy confidence threshold. Examples include plausible-but-unsafe matches such as `Las Acequias` to `Las Acequias Park` at 0.737 and `Santa Fe National Cemetery` to `Revival Center of Santa Fe` at 0.735.

## Scope And Staleness

The 50 diagnostics are still meaningful. All 50 are present in the 2025 listed-properties CSV, so they are not stale against the configured legacy feed.

Comparison to the NPS public geodatabase Santa Fe County slice:

| Legacy row category | Diagnostics | Evidence rows | Assessment |
|---|---:|---:|---|
| Listed Santa Fe County record with public geometry | 29 | 20 | In scope for the new canonical NRHP run. |
| Listed Santa Fe County record without public geometry | 13 | 1 | Still in scope as listed records, but not ingestible through the coordinate-bearing public geometry path in this run. |
| Present in 2025 CSV but absent from the spatial Santa Fe County slice | 8 | 1 | Not stale in the CSV. These are either newer than the public geodatabase snapshot, outside the county in the CSV, or otherwise absent from unrestricted public geometry. |

Two of the eight diagnostics absent from the spatial Santa Fe County slice are outside Santa Fe County in the 2025 CSV (`Glorieta Pass Battlefield` in San Miguel County and `Cochiti Pueblo` in Sandoval County). The other six are Santa Fe County listed records in the CSV but absent from the public spatial slice used for canonical ingestion.

## Source Chosen For The Real Run

The real canonical-ingestion run used the NPS IRMA public file geodatabase, because it carries coordinates and public geometry:

- IRMA reference: `https://irma.nps.gov/DataStore/Reference/Profile/2210280`
- Holdings API: `https://irma.nps.gov/DataStore/Reference/GetHoldings?referenceId=2210280`
- Download: `https://irma.nps.gov/DataStore/DownloadFile/662624`
- Local file: `data/runtime/nrhp/NRIS_CR_Standards_Public.gdb.zip`
- Format: Esri file geodatabase
- Acquisition date: 2026-05-01

The Santa Fe County `NR_Main` slice contains 92 records: 89 `Listed`, 2 `Eligible`, and 1 `Returned`. Restricting to listed records with public coordinates yields 61 candidate records for the adapter run. The 28 listed records without public geometry are retained in the audit but skipped by the canonical-ingestion adapter because this run is explicitly coordinate-bearing.

## Reconciliation Decision

Completed after the coordinate-bearing `source_id = 'nrhp'` run.

### Legacy diagnostics

| Decision | Count | Database action |
|---|---:|---|
| Superseded by spatial NRHP run | 29 | Updated `official_match_diagnostic.status` to `superseded`, `resolution_method` to `nrhp_spatial_superseded`, and set `reviewed_at/reviewed_by`. |
| Outside the Santa Fe County scope | 2 | Updated `status` to `out_of_scope` and `resolution_method` to `outside_county`. These are `Glorieta Pass Battlefield` in San Miguel County and `Cochiti Pueblo` in Sandoval County in the 2025 CSV. |
| Retained as legacy unreviewed diagnostics | 19 | Left unchanged because they are current listed CSV records not covered by the public Santa Fe County geometry run. Thirteen are listed Santa Fe County records without public geometry; six are Santa Fe County CSV records absent from the spatial slice. |

### Legacy evidence

| Decision | Count | Database action |
|---|---:|---|
| Superseded by same-canonical `nrhp` evidence | 14 | Left under `source_id = 'nrhp_listed_properties'` to preserve lineage, but tagged `raw_evidence_json.legacy_reconciliation_status = superseded_by_nrhp_spatial_run`. No migration to `source_id = 'nrhp'` was done because the new run already created first-class `nrhp` evidence for the same canonical POIs. |
| Duplicate review required | 6 | Tagged `raw_evidence_json.legacy_reconciliation_status = duplicate_review_required` and recorded the new NRHP POI ID. These rows share the same NRHP reference with the new run, but the new spatial+name matcher created a different canonical POI instead of attaching to the existing legacy-evidence POI. |
| Retained; not replaced by spatial run | 2 | Tagged `raw_evidence_json.legacy_reconciliation_status = retained_no_public_geometry_or_missing_from_spatial_run`. These are `Laboratory of Anthropology Director’s Residence` and `Delgado Street Bridge`. |

Duplicate-review cases created by the real run:

| NRHP ID | Legacy POI | New NRHP POI | Assessment |
|---|---|---|---|
| 02001163 | Don Gaspar Avenue Bridge | Don Gaspar Bridge | Likely same bridge; matcher missed because name similarity was just below threshold. |
| 08000732 | El Zaguán | El Zaguan | Likely same property; accent normalization gap. |
| 08001181 | Santa Fe River Park East | Santa Fe River Park Channel | Likely same corridor/channel concept, but label and geometry scope differ. |
| 70000409 | Randall Davey House | Davey, Randall, House | Likely same property; register-name inversion plus spatial offset. |
| 73001150 | Donaciana | Santa Fe Historic District | Genuine scope conflict: point/venue-style OSM POI versus district listing. |
| 74001209 | Pinckney R Tully House | Tully, Pinckney R., House | Likely same property; spatial offset exceeded the 100 m threshold. |

No legacy evidence rows were bulk-migrated to `source_id = 'nrhp'`. That avoids duplicate first-class NRHP evidence and keeps the old CSV lineage visible for audit.
