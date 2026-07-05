"""Build and verify the curated Detour v2 delivery.

This is the packaged home of the triaged delivery build formerly hardcoded in
``scripts/build_detour_v2_delivery.py``. The behavior-bearing pieces are:

- the human-triaged dispositions (collapses, exclusions, review candidates, and
  data-quality flags) now live in ``data/detour_v2_dispositions.json``;
- the build applies those dispositions via the tested ``merge_cluster`` logic,
  then re-clusters the final CSV exactly as the Detour acceptance gate would
  (shared significant name token within 35 m) so every surviving multi-row
  cluster is dispositioned;
- the manifest is stamped with ``schema_version: 2`` and input-artifact
  provenance (the committed delivery predates this and remains legacy
  ``schema_version: 1``; see docs/INTEGRATION_CONTRACT.md).

The verify half is a faithful replica of the Detour-side ``qc_pois.py`` gate.
We cannot run their gate (it lives Detour-side); the real PASS happens on their
receipt. Do not treat a producer-side PASS as promotion approval.
"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from poi_curator_editorial.export_schema import (
    AUDIT_COLUMNS,
    BBOX,
    DETOUR_REQUIRED_COLUMNS,
    MERGE_REASONS,
    ExportSchemaError,
    validate_export_rows,
    validate_manifest_payload,
)
from poi_curator_editorial.feature_canonicalization import (
    Cluster,
    haversine_m,
    merge_cluster,
    significant_tokens,
)

MANIFEST_SCHEMA_VERSION = 2
MANIFEST_CONTRACT = "detour-export"

DEFAULT_V1_CSV = Path("reports/query_capable_pois_merged_v1.csv")
DEFAULT_DISPOSITIONS = Path("data/detour_v2_dispositions.json")
DEFAULT_OUT_CSV = Path("query_capable_pois_merged_v2.csv")
DEFAULT_OUT_MANIFEST = Path("query_capable_pois_merged_v2_merge_manifest.json")

# The allowlist must be derived at the SAME radius the gate fails on (<=35 m),
# so left_colocated member sets match the gate's residual clusters exactly.
GATE_RADIUS_M = 35.0

COLLAPSE_REASONS = MERGE_REASONS


class DispositionError(ValueError):
    """A disposition entry is malformed or references a missing dedupe_key."""


@dataclass(frozen=True)
class Dispositions:
    """Human-triaged delivery decisions loaded from the dispositions JSON."""

    excluded_rows: list[dict[str, str]] = field(default_factory=list)
    collapses: list[dict[str, Any]] = field(default_factory=list)
    review_candidate_sets: list[frozenset[str]] = field(default_factory=list)
    data_quality_flags: list[dict[str, str]] = field(default_factory=list)


def load_dispositions(path: Path) -> Dispositions:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DispositionError(f"dispositions file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DispositionError(f"dispositions file is not valid JSON: {path}: {exc}") from exc

    excluded_rows = []
    for entry in payload.get("excluded_rows", []):
        if not entry.get("dedupe_key") or not entry.get("reason"):
            raise DispositionError(f"excluded_rows entry needs dedupe_key and reason: {entry}")
        excluded_rows.append({"dedupe_key": entry["dedupe_key"], "reason": entry["reason"]})

    collapses = []
    for entry in payload.get("collapses", []):
        reason = entry.get("reason")
        members = entry.get("members") or []
        if reason not in COLLAPSE_REASONS:
            raise DispositionError(
                f"collapse reason {reason!r} not in {sorted(COLLAPSE_REASONS)}: {entry}"
            )
        if len(members) < 2:
            raise DispositionError(f"collapse needs at least 2 members: {entry}")
        collapses.append({"reason": reason, "members": list(members)})

    review_sets = [
        frozenset(members) for members in payload.get("review_candidate_sets", [])
    ]

    flags = []
    for entry in payload.get("data_quality_flags", []):
        if not entry.get("dedupe_key") or not entry.get("issue"):
            raise DispositionError(f"data_quality_flags entry needs dedupe_key and issue: {entry}")
        flags.append({"dedupe_key": entry["dedupe_key"], "issue": entry["issue"]})

    return Dispositions(
        excluded_rows=excluded_rows,
        collapses=collapses,
        review_candidate_sets=review_sets,
        data_quality_flags=flags,
    )


def check_disposition_keys(dispositions: Dispositions, by_key: dict[str, dict[str, str]]) -> None:
    """Fail loudly when any disposition references a dedupe_key absent from the input."""
    missing: list[str] = []
    for entry in dispositions.excluded_rows:
        if entry["dedupe_key"] not in by_key:
            missing.append(f"excluded_rows: {entry['dedupe_key']}")
    for collapse in dispositions.collapses:
        for key in collapse["members"]:
            if key not in by_key:
                missing.append(f"collapses: {key}")
    for members in dispositions.review_candidate_sets:
        for key in members:
            if key not in by_key:
                missing.append(f"review_candidate_sets: {key}")
    for flag in dispositions.data_quality_flags:
        if flag["dedupe_key"] not in by_key:
            missing.append(f"data_quality_flags: {flag['dedupe_key']}")
    if missing:
        raise DispositionError(
            "dispositions reference dedupe_keys missing from the input export "
            "(stale triage after re-ingestion?): " + "; ".join(missing)
        )


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
        fields = list(reader.fieldnames or [])
    return rows, fields


def cluster_components(rows: list[dict[str, str]]) -> list[list[str]]:
    """Gate-replica: connected components of rows sharing a significant name
    token AND within GATE_RADIUS_M."""
    by_key = {row["dedupe_key"]: row for row in rows}
    parent = {key: key for key in by_key}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        parent[find(left)] = find(right)

    tokens = {key: significant_tokens(row["name"]) for key, row in by_key.items()}
    for row_a, row_b in itertools.combinations(rows, 2):
        key_a, key_b = row_a["dedupe_key"], row_b["dedupe_key"]
        if not (tokens[key_a] & tokens[key_b]):
            continue
        distance = haversine_m(
            float(row_a["lon"]), float(row_a["lat"]), float(row_b["lon"]), float(row_b["lat"])
        )
        if distance <= GATE_RADIUS_M:
            union(key_a, key_b)

    components: dict[str, list[str]] = defaultdict(list)
    for key in by_key:
        components[find(key)].append(key)
    return [sorted(members) for members in components.values() if len(members) > 1]


def pair_distance(by_key: dict[str, dict[str, str]], keys: list[str]) -> float:
    points = [(float(by_key[key]["lon"]), float(by_key[key]["lat"])) for key in keys]
    return max(
        haversine_m(p[0], p[1], q[0], q[1]) for p, q in itertools.combinations(points, 2)
    )


def build_delivery(
    *,
    v1_csv: Path = DEFAULT_V1_CSV,
    dispositions_path: Path = DEFAULT_DISPOSITIONS,
    out_csv: Path = DEFAULT_OUT_CSV,
    out_manifest: Path = DEFAULT_OUT_MANIFEST,
) -> dict[str, Any]:
    """Deterministically build the Detour v2 delivery CSV + manifest."""
    dispositions = load_dispositions(dispositions_path)
    rows, fields = load_rows(v1_csv)
    rows_before = len(rows)
    by_key = {row["dedupe_key"]: row for row in rows}
    check_disposition_keys(dispositions, by_key)
    out_fields = fields + [column for column in AUDIT_COLUMNS if column not in fields]

    # 1) Excluded rows (documented, never coordinate-nudged into compliance).
    excluded_keys: set[str] = set()
    excluded_entries: list[dict[str, Any]] = []
    for entry in dispositions.excluded_rows:
        row = by_key[entry["dedupe_key"]]
        excluded_keys.add(entry["dedupe_key"])
        excluded_entries.append(
            {
                "dedupe_key": entry["dedupe_key"],
                "poi_id": row["poi_id"],
                "name": row["name"],
                "lon": float(row["lon"]),
                "lat": float(row["lat"]),
                "reason": entry["reason"],
            }
        )

    # 2) Apply explicit collapses via the tested merge_cluster logic.
    collapsed_keys: set[str] = set()
    survivors: dict[str, dict[str, str]] = {}
    collapsed_entries: list[dict[str, Any]] = []
    for collapse in dispositions.collapses:
        group = [by_key[key] for key in collapse["members"]]
        cluster = Cluster(rows=group, reasons={collapse["reason"]})
        survivor, merge_entry = merge_cluster(cluster)
        survivors[survivor["dedupe_key"]] = survivor
        collapsed_keys.update(collapse["members"])
        collapsed_entries.append(
            {
                "disposition": "collapsed",
                "reason": collapse["reason"],
                "survivor_poi_id": survivor["poi_id"],
                "survivor_dedupe_key": survivor["dedupe_key"],
                "chosen_display_name": merge_entry["chosen_display_name"],
                "alias_names": merge_entry["alias_names"],
                "dropped": [
                    {
                        "dedupe_key": dropped["dedupe_key"],
                        "poi_id": dropped["poi_id"],
                        "name": dropped["name"],
                        "lon": dropped["lon"],
                        "lat": dropped["lat"],
                    }
                    for dropped in merge_entry["dropped"]
                ],
            }
        )

    # 3) Assemble final rows: survivors + passthrough (minus excluded + dropped).
    final_rows: list[dict[str, str]] = []
    for row in rows:
        key = row["dedupe_key"]
        if key in excluded_keys:
            continue
        if key in survivors:
            final_rows.append(survivors[key])
        elif key in collapsed_keys:
            continue  # dropped member
        else:
            passthrough = dict(row)
            passthrough.setdefault("merged_from", "")
            passthrough.setdefault("merge_reason", "")
            final_rows.append(passthrough)

    final_by_key = {row["dedupe_key"]: row for row in final_rows}

    # 4) Re-cluster the FINAL csv (gate replica) -> disposition every residual cluster.
    components = cluster_components(final_rows)
    review_sets = set(dispositions.review_candidate_sets)
    left_colocated_entries: list[dict[str, Any]] = []
    review_entries: list[dict[str, Any]] = []
    for component in components:
        component_set = frozenset(component)
        if component_set in review_sets:
            review_entries.append(
                {
                    "disposition": "review_candidate",
                    "members": component,
                    "distance_m": round(pair_distance(final_by_key, component), 2),
                }
            )
        else:
            left_colocated_entries.append(
                {
                    "disposition": "left_colocated",
                    "members": component,
                }
            )

    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "contract": MANIFEST_CONTRACT,
        "inputs": {
            "v1_csv": {
                "path": str(v1_csv),
                "sha256": sha256_of(v1_csv),
                "rows": rows_before,
            },
            "dispositions": {
                "path": str(dispositions_path),
                "sha256": sha256_of(dispositions_path),
            },
        },
        "summary": {
            "rows_before": rows_before,
            "rows_after": len(final_rows),
            "clusters_collapsed": len(collapsed_entries),
            "clusters_left_colocated": len(left_colocated_entries),
            "review_candidates": len(review_entries),
        },
        "clusters": collapsed_entries + left_colocated_entries + review_entries,
        "excluded_rows": excluded_entries,
        "data_quality_flags": dispositions.data_quality_flags,
    }

    # 5) Validate against the versioned export contract before emitting anything.
    schema_errors = validate_export_rows(out_fields, final_rows)
    schema_errors += validate_manifest_payload(manifest)
    if schema_errors:
        raise ExportSchemaError(
            "refusing to write delivery: " + "; ".join(schema_errors)
        )

    # 6) Write outputs (deterministic; no timestamps).
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(final_rows)
    out_manifest.parent.mkdir(parents=True, exist_ok=True)
    out_manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest


def verify_delivery(
    csv_path: Path = DEFAULT_OUT_CSV,
    manifest_path: Path = DEFAULT_OUT_MANIFEST,
) -> list[str]:
    """Replica of the Detour acceptance gate plus manifest accounting checks.

    Returns a list of failure strings; empty means the producer-side replica
    passed. Accepts both the legacy committed manifest (schema_version 1) and
    the CLI-stamped manifest (schema_version 2).
    """
    failures: list[str] = []
    rows, header = load_rows(csv_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_key = {row["dedupe_key"]: row for row in rows}

    # 0) Versioned schema validation: row contract + manifest contract (v1 or v2).
    failures += validate_export_rows(header, rows)
    failures += validate_manifest_payload(manifest)

    # 1) Schema: 18 required columns present + audit columns. Redundant with the
    # header check above, but kept because it mirrors Detour's gate wording.
    missing = [column for column in DETOUR_REQUIRED_COLUMNS if column not in header]
    if missing:
        failures.append(f"missing required columns: {missing}")
    for column in AUDIT_COLUMNS:
        if column not in header:
            failures.append(f"missing audit column: {column}")

    # 2) Unique dedupe_key.
    keys = [row["dedupe_key"] for row in rows]
    duplicates = {key for key in keys if keys.count(key) > 1}
    if duplicates:
        failures.append(f"duplicate dedupe_key(s): {sorted(duplicates)[:5]}")

    # 3) Coords numeric, [lon, lat], in bbox.
    for row in rows:
        try:
            lon, lat = float(row["lon"]), float(row["lat"])
        except ValueError:
            failures.append(f"non-numeric coords: {row['dedupe_key']}")
            continue
        in_bbox = (
            BBOX["lon_min"] <= lon <= BBOX["lon_max"]
            and BBOX["lat_min"] <= lat <= BBOX["lat_max"]
        )
        if not in_bbox:
            failures.append(f"out of bbox: {row['dedupe_key']} ({lon},{lat})")

    # 4) Manifest summary.rows_after == CSV row count.
    rows_after = (manifest.get("summary") or {}).get("rows_after")
    if rows_after != len(rows):
        failures.append(f"summary.rows_after={rows_after} != csv rows={len(rows)}")

    # 5) collapsed: survivor present in CSV; every dropped key absent.
    allowlisted: set[frozenset[str]] = set()
    for cluster in manifest.get("clusters") or []:
        disposition = cluster.get("disposition")
        if disposition == "collapsed":
            survivor_key = cluster.get("survivor_dedupe_key")
            if survivor_key not in by_key:
                failures.append(f"collapsed survivor missing from CSV: {survivor_key}")
            for dropped in cluster.get("dropped") or []:
                if dropped.get("dedupe_key") in by_key:
                    failures.append(f"dropped key still in CSV: {dropped.get('dedupe_key')}")
        elif disposition in ("left_colocated", "review_candidate"):
            members = cluster.get("members") or []
            allowlisted.add(frozenset(members))
            for key in members:
                if disposition == "left_colocated" and key not in by_key:
                    failures.append(f"left_colocated member missing from CSV: {key}")

    # 6) THE GATE CORE: no un-dispositioned cluster <= GATE_RADIUS_M sharing a token.
    residual = [
        members
        for members in cluster_components(rows)
        if frozenset(members) not in allowlisted
    ]
    if residual:
        failures.append(f"RESIDUAL un-dispositioned <=35m clusters: {residual}")

    return failures
