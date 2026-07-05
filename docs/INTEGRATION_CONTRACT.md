# Detour Integration Contract

This document is the boundary contract between POI Curator (producer) and Detour (consumer).
The two projects are separate repositories joined by this contract. Nothing in this document
grants either side access to the other's internals, and nothing here should be implemented in a
way that collapses the producer / independent-verifier split described below.

There are two contract surfaces:

1. **Frozen file handoff** (current, launch-safe): POI Curator emits a deterministic CSV plus a
   merge manifest; Detour independently verifies the pair before promoting it.
2. **Live `/v1` API** (target hybrid path): Detour may call the public API at runtime behind a
   Detour-side feature flag, with the frozen file remaining the fallback and regression baseline.

## Roles

- **Producer (this repo).** POI Curator owns source ingestion, canonicalization, evidence,
  editorial state, scoring, and export generation. It emits the delivery artifacts and a
  producer-side verification report. The producer-side verifier
  (`poi-curator-export verify-detour-v2`) is a *replica* of Detour's acceptance gate, useful for
  catching failures before handoff. It is not the gate.
- **Verifier (Detour).** Detour runs its own acceptance checks (`qc_pois.py` or successor) on the
  received artifacts before promotion. A producer-side PASS never substitutes for Detour's
  independent check. Detour must not import code from this repo to verify a delivery.

## Surface 1: Frozen File Handoff

### Current delivery artifacts

The current Detour delivery is the **repo-root** pair:

- `query_capable_pois_merged_v2.csv` (501 rows)
- `query_capable_pois_merged_v2_merge_manifest.json`

These were produced by the triaged delivery build (now `poi-curator-export build-detour-v2`,
formerly `scripts/build_detour_v2_delivery.py`) from `reports/query_capable_pois_merged_v1.csv`
plus a human-triaged disposition set.

**Do not confuse them with `reports/query_capable_pois_merged_v2.csv` and
`reports/query_capable_pois_merged_v2_merge_manifest.json`.** Those are output of the earlier
auto-pipeline export (`scripts/export_query_capable_pois_merged_v1.py`), kept as a committed
intermediate/reference artifact. They are *not* the Detour delivery, they have a different row
count, and their manifest has a different shape. Only the repo-root pair is contract-bearing.

### CSV column contract

The delivery CSV has exactly 31 columns, in this order. Columns are grouped by who relies on them.

Detour-required columns (18):

| column | meaning |
| --- | --- |
| `poi_id` | stable canonical POI UUID; never renamed or reissued for the same feature |
| `dedupe_key` | source-shaped identity key, e.g. `osm:way/473190151`; unique per row |
| `name` | display name chosen by strongest identity evidence |
| `lon` | longitude, WGS84 decimal degrees; **order is always `[lon, lat]`; values are never rounded** |
| `lat` | latitude, WGS84 decimal degrees |
| `primary_category` | one of `history`, `art`, `scenic`, `culture`, `civic` |
| `display_priority` | integer display weight (currently `50`, `90` for fixture showcase rows) |
| `quality_score` | numeric derived signal; a review aid, not a measure of cultural worth |
| `walk_affinity_hint` | float 0..1 |
| `drive_affinity_hint` | float 0..1 |
| `wikipedia_title` | optional Wikipedia title |
| `short_description` | short traveler-facing description (draft status; see governance columns) |
| `description_map_v1` | generated map-popup draft |
| `description_card_v1` | generated card draft |
| `description_subcategory_v1` | generated subcategory label |
| `description_confidence_v1` | `high`, `medium`, `low` |
| `description_basis_v1` | pipe-separated basis tokens for the generated description |
| `address` | optional street address |

Optional columns (3): `evidence_sources`, `preferred_aliases`, `active_themes`
(pipe-separated; `active_themes` values are currently limited to `water` and `rail`).

Governance columns (8), required by `docs/DATA_QUALITY_GOVERNANCE.md`:

