# NM HPD / NM DCA Post-Sprint Followups

Date: 2026-05-11

## Integration

`sprint/nm-hpd` was merged first and passed the post-merge gate:

- `pytest`: 179 passed.
- Core check suite: 6 passed at `reports/check_runs/20260511T104850Z/`.

`sprint/nm-dca` was merged second. Combined verification passed.

## Duplicate-Review Cases

No HPD or DCA ambiguous match-log decisions were produced in the live database.

| Source | Case | Status | Notes |
|---|---|---|---|
| NM HPD | None from new run | Closed | HPD unmatched rows were retained as no-coordinate diagnostics rather than duplicate-review cases. |
| NM DCA | None from new run | Closed | DCA produced five attachments and one new canonical; no ambiguity. |

## Retained Diagnostics

| Source | Count | Category | Notes |
|---|---:|---|---|
| NM HPD | 136 | current-no-coordinate | Current Santa Fe County State Register records without coordinates; retained as `nm_hpd` diagnostics. |
| NM HPD legacy | 73 | retained-unreviewed | Legacy `nm_hpd_register_workbook` diagnostics that remain current but were not superseded by the new run. |
| NM HPD legacy | 17 | superseded | Legacy diagnostics superseded by new HPD evidence attachments. |
| NM HPD legacy | 1 | out-of-scope | Non-source/test row marked out of scope. |
| NM DCA | 0 | retained diagnostics | DCA used direct evidence attachment/new-canonical path. |

## Naming Policy Followups

Observed patterns:

- HPD State Register inverted person-building names follow the existing NRHP register-name rule.
- HPD register qualifiers such as `NHL` should remain sourced alternates unless needed for
  disambiguation.
- DCA source names corroborate public-facing museum/campus labels; parent institution names should
  not override clearer campus display names.

Action taken:

- Updated `docs/EDITORIAL_NAMING_POLICY.md` with HPD and DCA naming rules.
- Existing HPD/DCA name provenance already marks OSM/common names canonical for matched records.
  The only HPD/DCA canonical name row is the DCA-primary `New Mexico Museum of Art - Vladem
  Contemporary`.

## Editorial Backlog Updates

See `docs/EDITORIAL_BACKLOG.md` for the consolidated current backlog.

Added or updated items:

| Source | Backlog item | Count | Notes |
|---|---|---:|---|
| GNIS | demoted review queue | 104 | Includes 98 no-nearby-canonical records and 6 demoted records with nearby evidence attachments. |
| Multi-source | field conflicts | 276 | Name and short-description conflicts increased after HPD/DCA evidence. |
| NM HPD | current no-coordinate diagnostics | 136 | Main new editorial queue from this sprint. |
| NM HPD legacy | retained-unreviewed diagnostics | 73 | Still current after reconciliation. |
| NRHP legacy | retained diagnostics | 19 | Carried forward from NRHP reconciliation. |
| NM DCA | DCA-primary canonical review | 1 | `New Mexico Museum of Art - Vladem Contemporary`. |

## Verification Notes

- Final combined `pytest`: 188 passed.
- `ruff check .`: passed.
- `mypy apps packages tests`: passed with no issues in 93 source files.
- Full check-suite run: 28 passed, 0 failed at `reports/check_runs/20260511T105213Z/`.
- Promoted baseline: `reports/check_runs/20260511T_hpd_dca_baseline/`.
- Admin Coverage confirmed `nm_hpd=78`, `nm_dca=6`, and `total_pois=743`.
- Score drift was expected and beneficial: Palace of the Governors and New Mexico History Museum
  gained institutional corroboration in history/plaza cases without breaking expected anchors.
