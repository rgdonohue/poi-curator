## Remediation Log

### 2026-04-30T17:09:49Z - Phase 1: Admin Access Control

Files modified:
- `.env.example`: documented `POI_CURATOR_ADMIN_KEY` with a local placeholder.
- `apps/api/poi_curator_api/routes/admin.py`: added a router-level FastAPI dependency that
  requires `X-POI-Curator-Admin-Key` to match `POI_CURATOR_ADMIN_KEY`.
- `packages/domain/poi_curator_domain/settings.py`: added the `admin_key` setting.
- `tests/unit/test_api.py`: added admin-key tests for missing, invalid, and valid keys.
- `tests/unit/test_admin_editorial.py`: configured the admin key for DB-backed admin tests.
- `tests/integration/test_db_query_paths.py`: configured the admin key for DB-backed admin tests.

New tests:
- `test_admin_poi_evidence_endpoint_requires_api_key`: asserts admin evidence returns `401`
  without a key or with the wrong key, and succeeds with the configured key.

Additional risks found:
- None.

Verification:
- `.venv/bin/python -m pytest tests/unit/test_api.py` - 14 passed.
- `.venv/bin/python -m pytest tests/unit/test_admin_editorial.py` - 9 skipped because local
  Postgres is unavailable.

### 2026-04-30T17:14:03Z - Phase 2: Canonical Overwrite and Evidence Audit Trail

Files modified:
- `packages/ingestion/poi_curator_ingestion/pipeline.py`: protected reviewed title,
  category, and description fields from OSM re-upsert overwrites and emits an unreviewed
  diagnostic when incoming OSM values are skipped.
- `packages/enrichment/poi_curator_enrichment/pipeline.py`: added Wikidata source registry
  maintenance and a Wikidata evidence upsert before canonical identity fields are written.
- `tests/unit/test_osm_ingestion_pipeline.py`: added a targeted OSM overwrite-protection unit
  test.
- `tests/unit/test_wikidata_enrichment.py`: updated Wikidata enrichment tests for the evidence
  upsert and added evidence payload assertions.

New tests:
- `test_osm_upsert_does_not_overwrite_reviewed_canonical_field`: asserts reviewed canonical
  title, category, and description fields are preserved while non-protected raw summaries update.
- `test_apply_wikidata_entity_creates_evidence_before_canonical_write`: asserts a Wikidata
  evidence row and source registry row are created alongside the canonical identity write.

Additional risks found:
- None.

Verification:
- `.venv/bin/python -m pytest tests/unit/test_osm_ingestion_pipeline.py tests/unit/test_wikidata_enrichment.py` -
  6 passed.

### 2026-04-30T17:17:37Z - Phase 3: FK Cascade Safety on Evidence Refresh and OSM Reset

Files modified:
- `packages/ingestion/poi_curator_ingestion/pipeline.py`: documented OSM reset delete order,
  added child-first dependent cleanup for aliases, diagnostics, theme memberships, membership
  evidence links, evidence, editorial state, and signals, and rolls back the reset on failure.
- `packages/enrichment/poi_curator_enrichment/pipeline.py`: added child-first evidence refresh
  cleanup for theme membership evidence links, wrapped refresh writes in rollback-on-failure blocks,
  and preserved reviewed match diagnostics during refresh.
- `tests/integration/test_reset_delete_order.py`: added a Postgres-backed reset dependency cleanup
  integration test.

New tests:
- `test_osm_reset_clears_dependent_rows_without_orphans`: creates an OSM POI with raw source,
  evidence, alias, editorial, diagnostic, theme membership, and membership evidence rows, then
  resets the region and asserts dependent rows are gone.

Additional risks found:
- None.

Verification:
- `.venv/bin/python -m pytest tests/integration/test_reset_delete_order.py tests/unit/test_wikidata_enrichment.py` -
  5 passed, 1 skipped because local Postgres is unavailable.

### 2026-04-30T17:18:53Z - Phase 4: Deterministic Result Ordering

Files modified:
- `packages/scoring/poi_curator_scoring/query_service.py`: added `POI.poi_id` ordering to DB
  candidate queries and uses `(-score, poi_id)` as the final stable sort key for route and nearby
  suggestions.
