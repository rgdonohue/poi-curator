# Same-Feature Canonicalization for the Merged POI Export

**Date:** 2026-06-01
**Status:** Approved design, pre-implementation
**Owner:** curator project (POI Curator)
**Consumer:** Detour frontend map (renders one pin per CSV row)

## Problem

`reports/query_capable_pois_merged_v1.csv` contains multiple rows for single
physical features, which Detour renders as clusters of near-identical pins. The
clearest case is the Roque Tudesque House: an OSM relation
(`osm:relation/13422888`), its two member ways (`osm:way/461729208`,
`osm:way/461729209`), and a standalone node (`osm:node/6479254097`), all within
~30 m, surviving as four rows.

### Root cause

The export step (`scripts/export_query_capable_pois_merged_v1.py:135-164`) already
collapses rows by `dedupe_key`, keeping the highest `quality_score`. But
`dedupe_key` is the raw OSM entity id (`osm:relation/…`, `osm:way/…`,
`osm:node/…`), so one feature expressed as relation + member ways + node has four
distinct keys and survives as four rows. Upstream, the shared matcher
(`packages/ingestion/poi_curator_ingestion/matching.py`) uses a 100 m window +
0.85 name similarity and has **no OSM relation↔member-way lineage rule**, so it
never links them into one canonical either. The directional suffixes
("Tudesque House" vs "Roque Tudesque House East/West") also push name similarity
below 0.85. The duplicates therefore exist as separate canonical POIs in the DB,
and the export faithfully emits all of them.

### The over-merge trap (verified against the data)

Two of the three clusters the original handoff cited as duplicates are **not**
duplicates:

| Cluster | Apart | Distinguisher | Verdict |
|---|---|---|---|
| Roque Tudesque (rel + 2 ways + node) | ~30 m | same place | **duplicate — collapse** |
| Santa Fe River Park East/West | ~570 m | two ends of a linear park | **distinct — keep** |
| Pueblo Alegre North/South Park | ~250 m | *Vuelta San Marcos* vs *Camino de Chelly* | **distinct — keep** |

A naive "shared name base after stripping East/West/North/South + proximity"
rule would wrongly merge the latter two. The reliable primary signal is OSM
relation↔member lineage; proximity+name is used only as a tight secondary
absorber for non-member rows.

## Decisions (locked during brainstorming)

1. **Fix location:** export-time canonicalization (not an ingestion/matcher fix).
   No DB writes, no migration, no re-ingestion. A matcher lineage rule is a
   possible later follow-up, explicitly out of scope here.
2. **Lineage source:** carry relation→member lineage as data, extracted once from
   `poi_source_raw` and committed as an artifact; the merge stays pure-CSV.
3. **Merge boundary:** authoritative OSM lineage is primary; a tight (35 m +
   shared significant name token) absorber pulls in non-member nodes/ways. No
   cluster is ever formed without a relation in it.

## Architecture & data flow

```
poi_source_raw (DB) ──[1] extract_osm_relation_lineage.py──▶ reports/osm_relation_lineage.csv
                                                              (relation→member map, provenance-stamped)
                                                                    │
seed_described_v1.csv + seed_context_v1.csv ──[2] lineage join──▶ parent_relation_id, osm_member_refs
                                                                    │
                                          [3] feature_canonicalization (pure module, no I/O)
                                                                    │
                            ┌───────────────────────────┬──────────┴───────────┐
                            ▼                           ▼                        ▼
              query_capable_pois_merged_v2.csv   *_merge_manifest.json    stdout counts report
              (v1 schema + merged_from,           (schema_version, summary,
               merge_reason appended)              clusters, review_candidates)
```

### [1] Lineage extractor — `scripts/extract_osm_relation_lineage.py` (new)

- Opens a DB session, reads current `poi_source_raw` where `source_name == osm`
  and `is_current`, parses `raw_payload_json`. For `type == "relation"` records,
  emits each relation id and its `members[].ref`/`.type` (member way/node ids).
- Output: `reports/osm_relation_lineage.csv`, committed as a carried artifact.
- **Provenance stamp:** header comment / sidecar fields recording extraction date
  and `poi_source_raw` current-row count (ingest snapshot), so staleness is
  detectable.