| column | allowed values |
| --- | --- |
| `record_origin` | `database`, `fixture_overlay`, `manual_export`, `test_fixture` |
| `source_basis` | pipe-separated source-family tokens |
| `evidence_strength` | `high`, `medium`, `low`, `unknown` |
| `description_status` | `none`, `source`, `generated_draft`, `editorial_approved` |
| `description_method` | `source_import`, `deterministic_draft`, `model_draft`, `model_draft_batch`, `editorial` |
| `description_review_status` | `unreviewed`, `needs_revision`, `approved`, `rejected` |
| `claim_basis` | pipe-separated evidence labels backing human-facing claims |
| `risk_flags` | pipe-separated tokens from: `low_confidence`, `low_evidence`, `category_fallback`, `civic_sensitivity`, `culture_sensitivity`, `history_sensitivity`, `synthetic_fixture` |

Audit columns (2), appended by same-feature canonicalization:

| column | meaning |
| --- | --- |
| `merged_from` | pipe-separated `dedupe_key`s collapsed into this row (empty when no merge) |
| `merge_reason` | `osm_relation_members`, `name+proximity`, or both pipe-separated |

Consumption rules for Detour:

- Treat `poi_id` as the stable join key. `dedupe_key` is stable per source snapshot but can change
  if the underlying OSM representation changes across re-ingestions.
- Rows with `record_origin=fixture_overlay` are hand-authored showcase rows, not corpus data.
  Detour may render them but must not treat them as sourced facts.
- Every description column is a **generated draft** unless `description_review_status=approved`.
  In the current delivery all 501 rows are `generated_draft` / `deterministic_draft` /
  `unreviewed`. Displaying drafts is a Detour product decision; treating them as canonical or
  editorially approved copy is a contract violation on either side.
- New columns may be appended in future deliveries (additive change, minor version bump).
  Existing columns are never renamed, dropped, or reordered without a major version bump agreed
  with Detour in advance.

### Geometry and bbox

All coordinates are WGS84 `[lon, lat]`. Every row in a Santa Fe delivery falls inside the bbox:

```text
lon: -106.10 .. -105.80
lat:   35.55 ..   35.78
```

Rows that cannot honestly satisfy this (for example, a linear National Historic Trail whose
anchor sits outside the box) are excluded and documented in the manifest `excluded_rows`, never
coordinate-nudged into compliance.

### Manifest contract

Two manifest schema versions exist. Be explicit about which one you are reading.

**Legacy `schema_version: 1` (the currently committed delivery).** Shape as shipped:

```json
{
  "schema_version": 1,
  "summary": {
    "rows_before": 516,
    "rows_after": 501,
    "clusters_collapsed": 10,
    "clusters_left_colocated": 13,
    "review_candidates": 0
  },
  "clusters": [ ... ],
  "excluded_rows": [ ... ],
  "data_quality_flags": [ ... ]
}
```

Note: the auto-pipeline manifest under `reports/` also says `schema_version: 1` but has a
*different* shape (`review_candidates` / `secondary_flags` keys, no `excluded_rows` or
`data_quality_flags`). That collision is a known legacy defect and one reason this contract
exists. The reports-side manifest is out of contract.

**`schema_version: 2` (stamped by `poi-curator-export build-detour-v2`).** Everything in the
legacy delivery shape, plus provenance of the inputs that produced the export:

```json
{
  "schema_version": 2,
  "contract": "detour-export",
  "inputs": {
    "v1_csv": {"path": "reports/query_capable_pois_merged_v1.csv", "sha256": "...", "rows": 516},
    "dispositions": {"path": "data/detour_v2_dispositions.json", "sha256": "..."}
  },
  "summary": { ...same keys as v1... },
  "clusters": [ ... ],
  "excluded_rows": [ ... ],
  "data_quality_flags": [ ... ]
}
```

Cluster entries carry a `disposition` of `collapsed`, `left_colocated`, or `review_candidate`:

- `collapsed`: `reason` (`osm_relation_members` or `name+proximity`), `survivor_poi_id`,
  `survivor_dedupe_key`, `chosen_display_name`, `alias_names`, and the full `dropped` row list.
- `left_colocated`: `members` list of dedupe_keys deliberately kept distinct.
- `review_candidate`: `members` plus `distance_m`; surfaced for human review, not merged.

