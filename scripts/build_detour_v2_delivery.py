#!/usr/bin/env python3
"""Build the curated Detour v2 delivery: triaged same-feature collapse + disposition manifest.

Unlike the auto-pipeline export, this applies an explicit, human-triaged set of
collapses (the 9 confirmed same-feature clusters), drops the one out-of-bbox row,
and derives the left_colocated allowlist by RE-CLUSTERING the final CSV exactly as
the QA gate would (shared significant name token + <=75 m). That guarantees every
surviving multi-row cluster is dispositioned.

Outputs (repo root, matching the gate command):
- query_capable_pois_merged_v2.csv              (v1's 29 cols + merged_from, merge_reason)
- query_capable_pois_merged_v2_merge_manifest.json
"""

from __future__ import annotations

import csv
import itertools
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from poi_curator_editorial.feature_canonicalization import (
    Cluster,
    haversine_m,
    merge_cluster,
    significant_tokens,
)

V1_CSV = Path("reports/query_capable_pois_merged_v1.csv")
OUT_CSV = Path("query_capable_pois_merged_v2.csv")
OUT_MANIFEST = Path("query_capable_pois_merged_v2_merge_manifest.json")

# Santa Fe bounding box (gate contract).
BBOX = {"lon_min": -106.10, "lon_max": -105.80, "lat_min": 35.55, "lat_max": 35.78}

# Allowlist must be derived at the SAME radius the gate fails on (<=35 m), so the
# left_colocated frozensets match the gate's residual clusters exactly.
CLUSTER_RADIUS_M = 35.0

AUDIT_COLUMNS = ["merged_from", "merge_reason"]

# --- Out-of-bbox row: a ~hundreds-of-mile National Historic Trail whose anchor
# sits 222 m north of the box. Not a stop-shaped pin; coordinate cannot be honestly
# corrected. Dropped from the Detour export and documented in the manifest.
EXCLUDED_BBOX_KEY = "osm:relation/18934145"

# --- Explicit, human-triaged collapses. Each entry: survivor is chosen by
# merge_cluster (highest quality_score; relation>way>node; lowest poi_id). The
# display name is chosen by strongest identity evidence inside merge_cluster.
# reason is the contract vocabulary: "osm_relation_members" | "name+proximity".
COLLAPSES: list[tuple[str, list[str]]] = [
    # Roque Tudesque House: relation + its two member ways + member node (lineage).
    ("osm_relation_members", [
        "osm:relation/13422888", "osm:way/461729209",
        "osm:way/461729208", "osm:node/6479254097",
    ]),
    # Guadalupe church: Santuario + Catholic Church + "Our Lady" (same church,
    # 3 OSM representations within ~59 m). NOT the Guadalupe Street Bridge (91 m, distinct).
    ("name+proximity", [
        "osm:way/473190151", "osm:way/725191463", "osm:way/1212812771",
    ]),
    # Fire / Firefighters Museum.
    ("name+proximity", ["osm:way/475539174", "osm:node/6615398270"]),
    # United Church.
    ("name+proximity", ["osm:way/478163588", "osm:way/946169067"]),
    # Vietnam memorial.
    ("name+proximity", ["osm:way/686368793", "osm:node/8973437607"]),
    # Cross of the Martyrs (the downtown cross; not Old Cross / Overlook, which are >250 m away).
    ("name+proximity", [
        "osm:way/682544392", "osm:node/6392062194", "osm:node/6392062211",
    ]),
    # Dish pair A.
    ("name+proximity", ["osm:node/6626953354", "osm:node/6626953353"]),
    # Dish pair B.
    ("name+proximity", ["osm:node/7531555535", "osm:node/7531555578"]),
    # Dish pair C.
    ("name+proximity", ["osm:node/9140510013", "osm:node/6696363459"]),
    # Atalaya Mountain: same summit, two DB nodes ~39 m apart (gate blind-spot,
    # >35 m). Same physical feature -> collapse by identity (don't await the gate).
    ("name+proximity", ["osm:node/357610899", "osm:node/6946550897"]),
]

# Final-CSV components flagged for human review rather than allowlisted as distinct:
# identical/subset-name near-misses in the 35-75 m band that are plausibly the same
# feature but we are not collapsing without confirmation. (None currently: Atalaya
# was confirmed same-feature and moved to COLLAPSES.)
REVIEW_CANDIDATE_SETS: list[frozenset[str]] = []

# Data-quality flags surfaced for the consumer (not blocking; informational).
DATA_QUALITY_FLAGS: list[dict[str, str]] = [
    {"dedupe_key": "osm:way/santa-fe-plaza",
     "issue": "hand-authored non-OSM dedupe_key; record_origin=fixture_overlay; "
     "overlaps real 'The Santa Fe Plaza' (osm:way/141165187) ~81 m away"},
    {"dedupe_key": "osm:node/cross-martyrs",
     "issue": "hand-authored non-OSM dedupe_key; record_origin=fixture_overlay; "
     "'Cross of the Martyrs Overlook' ~290 m from the downtown Cross cluster"},
    {"dedupe_key": "osm:way/canyon-road",
     "issue": "hand-authored non-OSM dedupe_key; record_origin=fixture_overlay showcase point"},
    {"dedupe_key": "osm:way/rail-yard",
     "issue": "hand-authored non-OSM dedupe_key; record_origin=fixture_overlay showcase point"},
    {"dedupe_key": "osm:node/7777929438",
     "issue": "4th distinct 'Dish' location ~6 km from the others; category_fallback; "
     "likely stray/mis-tagged data, but isolated (not a redundant pin)"},
]


def load_v1() -> tuple[list[dict[str, str]], list[str]]:
    with V1_CSV.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = [dict(r) for r in reader]
        fields = list(reader.fieldnames or [])
    return rows, fields


