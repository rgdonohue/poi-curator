# GNIS Canonical-Creation Policy Refinement

Date: 2026-05-02

## Summary

The GNIS adapter now creates canonical POIs only for stop-shaped feature classes:
Canal, Spring, Summit, Valley, Church, Cemetery, Park, Trail, and School. Civil,
Populated Place, Locale, and Building records are retained as GNIS evidence when
they match an existing canonical POI, but they no longer create new canonicals
automatically.

This policy follows the 20260502 GNIS quality spot-check: broad administrative
geographies include some valuable cultural-landscape anchors, but the mix is too
noisy for automatic canonical creation. Those records should enter editorial
review rather than public scoring by default.

## Corpus Cleanup

One-time cleanup demoted 104 active GNIS-primary canonicals whose feature classes
are outside the revised canonical-creation policy.

| Feature class | Demoted canonicals |
|---|---:|
| Civil | 41 |
| Populated Place | 62 |
| Military | 1 |
| Total | 104 |

Attachment outcome:

| Outcome | Count |
|---|---:|
| Attached GNIS evidence to a nearby non-GNIS canonical within 150m | 6 |
| No nearby canonical; queued for curator review | 98 |

All demoted POIs remain in the database with
`review_status='gnis_demoted_pending_review'` and are inactive for public scoring.
Each demotion was logged in `poi_match_log` with
`match_strategy='gnis_policy_demotion'`.

## Adapter Re-Run

The GNIS adapter was re-run against the source feed after the policy change.

| Metric | Count |
|---|---:|
| Candidate records | 292 |
| Canonicals created | 160 |
| Evidence attachments | 180 |
| Variant evidence attachments | 110 |
| Ambiguous records | 1 |
| Historical records without match | 8 |
| Skipped out of scope | 12,763 |
| Skipped by feature class | 10,784 |

No active GNIS-primary canonicals now exist for Civil, Populated Place, Locale,
Building, or Military. Active GNIS-primary canonicals after the re-run are:

| Feature class | Active canonicals |
|---|---:|
| Valley | 74 |
| Summit | 58 |
| Spring | 28 |
| Canal | 13 |
| Total | 173 |

Evidence idempotence check: no duplicate GNIS evidence rows were found for the
same POI, evidence type, external record ID, and evidence label.

## Updated Source Basis

Active canonical source-basis counts after cleanup and re-run:

| Source basis | Count |
|---|---:|
| osm | 414 |
| gnis | 173 |
| osm+wikidata | 78 |
| nrhp | 36 |
| nrhp+osm+wikidata | 16 |
| nmose_pod | 11 |
| gnis+nrhp | 7 |
| gnis+osm+wikidata | 3 |
| gnis+nrhp+osm+wikidata | 1 |
| gnis+osm | 1 |
| nrhp+osm | 1 |
| none | 1 |

Primary-source counts for active canonicals:

| Primary source | Count |
|---|---:|
| osm_overpass | 514 |
| gnis | 173 |
| nrhp | 43 |
| nmose_pod | 11 |
| test | 1 |

The active GNIS-primary count increased from the pre-refinement 117 to 173
because the refined policy demoted broad classes but also admitted newly eligible
Spring, Summit, and Valley records. The important policy result is that broad
administrative GNIS classes no longer surface automatically.

## Admin Visibility

The admin viewer now exposes a `GNIS demoted` review-state filter for POI List
and Map Browser. The running admin viewer was smoke-tested against the live
database with `review_state='gnis_demoted_pending_review'` and `active_only=false`;
the demoted GNIS review queue returned the expected rows.

Coverage semantics were tightened to report active canonical coverage, so
inactive demoted canonicals are not counted as active source coverage. Manual
smoke after restarting the API showed `total_pois=742`, `by_source.gnis=185`,
and `single_source_gaps.gnis=173`.

## Score Drift

Verification run:

- `pytest`: 177 passed.
- `ruff`: clean.
- `mypy`: clean.
- Full check suite:
  `reports/check_runs/20260502T154929Z/index.md`, 28 passed, 0 failed.

Compared with the promoted GNIS/NMOSE baseline
`reports/check_runs/20260502T_gnis_nmose_baseline/`, saved check-suite top
results and rounded scores were unchanged. No baseline promotion is needed for
this refinement.

## Sanity Check Appendix - 2026-05-11

Canonical count reconciliation:

- Pre-refinement active GNIS-primary canonicals were 117 total: 62 Populated Place,
  41 Civil, 13 Canal, and 1 Military.
- Of those 117, only 13 Canal records were in the refined canonical-eligible class list.
- The original GNIS filter admitted Canal, Civil, Crossing, Military, and Populated Place.
  It excluded Spring, Summit, and Valley, so the rerun's newly created Spring/Summit/Valley
  canonicals are net-new eligible ingestions, not duplicate creation.
- Santa Fe County source-file counts for the newly admitted classes were 29 Spring,
  62 Summit, and 74 Valley records. The active canonical output was 28 Spring, 58 Summit,
  and 74 Valley because Spring 8, Cerro Gordo, Sun Mountain, and Tano Point matched existing
  canonicals, while Atalaya Mountain was logged as ambiguous.
- The 13 pre-existing Canal canonicals matched on rerun and were not duplicated.

Allowed-class silent-loss check:

- The GNIS New Mexico source file used by the adapter has zero Santa Fe County rows for Church,
  Cemetery, Park, Trail, or School. Their absence from the active canonical set is source-data
  absence, not filtering loss.

Demoted queue spot-check:

| Record | Feature class | Promote candidate? | Evidence preserved? | Demotion rationale |
|---|---|---|---|---|
| SHC 1895 | Civil | Low. The label is cryptic and reads like an administrative/civil record rather than a traveler-facing stop. | Yes. GNIS geographic-name evidence, coordinates, feature ID, and feature class are present. | Accurate; Civil is broad and should require curator review. |
| Santa Cruz | Populated Place | Yes, possible. It is a named community with a preserved variant name, but it is still settlement-scale rather than a stop. | Yes. GNIS evidence includes feature ID 928814, coordinates, class, and variant `Kangaera'imbu'u *`. | Accurate; Populated Place should be reviewed before canonical promotion. |
| Rancho Valle | Populated Place | Maybe, low priority. It may be useful as a local place-name lead but has no obvious stop-shape value from GNIS alone. | Yes. GNIS geographic-name evidence and field provenance are present. | Accurate; broad populated-place record. |
| Nambe | Populated Place | Yes, high manual-review candidate because the place name is culturally significant, but GNIS alone is too broad. | Yes. GNIS evidence and provenance retain name, coordinates, feature ID, and class. | Accurate; demotion preserves discoverability without automatic surfacing. |
| Caja del Rio Grant | Civil | Yes, possible. It is a historically meaningful land-grant/geographic context anchor, but needs editorial modeling before display. | Yes. GNIS evidence and provenance retain the Civil class, coordinates, and feature ID. | Accurate; Civil land-grant geography is valuable context but not automatic stop-shaped POI. |

Conclusion: the demoted queue is doing what it should. It preserves useful GNIS leads and
provenance while preventing broad administrative or settlement geographies from entering public
scoring without deliberate curation.