- `packages/scoring/poi_curator_scoring/engine.py`: applies the same `(-score, poi_id)` tiebreaker
  in fixture route and nearby suggestions.
- `tests/unit/test_api.py`: added a repeated route suggestion assertion for stable result order.

New tests:
- `test_route_suggest_order_is_stable_for_repeated_query`: runs the same route suggestion request
  twice and asserts the result POI id order is identical.

Additional risks found:
- None.

Verification:
- `.venv/bin/python -m pytest tests/unit/test_api.py tests/unit/test_db_point_scoring.py` -
  26 passed.

### 2026-04-30T17:20:42Z - Phase 5: API Coordinate Validation

Files modified:
- `packages/domain/poi_curator_domain/schemas.py`: added finite and longitude/latitude range
  validation for route LineStrings, named points, and nearby center points.
- `apps/api/poi_curator_api/main.py`: sanitizes validation error payloads so non-finite inputs
  return HTTP 422 instead of failing response serialization.
- `tests/unit/test_api.py`: added public endpoint tests for invalid route, nearby, and point
  coordinates.

New tests:
- `test_route_suggest_rejects_out_of_range_coordinate`: asserts route coordinates outside longitude
  range return 422.
- `test_route_suggest_rejects_single_point_linestring`: asserts degenerate LineStrings return 422.
- `test_nearby_suggest_rejects_non_finite_coordinate`: asserts non-finite center coordinates return
  422 with a descriptive message.
- `test_point_suggest_rejects_out_of_range_coordinate`: asserts point latitude outside range returns
  422.

Additional risks found:
- None.

Verification:
- `.venv/bin/python -m pytest tests/unit/test_api.py` - 19 passed.

### 2026-04-30T17:22:35Z - Phase 6: Stale Canonical Records on Source Removal

Files modified:
- `packages/ingestion/poi_curator_ingestion/pipeline.py`: tracks normalized OSM ids during full
  ingest, deactivates active OSM canonical POIs absent from the normalized batch, logs the count,
  and reactivates stale POIs that reappear.
- `packages/ingestion/poi_curator_ingestion/cli.py`: added `--no-deactivate-stale` to OSM ingest
  and rebuild commands and reports `stale_deactivated`.
- `tests/integration/test_reset_delete_order.py`: added stale OSM deactivation integration coverage.

New tests:
- `test_deactivate_stale_osm_pois_marks_missing_current_batch_inactive`: creates current and stale
  OSM POIs, runs stale deactivation, and asserts only the absent POI is marked inactive/stale.

Additional risks found:
- None.

Verification:
- `.venv/bin/python -m pytest tests/unit/test_osm_ingestion_pipeline.py tests/integration/test_reset_delete_order.py` -
  1 passed, 2 skipped because local Postgres is unavailable.

### 2026-04-30T17:29:18Z - Phase 7: Lint and Type Errors

Files modified:
- `packages/domain/poi_curator_domain/theme_service.py`, `packages/domain/poi_curator_domain/themes.py`,
  `packages/scoring/poi_curator_scoring/engine.py`, `packages/scoring/poi_curator_scoring/evaluation.py`,
  `packages/scoring/poi_curator_scoring/query_service.py`, `packages/scoring/poi_curator_scoring/checks.py`,
  and `packages/editorial/poi_curator_editorial/service.py`: resolved theme `Literal` typing at
  string/DB boundaries.
- `tests/` helpers and check-suite tests: added missing annotations and typed fixture values.
- Formatting-only line-wrap/import cleanup in migrations, scoring representation, and integration
  tests from `ruff --fix` plus remaining manual wraps.

New tests:
- None. This phase was lint/type cleanup only.

Additional risks found:
- None.

Verification:
- `.venv/bin/ruff check .` - passed.
- `.venv/bin/mypy apps packages tests` - passed with no issues.
- `.venv/bin/python -m pytest` - 124 passed, 19 skipped because local Postgres is unavailable.
- `.venv/bin/python scripts/run_check_suite.py --suite core-product` - failed because PostGIS is
  not running on `localhost:5432` (connection refused).