def in_bbox(row: dict[str, str]) -> bool:
    lon, lat = float(row["lon"]), float(row["lat"])
    return (
        BBOX["lon_min"] <= lon <= BBOX["lon_max"]
        and BBOX["lat_min"] <= lat <= BBOX["lat_max"]
    )


def cluster_components(rows: list[dict[str, str]]) -> list[list[str]]:
    """Gate-replica: connected components of rows sharing a significant name token
    AND within CLUSTER_RADIUS_M."""
    by_key = {r["dedupe_key"]: r for r in rows}
    parent = {k: k for k in by_key}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    tokens = {k: significant_tokens(r["name"]) for k, r in by_key.items()}
    for a, b in itertools.combinations(rows, 2):
        ka, kb = a["dedupe_key"], b["dedupe_key"]
        if not (tokens[ka] & tokens[kb]):
            continue
        if haversine_m(float(a["lon"]), float(a["lat"]), float(b["lon"]), float(b["lat"])) <= CLUSTER_RADIUS_M:
            union(ka, kb)

    comp: dict[str, list[str]] = defaultdict(list)
    for k in by_key:
        comp[find(k)].append(k)
    return [sorted(v) for v in comp.values() if len(v) > 1]


def pair_distance(by_key: dict[str, dict[str, str]], keys: list[str]) -> float:
    pts = [(float(by_key[k]["lon"]), float(by_key[k]["lat"])) for k in keys]
    return max(
        haversine_m(p[0], p[1], q[0], q[1]) for p, q in itertools.combinations(pts, 2)
    )


def build() -> dict[str, Any]:
    rows, fields = load_v1()
    rows_before = len(rows)
    by_key = {r["dedupe_key"]: r for r in rows}
    out_fields = fields + AUDIT_COLUMNS

    # 1) Excluded out-of-bbox row.
    excluded = by_key.get(EXCLUDED_BBOX_KEY)
    excluded_entry = None
    if excluded is not None:
        excluded_entry = {
            "dedupe_key": EXCLUDED_BBOX_KEY,
            "poi_id": excluded["poi_id"],
            "name": excluded["name"],
            "lon": float(excluded["lon"]),
            "lat": float(excluded["lat"]),
            "reason": "out_of_bbox: lat 35.78200 is north of bbox max 35.78; linear "
            "National Historic Trail, not a stop-shaped pin; dropped",
        }

    collapsed_keys: set[str] = set()
    survivors: dict[str, dict[str, str]] = {}
    collapsed_entries: list[dict[str, Any]] = []

    # 2) Apply explicit collapses via the tested merge_cluster logic.
    for reason, keys in COLLAPSES:
        group = [by_key[k] for k in keys]
        cluster = Cluster(rows=group, reasons={reason})
        survivor, entry = merge_cluster(cluster)
        survivors[survivor["dedupe_key"]] = survivor
        collapsed_keys.update(keys)
        collapsed_entries.append({
            "disposition": "collapsed",
            "reason": reason,
            "survivor_poi_id": survivor["poi_id"],
            "survivor_dedupe_key": survivor["dedupe_key"],
            "chosen_display_name": entry["chosen_display_name"],
            "alias_names": entry["alias_names"],
            "dropped": [
                {"dedupe_key": d["dedupe_key"], "poi_id": d["poi_id"],
                 "name": d["name"], "lon": d["lon"], "lat": d["lat"]}
                for d in entry["dropped"]
            ],
        })

    # 3) Assemble final rows: survivors + passthrough (minus excluded + dropped).
    final_rows: list[dict[str, str]] = []
    for r in rows:
        k = r["dedupe_key"]
        if k == EXCLUDED_BBOX_KEY:
            continue
        if k in survivors:
            final_rows.append(survivors[k])
        elif k in collapsed_keys:
            continue  # dropped member
        else:
            row = dict(r)
            row.setdefault("merged_from", "")
            row.setdefault("merge_reason", "")
            final_rows.append(row)

    final_by_key = {r["dedupe_key"]: r for r in final_rows}

    # 4) Re-cluster the FINAL csv (gate replica) -> disposition every residual cluster.
    components = cluster_components(final_rows)
    review_sets = {frozenset(s) for s in REVIEW_CANDIDATE_SETS}
    left_colocated_entries: list[dict[str, Any]] = []
    review_entries: list[dict[str, Any]] = []
    for comp in components:
        comp_set = frozenset(comp)
        if comp_set in review_sets:
            review_entries.append({
                "disposition": "review_candidate",
                "members": comp,
                "distance_m": round(pair_distance(final_by_key, comp), 2),
            })
        else:
            left_colocated_entries.append({
                "disposition": "left_colocated",
                "members": comp,
            })

    clusters = collapsed_entries + left_colocated_entries + review_entries
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "summary": {
            "rows_before": rows_before,
            "rows_after": len(final_rows),
            "clusters_collapsed": len(collapsed_entries),
            "clusters_left_colocated": len(left_colocated_entries),
            "review_candidates": len(review_entries),
        },
        "clusters": clusters,
        "excluded_rows": [excluded_entry] if excluded_entry else [],
        "data_quality_flags": DATA_QUALITY_FLAGS,
    }

    # 5) Write outputs (deterministic).
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(final_rows)
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    m = build()
    s = m["summary"]
    print(f"wrote {OUT_CSV} and {OUT_MANIFEST}")
    print(
        "rows_before={rows_before} rows_after={rows_after} "
        "clusters_collapsed={clusters_collapsed} "
        "clusters_left_colocated={clusters_left_colocated} "
        "review_candidates={review_candidates}".format(**s)
    )
