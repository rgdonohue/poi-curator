# Editorial Backlog

Last updated: 2026-05-11

This page consolidates source-driven curation queues so editorial work can be selected from one
place. Counts reflect the live local Santa Fe database after the GNIS/NMOSE and NM HPD/NM DCA
source sprints.

## Summary

| Queue | Count | Source | Current handling |
|---|---:|---|---|
| GNIS-demoted records | 104 | GNIS | Review for possible promotion; 98 have no nearby attachment, 6 also attached evidence to nearby canonicals. |
| Field-level conflicts | 276 | Multi-source | Resolve or mark as accepted alternates; largest groups are name and short-description conflicts. |
| HPD no-coordinate diagnostics | 136 | NM HPD | Current State Register records retained because the public workbook has no coordinates. |
| Legacy HPD retained diagnostics | 73 | NM HPD legacy | Still unreviewed after reconciliation; evaluate against current State Register workbook. |
| Retained NRHP diagnostics | 19 | NRHP legacy | 11 queued for next ingest/manual coordinates, 9 out-of-scope retained for audit context. |
| GNIS ambiguous match | 1 | GNIS | `Atalaya Mountain`; two candidate canonicals in match diagnostics. |

## Field Conflicts

| Field | Count |
|---|---:|
| name | 130 |
| short_description | 92 |
| coordinates | 34 |
| primary_category | 18 |
| gnis_feature_id | 1 |
| street_address | 1 |

Common patterns:

- NRHP/HPD register-order names versus OSM/common display names.
- GNIS variant names and official geographic names versus local/common names.
- DCA institution coordinates versus OSM point placement for museum campuses.
- Source-specific short-description templates on already matched canonicals.

## Source Queues

### GNIS

Broad Civil, Populated Place, and Military records were demoted from active scoring after the GNIS
policy refinement. These records remain discoverable in the admin viewer with
`review_state='gnis_demoted_pending_review'`.

Priority examples for review:

- culturally significant populated places such as Nambe, Santa Cruz, and Cerrillos
- land-grant/civil geographies such as Caja del Rio Grant
- low-value or cryptic civil labels that should likely remain inactive

### NM HPD

The current HPD State Register workbook is not coordinate-bearing. Matched records attach State
Register evidence, but unmatched Santa Fe County records remain diagnostics rather than canonical
POIs.

Next editorial decision needed:

- whether to establish a manual coordinate-entry policy for high-value HPD records
- whether district designations should link to more granular member POIs where defensible
- whether retained legacy workbook diagnostics should be closed after manual review

### NRHP

NRHP retained diagnostics remain from the legacy CSV reconciliation. They should be reviewed
alongside HPD no-coordinate records because the underlying issue is similar: formal register
recognition without usable public geometry.

### NM DCA

DCA produced no large editorial queue. It mostly attached institutional membership evidence to
existing canonicals. The one DCA-primary canonical, `New Mexico Museum of Art - Vladem Contemporary`,
should receive normal editorial review before relying on it as a polished Detour stop.

## Working Rule

Do not resolve these queues by inventing coordinates, suppressing source alternates, or treating
official recognition as automatic traveler-facing importance. Resolve by preserving evidence,
marking one canonical display value where appropriate, and adding human review notes when promoting
or suppressing records.