The manifest is intentionally timestamp-free so identical inputs produce byte-identical outputs.

Accounting invariants (Detour's gate is expected to check these; the producer-side verifier
checks them too):

- `summary.rows_after` equals the CSV row count.
- Every `collapsed` survivor is present in the CSV; every dropped `dedupe_key` is absent.
- Every `left_colocated` member is present in the CSV.
- No un-dispositioned cluster of rows sharing a significant name token within 35 m remains.
- `dedupe_key` is unique; coordinates are numeric and in-bbox.

### Export versioning rules

- The manifest `schema_version` versions the *manifest shape*.
- CSV shape changes: additive column = document here + note in the delivery message; rename,
  drop, reorder, or semantic change of an existing column = new export generation (a `_v3`
  filename), never a silent mutation of `_v2`.
- `poi_id` values remain stable across deliveries for the same canonical feature.
- Deliveries are deterministic: same inputs and dispositions produce byte-identical outputs.
  Regeneration after re-ingestion is a *new corpus snapshot*, requires re-running relation
  lineage extraction, re-triaging dispositions, and a fresh Detour-side verification pass.

### Out of contract (file surface)

- Everything under `reports/` (intermediates, QA runs, description-enrichment artifacts).
- The disposition file `data/detour_v2_dispositions.json` (producer-internal triage record).
- `reports/osm_relation_lineage.csv` and other lineage/ingest internals.
- Admin/editorial/diagnostic state of any kind.

## Surface 2: Live `/v1` API

Base path `/v1`, served by `apps/api/poi_curator_api`. The backend estimates detour/access cost
geometrically from supplied geometry; it does not compute turn-by-turn routes. Detour keeps
owning baseline route drawing and final rerouting through a selected stop.

Field classes used below:

- **Stable**: Detour may depend on presence, type, and meaning. Removal or rename is a breaking
  change requiring agreement.
- **Advisory**: present today and useful for debugging/telemetry, but shape or content may change
  without notice. Detour must not branch product behavior on these.
- **Excluded**: not part of the contract; may change or disappear at any time.

### `GET /v1/health`

- Stable: `status`, `service`, `scoring_profile_version`.
- Advisory: `environment`.
- Excluded: `scoring_source` (operational diagnostic).

### `GET /v1/config`

- Stable: `supported_regions`, `supported_categories`, `default_detour_budgets_by_mode`
  (map of mode to `{max_detour_meters, max_extra_minutes}`), `scoring_profile_version`.

### `GET /v1/categories`

- Stable: list of `{slug, label, description}`. Current slugs: `history`, `culture`, `art`,
  `scenic`, `food`, `civic`, `mixed`.

### `POST /v1/route/suggest`

Request (stable): `route_geometry` (GeoJSON `LineString`, `[lon, lat]` pairs, at least 2),
`origin` and `destination` (`{name, coordinates: [lon, lat]}`), `travel_mode`
(`driving` | `walking`), `category` (public category slug or `mixed`), `max_detour_meters` (> 0),
`max_extra_minutes` (> 0), `limit` (1..20, default 5). Optional: `theme` (must be query-active;
currently `water` or `rail` — sending an inactive theme is a 422), `region_hint`.

Response:

- Stable envelope: `data_source`, `query_summary`
  (`travel_mode`, `category`, `theme`, `max_detour_meters`, `limit`), `results`.
- Stable per result: `poi_id`, `name`, `primary_category`, `secondary_categories`,
  `coordinates` (`[lon, lat]`), `short_description`, `distance_from_route_m`,
  `estimated_detour_m`, `estimated_extra_minutes`, `score`, `why_it_matters`, `badges`,
  `data_source`.
- Advisory: `category_match_type`, `extended_place` (`place_form`, `encounter_mode`,
  `display_hint`, `encounter_anchors`) — typed and shipping, but its vocabulary is still
  settling.
- Excluded: `score_breakdown` (experimental scoring diagnostics; keys change with the scoring
  profile).

`score` is a deterministic heuristic ranking aid under the announced
`scoring_profile_version`. It is not an objective measure of cultural value and its absolute
scale may shift between scoring profile versions.

