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

## GNIS/NMOSE Source Sprint Verification — 2026-05-02

Changes merged:
- `sprint/gnis` (`ef0687d`): added GNIS pipe-delimited text ingestion, source documentation,
  unit coverage, and `reports/curation_outcomes/20260502_gnis_run.md`.
- `sprint/nmose-acequia` (`c53c4ba` merge): added public NMOSE POD and acequia conveyance
  ingestion, source documentation, unit coverage, and
  `reports/curation_outcomes/20260502_nmose_acequia_run.md`.
- `docs/EDITORIAL_NAMING_POLICY.md`: added rules for GNIS variant names and public OSE
  acequia/POD labels.
- `reports/curation_outcomes/20260502_post_sprint_followups.md`: records duplicate-review,
  diagnostics, policy, and verification follow-ups.

Database curation outcomes:
- Active canonical POIs after both runs: 686.
- Source-primary additions from this sprint: 117 `gnis` canonicals and 11 `nmose_pod`
  canonicals.
- Evidence added by the runs: 120 GNIS official-name rows, 108 GNIS variant-name rows,
  11 NMOSE POD rows, 24 NMOSE acequia-membership rows, and 31 NMOSE acequia-association rows.
- No new duplicate-review cases or ambiguous diagnostics were surfaced for `gnis`, `nmose_pod`,
  or `nmose_acequia`.
- Field conflicts now total 92 rows: 44 name, 21 coordinates, 21 short description, and
  6 primary category. New name conflicts are mostly GNIS variant-name alternates.

Verification:
- `.venv/bin/python -m pytest` - 174 passed.
- `.venv/bin/ruff check .` - passed after a formatting-only line wrap in
  `migrations/versions/20260501_0011_multi_source_provenance.py`.
- `.venv/bin/mypy apps packages tests` - passed with no issues in 89 source files.
- `.venv/bin/python scripts/run_check_suite.py --suite core-product` - 6 passed, 0 failed.
  Output directory: `reports/check_runs/20260502T144735Z/`.
- Full saved check-suite run:
  `.venv/bin/python scripts/run_check_suite.py --suite core-product --suite all-fixtures --suite empty-result-guardrails --suite rail-smoke --split-cases`
  - 28 passed, 0 failed. Output directory: `reports/check_runs/20260502T144858Z/`.

Score drift and baseline decision:
- The full suite still passes all 28 saved case runs after 128 source-primary additions.
- Core expected anchors and ordering remained stable for the product-critical cases; new GNIS and
  NMOSE records did not displace existing expected results.
- Water-theme evidence improved materially at the corpus level through NMOSE acequia/POD evidence,
  but the current scoring fixtures still return the existing Acequia Madre anchor rather than new
  POD canonicals, which is appropriate until those records receive editorial review.
- Promoted the post-sprint full run to
  `reports/check_runs/20260502T_gnis_nmose_baseline/` and updated `README.md` to point to it.

## Stash Review 20260502

Reviewed `stash@{0}` (`On sprint/gnis: pre-merge nmose and coordination artifacts`) against
current `main`.

Findings:
- `packages/ingestion/poi_curator_ingestion/sources/nmose_acequia.py`,
  `tests/unit/test_nmose_acequia.py`, and
  `reports/curation_outcomes/20260502_nmose_acequia_run.md` are byte-for-byte identical to files
  already committed on `main`.
- `docs/SOURCES.md` contains the pre-merge NMOSE source documentation; current `main` has that
  content plus the GNIS section from the serial merge, so the stash copy is superseded.
- `reports/curation_outcomes/20260502_post_sprint_followups.md` is the pre-integration scaffold;
  current `main` has the completed follow-up report, so the stash copy is superseded.
- `reports/check_runs/20260502T144047Z/` and `reports/check_runs/20260502T144229Z/` are
  intermediate sub-agent/core-product check outputs. They are superseded by committed post-merge
  verification outputs, including `reports/check_runs/20260502T144735Z/`,
  `reports/check_runs/20260502T144858Z/`, and the promoted
  `reports/check_runs/20260502T_gnis_nmose_baseline/`.

