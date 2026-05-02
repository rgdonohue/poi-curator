# GNIS/NMOSE Post-Sprint Followups

Generated: 2026-05-02

Scope: coordination follow-up for the parallel GNIS and NMOSE acequia/POD ingestion sprint after both source branches were reviewed, merged, and verified.

## 1. Integration Status

| Source sprint | Branch | Merge status | Verification status | Outcome report |
|---|---|---|---|---|
| GNIS | `sprint/gnis` | Merged into `main` (`ef0687d`) | Passed full pytest and core-product check suite after merge | `reports/curation_outcomes/20260502_gnis_run.md` |
| NMOSE acequia/POD | `sprint/nmose-acequia` | Merged into `main` (`c53c4ba`) | Passed combined pytest, ruff, mypy, and full check suite | `reports/curation_outcomes/20260502_nmose_acequia_run.md` |

## 2. Duplicate-Review Cases

No new duplicate-review cases were surfaced by either run. The combined database has no `official_match_diagnostic` rows for `gnis`, `nmose_pod`, or `nmose_acequia`, and no new evidence rows tagged `duplicate_review_required`.

| Source | Source record | Candidate POIs | Reason | Decision | Notes |
|---|---|---|---|---|---|
| GNIS | None | None | No ambiguous diagnostics | No action | Three spatial matches were attached; 117 current Santa Fe County records became GNIS-primary canonicals. |
| NMOSE | None | None | No ambiguous diagnostics | No action | Eleven active named POD records became NMOSE-primary canonicals. |

## 3. Naming And Conflict Policy Updates

The combined state now has 92 field-conflict rows: 44 name, 21 coordinates, 21 short description, and 6 primary category. The new pattern is mostly GNIS variant-name disagreement inside a single source family; NMOSE did not surface field-level conflicts because conveyance lines attach evidence only.

| Pattern | Sources involved | Proposed policy | Applied now? | Notes |
|---|---|---|---|---|
| GNIS official/variant name alternates | `gnis` | Treat GNIS variants as sourced alternates; keep current official or reviewed local/common display name canonical. | Yes | Added to `docs/EDITORIAL_NAMING_POLICY.md`. |
| OSE all-caps/shorthand POD labels | `nmose_pod`, `nmose_acequia` | Preserve public OSE label as source evidence; normalize only after review and do not add unpublished steward names without permission. | Yes | Added to `docs/EDITORIAL_NAMING_POLICY.md`. |

## 4. Retained Diagnostics And Unreviewed Records

Neither source produced retained `official_match_diagnostic` rows. GNIS logged nine Santa Fe County historical records as not promoted because they had no canonical match; NMOSE intentionally filtered the full 22,421 Santa Fe County POD layer down to 11 active named conveyance candidates.

| Source | Record count | Category | Next action | Notes |
|---|---:|---|---|---|
| GNIS | 9 | Historical records without canonical match | Leave out of canonical set for now | Historical-only GNIS records should become context only after editorial review or a stronger matching anchor. |
| NMOSE POD | 22,410 filtered from full county layer | Out-of-scope water-rights/well/POD records | Leave out of scope | Adapter intentionally ingests only active PODs tied to meaningful named conveyances. |
| NMOSE acequia | 0 diagnostics | Linear evidence-only source | No diagnostic action | 692 raw conveyance rows were retained as source rows; 24 membership and 31 association evidence rows were attached. |

## 5. Sub-Agent Surface-Area Requests

Track any requests from either branch that should not be handled inside the parallel sprint, such as schema changes, admin workflow needs, matching-threshold proposals, or source-specific policy work.

| Source | Request | Reason | Recommended owner | Priority |
|---|---|---|---|---|
| Both | Consider eliminating duplicate raw `new` match-log rows in future source adapters | Current adapters log the matcher decision and then log canonical creation, so raw rows are double-counted while de-duplicated report counts remain correct. | Ingestion | Medium |
| GNIS | Review broad `Civil` and `Populated Place` canonicals before high-visibility Detour surfacing | GNIS added useful official names but many are broad settlements, grants, or administrative geographies rather than stop-shaped POIs. | Editorial | High |
| NMOSE | Plan permission-aware acequia naming review | Public OSE data omits many names and may use shorthand; steward/local names should not be added without explicit permission. | Editorial/source partnerships | High |

## 6. Combined Verification Notes

After both merges, record the combined verification commands, result summaries, score drift, and baseline decision.

| Check | Command | Result | Notes |
|---|---|---|---|
| pytest | `.venv/bin/python -m pytest` | Passed | 174 passed. |
| ruff | `.venv/bin/ruff check .` | Passed | Required a formatting-only wrap in the existing multi-source migration SQL. |
| mypy | `.venv/bin/mypy apps packages tests` | Passed | No issues in 89 source files. |
| check suite | `.venv/bin/python scripts/run_check_suite.py --suite core-product` | Passed | 6/6 passed; output `reports/check_runs/20260502T144735Z/`. |
| full saved check suite | `.venv/bin/python scripts/run_check_suite.py --suite core-product --suite all-fixtures --suite empty-result-guardrails --suite rail-smoke --split-cases` | Passed | 28/28 passed; promoted to `reports/check_runs/20260502T_gnis_nmose_baseline/`. |

## 7. Final Follow-Up Decisions

- Duplicate-review triage: complete; no new cases.
- Naming policy updates: complete for GNIS variants and public OSE label handling.
- Retained diagnostics triage: complete; no new diagnostics, with GNIS historical no-promote and NMOSE POD filtering documented above.
- Check-suite baseline promotion: complete; `reports/check_runs/20260502T_gnis_nmose_baseline/` is the promoted post-sprint baseline.
