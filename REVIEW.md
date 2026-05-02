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

## Post-Remediation Verification — 2026-04-30T17:44:52Z

Setup:
- `make db-up` started `poi-curator-db` after Docker Desktop was launched.
- `make migrate` applied Alembic migrations successfully.
- `psql postgresql://poi_curator:poi_curator@localhost:5432/poi_curator -c "select 1 as reachable"`
  confirmed DB reachability.

Pytest summary:
- `.venv/bin/python -m pytest -v` - 143 passed, 0 failed, 0 skipped.
- Previously skipped DB-backed tests ran and passed, including
  `test_osm_reset_clears_dependent_rows_without_orphans`,
  `test_deactivate_stale_osm_pois_marks_missing_current_batch_inactive`, and the 9 DB-backed
  admin editorial tests in `tests/unit/test_admin_editorial.py`.
- Failures: none.

Check suite summary:
- `python3 scripts/run_check_suite.py ...` failed because system `python3` does not have the
  editable package environment (`ModuleNotFoundError: poi_curator_domain`).
- Equivalent repo-runtime command used:
  `.venv/bin/python scripts/run_check_suite.py --suite core-product --suite all-fixtures --suite empty-result-guardrails --suite rail-smoke --split-cases`.
- Output directory: `reports/check_runs/20260430T174322Z/`.
- `core-product`: 6 passed, 0 failed.
- `all-fixtures`: 14 passed, 0 failed.
- `empty-result-guardrails`: 4 passed, 0 failed.
- `rail-smoke`: 4 passed, 0 failed.
- Total suite runs: 28 passed, 0 failed.

Baseline diff:
- Prior baseline: `reports/check_runs/20260408T_history_validation_final/index.md`.
- New run: `reports/check_runs/20260430T174322Z/index.md`.
- Total suite-run count delta: 28 new vs 20 baseline, delta +8.
- Unique case id delta: 14 new vs 14 baseline, delta 0.
- Regressions: none. No baseline-passing shared suite run failed in the new run.
- Improvements: none. The baseline had no failing shared suite runs.
- New suite runs: `empty-result-guardrails` (`nearby-plaza-water-empty`,
  `nearby-plaza-rail-empty`, `nearby-downtown-scenic-empty`,
  `route-downtown-scenic-empty`) and `rail-smoke` (`nearby-railyard-civic`,
  `nearby-railyard-rail`, `route-railyard-civic`, `route-railyard-rail`).
- Score/order drift notes:
  - `nearby-plaza-history`: The Santa Fe Plaza moved from rank 3 score 71.3 to rank 2 score
    73.3. Drift came from point proximity/radius-fit components (`distance_from_center_m=100`
    baseline vs 48 new) while all expectations still passed.
  - `route-historic-center-driving`: `Kruger Building` and `Gregorio Crespín House` both score
    78.4; order is now stable as `Kruger Building` before `Gregorio Crespín House`, consistent
    with the Phase 4 deterministic tie-breaker.

Determinism check:
- Ran `core-product` twice against the same DB state:
  `reports/check_runs/20260430T174415Z/` and `reports/check_runs/20260430T174418Z/`.
- Pass/fail outcomes: identical, 6 passed and 0 failed in both runs.
- Per-case score values: identical.
- Result POI ordering: identical.

## NRHP Follow-up Verification — 2026-05-01

Changes made:
- `tests/integration/test_multi_source_ingestion.py`: fixed the integration fixture cleanup that
  deleted all `candidate_source = 'nrhp'` match logs. Cleanup now removes only fixture-owned NRHP
  reference IDs.
- `tests/unit/test_check_suites.py`: added a regression that inserts a production-style NRHP
  match-log row, runs the check suite, and asserts the row is preserved.
- `data/fixtures/eval_santa_fe.json`: promoted the editorial naming baseline from
  `The Santa Fe Plaza` to `Santa Fe Plaza`.
- `docs/EDITORIAL_NAMING_POLICY.md`: documented canonical display-name policy for register-order
  person names, accents, leading articles, parenthetical labels, and infrastructure names.
- Curation reports added under `reports/curation_outcomes/` for NRHP duplicate resolutions and
  retained diagnostics triage.

Database curation outcomes:
- NRHP duplicate review: 4 duplicate NRHP-only canonicals were merged into existing common-name
  canonicals and marked `superseded`; 2 district/scope cases were kept separate with legacy
  evidence moved to the NRHP canonical.
- Retained legacy diagnostics: 11 queued for next coordinate pass, 7 marked out of scope for now,
  and 1 marked for manual curator coordinate review.
- Field-level provenance: every current conflict row has exactly one canonical value flagged in
  `poi_field_provenance`.

Verification:
- `.venv/bin/python -m pytest` - 166 passed.
- `.venv/bin/ruff check tests/integration/test_multi_source_ingestion.py tests/unit/test_check_suites.py docs/EDITORIAL_NAMING_POLICY.md` - passed.
- `.venv/bin/python scripts/run_check_suite.py --suite core-product` - 6 passed, 0 failed.
  Output directory: `reports/check_runs/20260501T040459Z/`.
- Post-check-suite match-log preservation: `poi_match_log` still contains 61 NRHP rows
  (`18 match`, `43 new`).

Baseline drift:
- `nearby-plaza-history` now reports `Santa Fe Plaza` instead of `The Santa Fe Plaza`. This is an
  intentional editorial naming-policy drift, not a scoring regression.
- Score/order remained stable relative to the prior NRHP run: `Santa Fe Plaza` remains rank 2 with
  score 73.3, behind `Palace of the Governors` at 77.4.
- The expected-name fixture baseline was promoted to `Santa Fe Plaza` so future check-suite runs
  enforce the new canonical display policy.
- Determinism result: pass.

Baseline promotion decision:
- Promoted `reports/check_runs/20260430T174322Z/` to
  `reports/check_runs/20260430T_post_remediation_baseline/`.
- Updated `README.md` to point to
  `reports/check_runs/20260430T_post_remediation_baseline/index.md`.

Regression fixes applied during this pass:
- None.

Remediation 3b3a20a verified end-to-end against PostGIS.