No genuinely lost work was found in the stash. It is safe to drop after the required local-delete
confirmation.

## GNIS Policy Refinement Verification — 2026-05-02

Policy change:
- GNIS canonical creation is now limited to stop-shaped classes: Canal, Spring, Summit, Valley,
  Church, Cemetery, Park, Trail, and School.
- Civil, Populated Place, Locale, and Building are evidence-only classes. Broad GNIS-primary
  canonicals from the previous run were demoted to curator review instead of deleted.

Database curation outcomes:
- Demoted 104 active GNIS-primary canonicals: 41 Civil, 62 Populated Place, and 1 Military.
- 6 demoted records found a nearby non-GNIS canonical within 150m and had GNIS evidence attached;
  98 had no nearby canonical and were queued as `gnis_demoted_pending_review`.
- Re-ran the GNIS adapter against the source feed. It created 160 newly eligible stop-shaped
  canonicals: 74 Valley, 58 Summit, and 28 Spring. Active GNIS-primary canonicals now total 173,
  all in allowed canonical classes.
- No active Civil, Populated Place, Locale, Building, or Military GNIS-primary canonicals remain.

Verification:
- `.venv/bin/python -m pytest` - 177 passed.
- `.venv/bin/ruff check .` - passed.
- `.venv/bin/mypy apps packages tests` - passed with no issues in 89 source files.
- Full saved check-suite run:
  `.venv/bin/python scripts/run_check_suite.py --suite core-product --suite all-fixtures --suite empty-result-guardrails --suite rail-smoke`
  - 28 passed, 0 failed. Output directory: `reports/check_runs/20260502T154929Z/`.
- Admin viewer smoke check: POI List with `review_state='gnis_demoted_pending_review'` showed
  the demoted GNIS review queue, and Coverage showed active-canonical coverage
  (`total_pois=742`, `by_source.gnis=185`, `single_source_gaps.gnis=173`).

Score drift and baseline decision:
- Compared with `reports/check_runs/20260502T_gnis_nmose_baseline/`, saved check-suite top
  results and rounded scores were unchanged.
- No baseline promotion is needed for this refinement.

Sanity check append - 2026-05-11:
- Pre-refinement active GNIS-primary canonicals were 117 total: 62 `Populated Place`, 41 `Civil`,
  13 `Canal`, and 1 `Military`. Of these, only the 13 `Canal` records are in the refined
  canonical-eligible class list.
- The pre-refinement adapter filter in `HEAD` was narrower and only admitted `Canal`, `Civil`,
  `Crossing`, `Military`, and `Populated Place`; it did not admit `Spring`, `Summit`, or `Valley`.
  The 160 new active GNIS-primary canonicals from the rerun are therefore net-new eligible
  records, not duplicate recreation of prior GNIS canonicals.
- Source-file counts for the newly admitted classes in Santa Fe County were 29 `Spring`,
  62 `Summit`, and 74 `Valley` records. The active new set is 28 `Spring`, 58 `Summit`, and
  74 `Valley`: `Spring 8`, `Cerro Gordo`, `Sun Mountain`, and `Tano Point` matched existing
  canonicals, while `Atalaya Mountain` was logged as ambiguous with two candidates.
- The 13 existing `Canal` canonicals were matched on rerun and not duplicated.
- No `Church`, `Cemetery`, `Park`, `Trail`, or `School` Santa Fe County records exist in the
  downloaded GNIS New Mexico source file used by the adapter. Their absence from the active set is
  source-data absence, not filtering loss or missed attachment.

## NM HPD / NM DCA Source Sprint Verification — 2026-05-11

Changes merged:
- `sprint/nm-hpd` (`550c787`): added NM HPD State Register ingestion, CLI command, unit tests,
  source documentation, `reports/curation_outcomes/20260511_nm_hpd_legacy_audit.md`, and
  `reports/curation_outcomes/20260511_nm_hpd_run.md`.
- `sprint/nm-dca` (`5c611f4`): added NM DCA institution ingestion, unit tests, source
  documentation, and `reports/curation_outcomes/20260511_nm_dca_run.md`.
