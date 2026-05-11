# NM HPD Legacy Audit

Date: 2026-05-11

## Legacy Feed

The existing `nm_hpd_register_workbook` rows came from the older State Register enrichment path,
not from a canonical-ingestion adapter.

- Feed: NM Historic Preservation Division "03 State and National Register Spreadsheet"
- URL: `https://www.nmhistoricpreservation.org/assets/files/registers/2026/SR%20NR%20Excel%20Database.xlsx`
- Discovery page: `https://www.nmhistoricpreservation.org/programs/registers.html`
- Format: Excel workbook (`.xlsx`)
- Acquisition date for this audit: 2026-05-11
- Workbook metadata: created 2020-02-05, last modified 2025-12-08 by HPD/DCA staff
- Public source description: HPD describes the spreadsheet as a complete searchable list of State
  and National Register properties in Excel format.

## Why Records Landed In Diagnostics

The legacy path was an enrichment path that attempted conservative name-based matching against
existing canonical POIs. The public workbook does not carry latitude/longitude or geometry fields,
so it could not use the current spatial+name matcher and did not create State Register-only
canonical POIs.

The database has 91 unreviewed diagnostics under `source_id = 'nm_hpd_register_workbook'`. Ninety
are current Santa Fe County State Register rows still present in the 2026 workbook. One row,
`Theme Queue Case`, is a local/test diagnostic row using the same source id and is not a real HPD
register record.

Representative low-confidence legacy matches show the issue: rows such as `Ortiz, Nicholas and
Antonio Jose, Houses`, `Hinojos, Francisca, House`, and `La Conquistadora` had plausible but unsafe
name-only candidates below the legacy threshold. Without coordinates, the earlier path correctly
routed those to editorial review.

## Current Source Scope

The 2026 workbook contains 2,085 State Register rows statewide after filtering to rows with a State
Register year. Of those, 214 are in Santa Fe County and 144 have `City = Santa Fe`.

No public coordinate-bearing State Register layer or downloadable spatial file was found on the HPD
Registers pages during this audit. HPD does publish guidance for National Register GIS map
submission, but the public State and National Register spreadsheet itself is listing/address data,
not a geometry source.

## Pre-Ingestion Reconciliation Assessment

| Category | Count | Assessment |
|---|---:|---|
| Current Santa Fe County HPD diagnostics | 90 | Still in scope; eligible for the new adapter's conservative name/address matching. |
| Non-HPD local/test diagnostic using HPD source id | 1 | Not a real source record; leave untouched except to document as non-source noise. |
| Legacy HPD evidence rows | 55 | Existing legacy evidence; do not bulk-merge into the new `nm_hpd` source id during this run. |

## Post-Run Reconciliation Decision

Completed after the `source_id = 'nm_hpd'` workbook adapter run on 2026-05-11.

### Legacy diagnostics

| Decision | Count | Database action |
|---|---:|---|
| Superseded by new `nm_hpd` evidence | 17 | Updated `official_match_diagnostic.status` to `superseded`, `resolution_method` to `nm_hpd_run_superseded`, and set `reviewed_at/reviewed_by`. |
| Retained as legacy unreviewed diagnostics | 73 | Left unreviewed and tagged `raw_payload_json.legacy_reconciliation_status = retained_unreviewed_no_coordinates`. These rows remain current HPD State Register records but did not match safely through the no-coordinate path. |
| Non-source noise | 1 | Updated `Theme Queue Case` to `out_of_scope` with `resolution_method = not_hpd_source_record`. This is not a real HPD source row. |

### New-source diagnostics

The new adapter wrote 136 `source_id = 'nm_hpd'` diagnostics with `status = unreviewed`.
These are current Santa Fe County State Register rows that did not attach to an existing canonical
POI and could not create a new canonical because the public workbook has no coordinates. They are
retained as reviewable source leads, not discarded records.

No legacy `nm_hpd_register_workbook` evidence rows were bulk-migrated to `source_id = 'nm_hpd'`.
That preserves lineage for the older enrichment path while the new adapter records first-class
`nm_hpd` evidence where it can match safely.