- **Idempotent:** deterministic ordering; re-runs cleanly when the DB is up.
- Because there is no committed producer for the base seed CSVs, we run this once
  now and commit the artifact rather than blocking on a live DB.

### [2] Lineage join

The export load attaches two columns keyed by `dedupe_key`/`osm_id`:

- `parent_relation_id` — for a member way/node, the `osm:relation/<id>` it belongs
  to (empty otherwise).
- `osm_member_refs` — for a relation row, its pipe-listed member refs.

These are first-class inspectable columns. **Staleness guard:** the merge warns
loudly if the lineage artifact looks stale versus the seed — row-count mismatch
against its stamped snapshot, or an older mtime than the seed CSV.

### [3] Canonicalization module — `packages/editorial/poi_curator_editorial/feature_canonicalization.py` (new)

Pure functions, no I/O. The export script calls it. Reuses
`matching.normalize_name_tokens` and the haversine distance helper
(`matching.approx_distance_m` style) rather than reinventing them.

## The merge algorithm

### Step 1 — Build clusters (union-find)

- **Lineage grouping (authoritative):** group by shared `parent_relation_id`
  itself — **not** by the relation row's presence in the export. If a relation
  row is filtered out (unusable name, dropped category) but its member ways
  survive, those members must still cluster together via their shared
  `parent_relation_id`. (Folded-in correctness item #1 — prevents East/West
  re-leaking as two dots when the relation row is gone.)
- **Tight absorber (secondary):** a non-member row joins an existing lineage
  cluster iff its centroid is within **35 m of the nearest cluster member point**
  (not the relation centroid) **and** it shares ≥1 *significant* name token with
  the cluster.
- **Hard guard:** no cluster is ever created without a lineage (`parent_relation_id`)
  group as its seed. Two lone ways/nodes never merge on name+proximity alone.
  This is what provably protects River Park E/W (570 m, no relation) and Pueblo
  Alegre N/S (250 m, no relation).

