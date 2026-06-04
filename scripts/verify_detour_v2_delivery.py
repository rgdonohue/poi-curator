#!/usr/bin/env python3
"""Faithful replica of the Detour qc_pois.py acceptance gate + extra spot-checks.

We cannot run their gate (it lives Detour-side), so this reproduces the contract
stated in the request and reports PASS/FAIL. The real PASS happens on their receipt.
"""

from __future__ import annotations

import csv
import itertools
import json
import sys
from pathlib import Path

from poi_curator_editorial.feature_canonicalization import haversine_m, significant_tokens

CSV = Path("query_capable_pois_merged_v2.csv")
MANIFEST = Path("query_capable_pois_merged_v2_merge_manifest.json")

REQUIRED_18 = [
    "poi_id", "dedupe_key", "name", "lon", "lat", "primary_category",
    "display_priority", "quality_score", "walk_affinity_hint", "drive_affinity_hint",
    "wikipedia_title", "short_description", "description_map_v1", "description_card_v1",
    "description_subcategory_v1", "description_confidence_v1", "description_basis_v1", "address",
]
BBOX = {"lon_min": -106.10, "lon_max": -105.80, "lat_min": 35.55, "lat_max": 35.78}
GATE_RADIUS_M = 35.0  # the gate fails on un-dispositioned clusters <= 35 m


def main() -> int:
    failures: list[str] = []
    rows = list(csv.DictReader(CSV.open(newline="", encoding="utf-8")))
    header = list(csv.DictReader(CSV.open(newline="", encoding="utf-8")).fieldnames or [])
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_key = {r["dedupe_key"]: r for r in rows}

    # 1) Schema: 18 required columns present + audit columns.
    missing = [c for c in REQUIRED_18 if c not in header]
    if missing:
        failures.append(f"missing required columns: {missing}")
    for c in ("merged_from", "merge_reason"):
        if c not in header:
            failures.append(f"missing audit column: {c}")

    # 2) Unique dedupe_key.
    keys = [r["dedupe_key"] for r in rows]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        failures.append(f"duplicate dedupe_key(s): {sorted(dupes)[:5]}")

    # 3) Coords numeric, [lon,lat], in bbox.
    for r in rows:
        try:
            lon, lat = float(r["lon"]), float(r["lat"])
        except ValueError:
            failures.append(f"non-numeric coords: {r['dedupe_key']}")
            continue
        if not (BBOX["lon_min"] <= lon <= BBOX["lon_max"] and BBOX["lat_min"] <= lat <= BBOX["lat_max"]):
            failures.append(f"out of bbox: {r['dedupe_key']} ({lon},{lat})")

    # 4) Manifest summary.rows_after == CSV row count.
    if manifest["summary"]["rows_after"] != len(rows):
        failures.append(
            f"summary.rows_after={manifest['summary']['rows_after']} != csv rows={len(rows)}"
        )

    # 5) collapsed: survivor present in CSV; every dropped key absent.
    allowlisted: set[frozenset[str]] = set()
    for c in manifest["clusters"]:
        disp = c["disposition"]
        if disp == "collapsed":
            if c["survivor_dedupe_key"] not in by_key:
                failures.append(f"collapsed survivor missing from CSV: {c['survivor_dedupe_key']}")
            for d in c["dropped"]:
                if d["dedupe_key"] in by_key:
                    failures.append(f"dropped key still in CSV: {d['dedupe_key']}")
        elif disp in ("left_colocated", "review_candidate"):
            allowlisted.add(frozenset(c["members"]))
            for k in c["members"]:
                if disp == "left_colocated" and k not in by_key:
                    failures.append(f"left_colocated member missing from CSV: {k}")

    # 6) THE GATE CORE: no un-dispositioned cluster <= GATE_RADIUS_M sharing a token.
    parent = {r["dedupe_key"]: r["dedupe_key"] for r in rows}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    toks = {r["dedupe_key"]: significant_tokens(r["name"]) for r in rows}
    for a, b in itertools.combinations(rows, 2):
        ka, kb = a["dedupe_key"], b["dedupe_key"]
        if not (toks[ka] & toks[kb]):
            continue
        if haversine_m(float(a["lon"]), float(a["lat"]), float(b["lon"]), float(b["lat"])) <= GATE_RADIUS_M:
            union(ka, kb)
    comps: dict[str, list[str]] = {}
    for r in rows:
        comps.setdefault(find(r["dedupe_key"]), []).append(r["dedupe_key"])
    residual = []
    for members in comps.values():
        if len(members) > 1 and frozenset(members) not in allowlisted:
            residual.append(sorted(members))
    if residual:
        failures.append(f"RESIDUAL un-dispositioned <=35m clusters: {residual}")

    # Report.
    if failures:
        print("FAIL — not safe to promote")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS — safe to promote")
    print(f"  rows={len(rows)} clusters: "
          f"collapsed={manifest['summary']['clusters_collapsed']} "
          f"left_colocated={manifest['summary']['clusters_left_colocated']} "
          f"review={manifest['summary']['review_candidates']}")
    print(f"  residual <=35m clusters: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