- Main-agent docs: updated source ecology, strategic notes, naming policy, README status,
  `docs/EDITORIAL_BACKLOG.md`, and
  `reports/curation_outcomes/20260511_post_sprint_followups.md`.

Database curation outcomes:
- Active canonical POIs after the sprint: 743.
- NM HPD created no canonicals because the current public State Register workbook has no
  coordinates. It attached 78 State Register evidence rows and retained 136 current no-coordinate
  diagnostics.
- NM HPD legacy reconciliation marked 17 legacy diagnostics superseded, 73 retained unreviewed,
  and 1 out of scope.
- NM DCA attached 6 institutional membership evidence rows and created 1 DCA-primary canonical:
  `New Mexico Museum of Art - Vladem Contemporary`.
- Admin Coverage shows `nm_hpd=78` and `nm_dca=6` in source coverage, with active total 743.

Verification:
- HPD post-merge gate: `.venv/bin/python -m pytest` - 179 passed; core check suite - 6 passed at
  `reports/check_runs/20260511T104850Z/`.
- Final combined `.venv/bin/python -m pytest` - 188 passed.
- `.venv/bin/ruff check .` - passed.
- `.venv/bin/mypy apps packages tests` - passed with no issues in 93 source files.
- Full saved check-suite run:
  `.venv/bin/python scripts/run_check_suite.py --suite core-product --suite all-fixtures --suite empty-result-guardrails --suite rail-smoke`
  - 28 passed, 0 failed. Output directory: `reports/check_runs/20260511T105213Z/`.
- Admin viewer smoke check: Coverage tab showed `nm_hpd` and `nm_dca` source counts.

Score drift and baseline decision:
- Compared with `reports/check_runs/20260502T_gnis_nmose_baseline/`, two history/plaza cases
  drifted as expected from HPD/DCA institutional evidence. Palace of the Governors rose from 77.4
  to 81.0 in `nearby-plaza-history`, New Mexico History Museum entered the top five, and Palace of
  the Governors entered the `route-historic-center-driving` top five.
- Expected anchors still pass. The drift is legitimate institutional corroboration, not a matcher
  regression.
- Promoted `reports/check_runs/20260511T105213Z/` to
  `reports/check_runs/20260511T_hpd_dca_baseline/` and updated `README.md` to point to it.

## Bulk Conflict Resolution / HPD Geocoding Follow-Up — 2026-05-11

Database curation outcomes:
- Applied field-provenance policy to the 274 name, short-description, coordinate, and
  primary-category conflict rows. Each now has exactly one provenance row marked canonical; source
  alternates remain visible in `poi_field_conflicts`.
- Left `gnis_feature_id` and `street_address` conflicts untouched because they are outside the
  display-field policy.
- Flagged 35 short-description conflicts for editorial prose review because they have no
  OSM/common-use description source.
- Ran the HPD address-geocoding pass over 136 retained `nm_hpd` no-coordinate diagnostics:
  64 resolved to Santa Fe County geocodes and were queued as `geocoded_candidate_review`; 72 remain
  unreviewed because of missing addresses, no Nominatim result, or an out-of-county result.
- No geocoded HPD records matched existing canonicals under the current matcher thresholds, so no
  `geocoded_coordinate` evidence rows were attached and no canonicals were promoted.

Verification:
- `.venv/bin/python -m pytest` - 188 passed.
- `.venv/bin/ruff check .` - passed.
- `.venv/bin/mypy apps packages tests` - passed with no issues in 93 source files.
- Full saved check-suite run:
  `.venv/bin/python scripts/run_check_suite.py --suite core-product --suite all-fixtures --suite empty-result-guardrails --suite rail-smoke`
  - 28 passed, 0 failed. Output directory: `reports/check_runs/20260511T112319Z/`.

Score drift and baseline decision:
- Compared with `reports/check_runs/20260511T_hpd_dca_baseline/`, rounded result names, scores,
  primary categories, and short descriptions were unchanged for every check case.
- No baseline promotion is needed because this pass changed provenance flags, diagnostics, and
  review queues rather than active scoring inputs.
