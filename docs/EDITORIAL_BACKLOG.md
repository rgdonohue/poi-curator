# Editorial Backlog

Last updated: 2026-05-11

This page consolidates source-driven curation queues so editorial work can be selected from one
place. Counts reflect the live local Santa Fe database after the GNIS/NMOSE and NM HPD/NM DCA
source sprints, the 2026-05-11 bulk conflict-resolution pass, and the HPD address-geocoding pass.

## Summary

| Queue | Count | Source | Current handling |
|---|---:|---|---|
| GNIS-demoted records | 104 | GNIS | Review for possible promotion; 98 have no nearby attachment, 6 also attached evidence to nearby canonicals. |
| Field-level conflicts | 276 | Multi-source | All name, short-description, coordinate, and primary-category conflicts now have exactly one canonical provenance row; 35 short-description rows still need editorial prose. |
| HPD no-coordinate diagnostics | 72 | NM HPD | Current State Register records still lacking usable coordinates after the address-geocoding pass. |
| Geocoded HPD candidates | 64 | NM HPD + Nominatim | Address-derived coordinates queued for human review; no automatic canonical promotion. |
| Legacy HPD retained diagnostics | 73 | NM HPD legacy | Still unreviewed after reconciliation; evaluate against current State Register workbook. |
| Legacy NRHP diagnostics | 21 | NRHP legacy | 11 queued for next ingest/manual coordinates, 1 manual-review case, and 9 out-of-scope rows retained for audit context. |
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

Bulk policy status:

- Name, coordinate, primary-category, and short-description conflicts have one highlighted
  provenance-canonical value after the 2026-05-11 bulk conflict pass.
- Thirty-five short-description rows lack an OSM/common-use description and need editorial prose
  review even though their provenance-canonical row is normalized.
- `gnis_feature_id` and `street_address` remain visible source disagreements outside the naming and
  display-field policy.

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
POIs. The 2026-05-11 address-geocoding pass resolved 64 retained diagnostics to Santa Fe County
coordinates and queued them as `geocoded_candidate_review`; these are candidate canonicals only,
not automatic promotions.

Next editorial decision needed:

- whether to establish a manual coordinate-entry policy for high-value HPD records
- whether to promote any `geocoded_candidate_review` rows after side-by-side review
- whether district designations should link to more granular member POIs where defensible
- whether retained legacy workbook diagnostics should be closed after manual review

### NRHP

NRHP retained diagnostics remain from the legacy CSV reconciliation. Eleven are queued for a next
ingest or manual-coordinate pass, one is still marked `manual_review`, and nine out-of-scope rows
are retained for audit context. The reviewable rows should be considered alongside HPD
no-coordinate records because the underlying issue is similar: formal register recognition without
usable public geometry.

### NM DCA

DCA produced no large editorial queue. It mostly attached institutional membership evidence to
existing canonicals. The one DCA-primary canonical, `New Mexico Museum of Art - Vladem Contemporary`,
should receive normal editorial review before relying on it as a polished Detour stop.

## Working Rule

Do not resolve these queues by inventing coordinates, suppressing source alternates, or treating
official recognition as automatic traveler-facing importance. Resolve by preserving evidence,
marking one canonical display value where appropriate, and adding human review notes when promoting
or suppressing records.
