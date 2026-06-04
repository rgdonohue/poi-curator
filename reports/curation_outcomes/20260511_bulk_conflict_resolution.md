# Bulk Conflict Resolution Outcome

Date: 2026-05-11

Scope: live local database after the NM HPD/NM DCA sprint. This pass did not delete alternate
source values or change schema. It normalized `poi_field_provenance.is_canonical` so known
conflict patterns have one display-canonical provenance row while preserving alternates in the
admin conflict surface.

## Conflict Counts

`poi_field_conflicts` still reports 276 rows because the view intentionally surfaces preserved
source disagreement. The practical before/after metric is whether a conflicted field has exactly
one provenance row marked canonical.

| Field | Conflict rows | Before: exactly one canonical | Before: multi/no canonical | After: exactly one canonical | After: multi/no canonical |
|---|---:|---:|---:|---:|---:|
| name | 130 | 108 | 22 | 130 | 0 |
| short_description | 92 | 57 | 35 | 92 | 0 |
| coordinates | 34 | 27 | 7 | 34 | 0 |
| primary_category | 18 | 10 | 8 | 18 | 0 |
| gnis_feature_id | 1 | 0 | 1 | 0 | 1 |
| street_address | 1 | 0 | 1 | 0 | 1 |

The two non-policy fields, `gnis_feature_id` and `street_address`, were left untouched.

## Policy Rules Added

- Short descriptions: OSM/common-use descriptions are display-canonical when available. NRHP/HPD
  register boilerplate remains sourced alternate evidence. Rows without a common-use description
  are flagged for editorial description review.
- Register-order names: the existing Last-First-Type rule now applies at scale across NRHP and HPD
  provenance.
- Coordinates: OSM remains display-canonical when present because it matches current POI placement.
  Without OSM, the coordinate source closest to the current canonical centroid is marked
  provenance-canonical. Address-geocoded coordinates are review aids only.
- Primary categories: OSM/common-use categories remain primary for display; register `history`
  categories remain sourced alternates. No schema tweak was needed because `display_categories` and
  field provenance already preserve alternate category basis.

## Resolution Summary

| Pattern | Rows handled | Outcome |
|---|---:|---|
| Short-description conflicts with OSM/common-use description | 57 | Auto-resolved to OSM/common-use display provenance. |
| Short-description conflicts without common-use description | 35 | Provisional canonical row normalized; POIs flagged in editorial notes for manual description review. |
| Name conflicts with Last-First-Type register pattern | 24 | Applied common-display-name policy; register names retained as alternates. |
| Other name conflicts, mostly GNIS variants and formal suffixes | 106 | Existing display name retained as canonical provenance; variants retained. |
| Coordinate conflicts | 34 | OSM preferred where present; otherwise closest source to current centroid. |
| Primary-category conflicts | 18 | Common-use/current display category retained; register categories preserved as alternates. |

Policy logs were written to `poi_match_log` with `candidate_source='editorial_policy'` for the
152 rows whose canonical provenance state changed from multi-canonical or otherwise ambiguous.

## Residual Review Queue

Thirty-five short-description conflicts lack an OSM/common-use description. These are resolved only
in the narrow provenance sense: exactly one row is marked canonical so the admin viewer can
highlight a current display value. They still need editorial prose because all available values are
register or GNIS evidence labels rather than traveler-facing descriptions.

No schema changes were requested by this pass.