### `POST /v1/nearby/suggest`

Request (stable): `center` as `{lat, lon}` **(object with named fields — note this differs from
the `[lon, lat]` arrays used everywhere else)**, `travel_mode`, `category`, `radius_meters` (> 0),
`limit` (1..20, default 10). Optional: `theme`, `region_hint`.

Response: same classes as route/suggest, with `distance_from_center_meters`,
`estimated_access_m`, `estimated_access_minutes` in place of the route-relative fields.

### `POST /v1/point/suggest`

Compatibility wrapper only. It accepts `{location: NamedPoint, radius_meters, ...}` and delegates
to nearby scoring. **Not the preferred Detour integration path** — new Detour code must call
`/v1/nearby/suggest`. This endpoint may be frozen or removed in a future API version.

### `GET /v1/poi/{poi_id}`

- Stable: `poi_id`, `name`, `primary_category`, `secondary_categories`,
  `coordinates` (`[lon, lat]`), `short_description`, `why_it_matters`, `badges`, `themes`
  (list of `{theme_slug, label, status, assignment_basis, confidence, rationale_summary,
  is_query_active, editorial_decision, evidence}`).
- Advisory: `extended_place`; the *presence* of `provenance` and `evidence` objects, plus these
  specific provenance keys: `primary_source`, `osm_id`, `wikidata_id`, `wikipedia_title`.
- Excluded: the internal structure of `provenance.field_sources`, `provenance.raw_source_count`,
  and the raw `evidence` item internals (`source_id`, `evidence_type`, `label`, `text`, `url`,
  `confidence`). These are `dict[str, Any]` passthroughs of editorial internals today. If Detour
  needs them, they get typed and promoted to stable first — do not depend on them as-is.
- 404 with `{"detail": "POI not found"}` for unknown ids.

### Out of contract (API surface)

- All `/v1/admin/*` routes, the admin key header, and every admin response model.
- Editorial diagnostics, match logs, query logs, conflicts, coverage, provenance detail views.
- `/map-test`, `/admin`, `/static`, and the root `/` metadata route.
- FastAPI-generated OpenAPI docs (`/docs`) — informative, not normative.

### Fixture fallback and `data_source`

Every suggestion response and result row carries `data_source`: `database` or
`fixture_fallback`. The hybrid backend falls back to fixture scoring when the database errors or
returns empty and `POI_CURATOR_ALLOW_FIXTURE_FALLBACK` is true (the default).

Policy:

- Fixture fallback is acceptable for local development and tests.
- **Production Detour integration must do at least one of:** run POI Curator with
  `POI_CURATOR_ALLOW_FIXTURE_FALLBACK=false`, or reject/flag any response whose `data_source` is
  not `database`. Fixture-backed responses must never be presented to travelers as corpus data,
  and must never be cited as evidence of corpus quality.

### API versioning

- The path prefix (`/v1`) versions the API shape. Breaking changes require `/v2`.
- `scoring_profile_version` (in `/v1/health` and `/v1/config`) versions ranking behavior
  independently of API shape. Detour should log it alongside any cached suggestions.
- Additive response fields are non-breaking. Detour clients must ignore unknown fields.

## Data governance obligations that cross the boundary

- Generated or templated descriptions remain labeled drafts until editorial review; promotion to
  approved copy happens in this repo's editorial workflow, never Detour-side.
- No synthetic POIs, invented evidence, dates, actors, or historical claims may enter delivery
  artifacts. Fixture rows are always visibly labeled via `record_origin`.
- Suppressed POIs must not appear in public query results or deliveries.
- See `docs/DATA_QUALITY_GOVERNANCE.md` for the full doctrine; where that document and this one
  disagree about governance, that document wins.

## Change management

Changes to either surface land as:

1. a PR in this repo updating this document and the schema models
   (`poi_curator_editorial.export_schema`) together,
2. a version bump per the rules above, and
3. an explicit note in the delivery/release message to Detour.

Detour-side gate changes should be communicated back so the producer-side verifier replica
(`poi-curator-export verify-detour-v2`) can be kept faithful.