**Significant token rule (correctness item #3):** generic/structural tokens are
excluded from the shared-token test — `house`, `park`, `building`, `gallery`,
`studio`, `annex`, plus the existing `COMMON_AFFIXES` and directional words
(`east/west/north/south`). Two unrelated "… House" rows must not bridge on
"house" alone. Lineage + proximity already guard this; the token rule makes it
explicit.

### Step 1b — Near-miss review band (correctness/transparency, from review (a))

Rows at **35–75 m** from a lineage cluster that share a significant name token,
but are **not merged**, are recorded in the manifest as `review_candidates`. A
too-tight auto-merge radius can then never *silently* leave a duplicate dot — it
surfaces for a human instead. We do **not** widen the auto-merge radius.

### Step 2 — Pick the survivor (canonical row)

Per cluster: highest `quality_score`; tie-break `relation > way > node`, then
lowest `poi_id`. For Tudesque this selects the relation at 80.0. If no relation
row survived filtering, the survivor is the highest-quality surviving member.

### Step 2b — Choose display name separately from the canonical row (item #2)

The survivor supplies geometry, score, and `poi_id`, but the **display name** is
chosen independently:

- Prefer the cluster member's name backed by the strongest identity evidence
  (`state_register` / `nrhp` / historic basis), else the most specific name.
- For Tudesque this prefers "Roque Tudesque House" (state-register-backed) over
  the relation's bare "Tudesque House".
- All other cluster names become aliases.
- The manifest records the chosen display name and the losing names.

### Step 3 — Merge provenance into the survivor

No coordinate change, no score recompute.

- `evidence_sources`, `active_themes`, `preferred_aliases`: pipe-union
  (de-duplicated, stable order).
- Dropped rows' names + the relation's own name → aliases on the survivor
  (preserves "Tudesque House", "…East", "…West", etc.).
- `wikipedia_title`: fill only if the survivor's is empty, from the
  highest-quality dropped row that has one.
- All other survivor fields untouched.

### Step 4 — Audit columns (appended to every surviving row)

- `merged_from`: pipe-list of collapsed `dedupe_key`s (empty for singleton rows).
- `merge_reason`: `osm_relation_members`, `node_proximity`, or both joined;
  empty for untouched rows.

### Idempotency (correctness item #4)

Re-running the merge on an already-merged v2 must be a true no-op:

- The algorithm ignores the `merged_from` / `merge_reason` columns on input.
- Alias lists do not re-append already-present names; pipe-unions are
  set-stable.
- The idempotency test asserts alias and provenance lists **do not grow** on a
  second pass and that row count is unchanged.

## Outputs

### `reports/query_capable_pois_merged_v2.csv`

Identical v1 column order, with `merged_from` and `merge_reason` appended. No
existing column renamed or dropped. `poi_id` stable for surviving rows.
Coordinates unchanged and unrounded; `[lon, lat]` order preserved.

### `reports/query_capable_pois_merged_v2_merge_manifest.json`

```jsonc
{
  "schema_version": 1,
  "summary": {
    "rows_before": 0,
    "rows_after": 0,
    "clusters_collapsed": 0,
    "clusters_left_colocated": 0,   // multi-row spatial clusters intentionally kept
    "review_candidates": 0          // 35–75m near-misses for human review
  },
  "clusters": [
    {
      "survivor_poi_id": "...",
      "survivor_dedupe_key": "osm:relation/13422888",
      "chosen_display_name": "Roque Tudesque House",
      "alias_names": ["Tudesque House", "Roque Tudesque House East", "..."],
      "dropped": [
        {"poi_id": "...", "dedupe_key": "osm:way/461729208", "name": "...",
         "lon": 0, "lat": 0, "distance_m": 0.0}
      ],
      "merge_reason": "osm_relation_members+node_proximity"
    }
  ],
  "review_candidates": [
    {"cluster_survivor_poi_id": "...", "candidate_poi_id": "...",
     "candidate_name": "...", "distance_m": 0.0, "shared_tokens": ["..."]}
  ],
  "secondary_flags": []   // unreviewed descriptions, historic-vs-current names; flagged not fixed
}
```

Top-level `schema_version` and a `summary` block let a consumer (Detour's
`qc_pois.py`) assert in O(1) and diff cleanly across runs.

### stdout counts report

rows before, rows after, clusters collapsed, multi-row spatial clusters left as
co-located, review_candidates count.

## Testing (TDD — tests written first)

`tests/unit/test_feature_canonicalization.py`:

- **Tudesque fixture** (rel + 2 ways + node) → 1 survivor; canonical row is the
  relation; `chosen_display_name == "Roque Tudesque House"`; `merged_from` has 3
  keys; dropped names present as aliases; `merge_reason ==
  osm_relation_members+node_proximity`.
- **River Park E/W** and **Pueblo Alegre N/S** fixtures → unchanged, no merge,
  zero clusters collapsed for them.
- **Orphaned-relation fixture** (relation row filtered out, member ways survive) →
  members still cluster via `parent_relation_id`; survivor is highest-quality
  member; East/West do not re-leak.
- **Display-name selection** → state-register-backed name beats the relation's
  bare name.
- **Significant-token guard** → two unrelated "… House" rows within 35 m but with
  no other shared token and no shared relation do **not** merge.
- **Near-miss band** → a 50 m same-token non-member appears in `review_candidates`,
  not merged.
- **Survivor tie-break** → equal scores ⇒ relation wins; equal type ⇒ lowest
  poi_id.
- **Provenance union** correctness.
- **Idempotency** → second pass on v2 leaves row count and alias/provenance lists
  unchanged (lists do not grow).
- **End-to-end** → run the export on the committed seed CSV; assert v1→v2
  row-count delta equals the manifest's `clusters_collapsed` accounting.

## Scope guards (YAGNI)

- No DB writes, migration, re-ingestion, or matcher changes.
- Secondary handoff items — `description_review_status=unreviewed` templated
  drafts, and historic-vs-current names (e.g. "Roque Tudesque House" is now the
  "Inn of the Five Graces") — are **flagged in the manifest** (`secondary_flags`),
  not fixed here. They do not block the dedup fix.

## Open item

The lineage extractor needs a live DB to (re)generate `osm_relation_lineage.csv`.
Resolution: run it once now and commit the stamped artifact; the merge stays
pure-CSV and re-runnable, with a loud staleness warning if the artifact and seed
diverge.
