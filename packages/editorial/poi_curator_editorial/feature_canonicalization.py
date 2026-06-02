"""Same-feature canonicalization for the Detour merged POI export.

Pure functions only: no DB access, no file I/O. Collapses OSM
relation+member-way+node duplicates into a single canonical row while
preserving legitimately co-located distinct features.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from poi_curator_ingestion.matching import normalize_name_tokens

# Structural / type tokens that must never be the *only* shared token between
# two rows. Layered on top of matching.COMMON_AFFIXES (the, de, san, fe, ...)
# and the directional words below, which normalize_name_tokens does NOT strip.
STRUCTURAL_TOKENS: frozenset[str] = frozenset(
    {
        "house",
        "park",
        "building",
        "gallery",
        "studio",
        "annex",
        "site",
        "center",
        "centre",
        "complex",
        "compound",
        # Plural residues from normalize_name_tokens (strips trailing "s",
        # does not handle y->ies): gallery/annex/complex.
        "gallerie",
        "annexe",
        "complexe",
    }
)
DIRECTIONAL_TOKENS: frozenset[str] = frozenset(
    {"east", "west", "north", "south", "northeast", "northwest", "southeast", "southwest"}
)
_NON_SIGNIFICANT = STRUCTURAL_TOKENS | DIRECTIONAL_TOKENS

_EARTH_RADIUS_M = 6_371_000.0


def significant_tokens(name: str) -> set[str]:
    """Identity-bearing tokens: normalized tokens minus structural/directional ones."""
    return {token for token in normalize_name_tokens(name) if token not in _NON_SIGNIFICANT}


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in metres between two [lon, lat] points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


Row = dict[str, str]

# Auto-merge a non-member row into a lineage cluster only within this radius.
ABSORB_RADIUS_M = 35.0
# Same-token non-members in this outer band are flagged for review, never merged.
REVIEW_RADIUS_M = 75.0


@dataclass
class Cluster:
    rows: list[Row]
    reasons: set[str] = field(default_factory=set)


@dataclass
class ReviewCandidate:
    cluster_survivor_poi_id: str
    candidate_poi_id: str
    candidate_name: str
    distance_m: float
    shared_tokens: list[str]


@dataclass
class ClusterResult:
    clusters: list[Cluster]
    review_candidates: list[ReviewCandidate]


def _lonlat(row: Row) -> tuple[float, float] | None:
    try:
        return float(row["lon"]), float(row["lat"])
    except (KeyError, ValueError):
        return None


def _quality(row: Row) -> float:
    try:
        return float(row.get("quality_score", "") or 0.0)
    except ValueError:
        return 0.0


def _lineage_key(row: Row, relation_keys: set[str]) -> str | None:
    """Cluster key from OSM relation lineage, independent of relation-row survival."""
    parent = row.get("parent_relation_id", "").strip()
    if parent:
        return parent
    if row["dedupe_key"] in relation_keys:
        return row["dedupe_key"]
    return None


def build_clusters(rows: list[Row]) -> ClusterResult:
    relation_keys = {
        ref
        for row in rows
        for ref in (row.get("parent_relation_id", "").strip(),)
        if ref
    }
    # Also treat any relation row that lists members as a cluster seed.
    for row in rows:
        if row.get("osm_member_refs", "").strip():
            relation_keys.add(row["dedupe_key"])

    lineage: dict[str, Cluster] = {}
    unclustered: list[Row] = []
    for row in rows:
        key = _lineage_key(row, relation_keys)
        if key is None:
            unclustered.append(row)
            continue
        cluster = lineage.setdefault(key, Cluster(rows=[]))
        cluster.rows.append(row)
        cluster.reasons.add("osm_relation_members")

    review_candidates: list[ReviewCandidate] = []
    leftover: list[Row] = []
    for row in unclustered:
        coords = _lonlat(row)
        if coords is None:
            # Unparseable coordinates: cannot compute distance, so this row can
            # neither absorb into nor be absorbed by any cluster. It becomes a
            # singleton and is never flagged for review.
            leftover.append(row)
            continue
        lon, lat = coords
        tokens = significant_tokens(row["name"])
        best_cluster: Cluster | None = None
        best_distance = ABSORB_RADIUS_M
        best_review: tuple[Cluster, float, set[str]] | None = None
        for cluster in lineage.values():
            for member in cluster.rows:
                shared = tokens & significant_tokens(member["name"])
                if not shared:
                    continue
                member_coords = _lonlat(member)
                if member_coords is None:
                    continue
                m_lon, m_lat = member_coords
                distance = haversine_m(lon, lat, m_lon, m_lat)
                if distance <= best_distance:
                    # Ties at equal distance resolve to the later cluster in
                    # iteration order (deterministic given stable input).
                    best_distance = distance
                    best_cluster = cluster
                elif ABSORB_RADIUS_M < distance <= REVIEW_RADIUS_M and (
                    best_review is None or distance < best_review[1]
                ):
                    best_review = (cluster, distance, shared)
        if best_cluster is not None:
            best_cluster.rows.append(row)
            best_cluster.reasons.add("node_proximity")
        elif best_review is not None:
            cluster, distance, shared = best_review
            survivor = select_survivor(cluster.rows)
            review_candidates.append(
                ReviewCandidate(
                    cluster_survivor_poi_id=survivor["poi_id"],
                    candidate_poi_id=row["poi_id"],
                    candidate_name=row["name"],
                    distance_m=round(distance, 2),
                    shared_tokens=sorted(shared),
                )
            )
            leftover.append(row)
        else:
            leftover.append(row)

    clusters = list(lineage.values()) + [Cluster(rows=[row]) for row in leftover]
    return ClusterResult(clusters=clusters, review_candidates=review_candidates)


_TYPE_RANK = {"relation": 0, "way": 1, "node": 2}

# Identity-evidence weights scanned across provenance columns for display-name choice.
# Matching is substring (not exact-token) ON PURPOSE: embedded provenance tokens like
# "nrhp_listed_properties" or "nm_hpd_register_workbook" must still be credited.
# "historic" is a deliberate weak catch-all that STACKS with the specific registers, so a
# state-registered building that is also in a historic_district scores higher. That
# stacking is intended behaviour, not a bug.
_IDENTITY_SIGNALS: tuple[tuple[str, int], ...] = (
    ("state_register", 3),
    ("nrhp", 3),
    ("historic", 1),
)
_PROVENANCE_COLUMNS = ("claim_basis", "source_basis", "evidence_sources", "description_basis_v1")


def _osm_type(row: Row) -> str:
    key = row["dedupe_key"]
    if key.startswith("osm:") and "/" in key:
        return key[len("osm:") :].split("/", 1)[0]
    return "zzz"  # non-OSM sorts last on the type tie-break


def select_survivor(rows: list[Row]) -> Row:
    return min(
        rows,
        key=lambda row: (
            -_quality(row),
            _TYPE_RANK.get(_osm_type(row), 9),
            row["poi_id"],
        ),
    )


def _identity_score(row: Row) -> int:
    haystack = " ".join(row.get(column, "") for column in _PROVENANCE_COLUMNS).casefold()
    return sum(weight for token, weight in _IDENTITY_SIGNALS if token in haystack)


def choose_display_name(rows: list[Row]) -> tuple[str, list[str]]:
    """Return (display_name, aliases). Aliases preserve every other cluster name."""
    chosen_row = min(
        rows,
        key=lambda row: (
            -_identity_score(row),
            -len(significant_tokens(row["name"])),
            -len(row["name"]),
            row["poi_id"],
        ),
    )
    chosen = chosen_row["name"]
    aliases: list[str] = []
    seen = {chosen}
    for row in rows:
        name = row["name"].strip()
        if name and name not in seen:
            seen.add(name)
            aliases.append(name)
    return chosen, aliases


def _union_pipe(values: list[str]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        for item in (part.strip() for part in value.split("|")):
            if item and item not in seen:
                seen.add(item)
                out.append(item)
    return "|".join(out)


def _dropped_entry(row: Row, survivor: Row) -> dict[str, Any]:
    row_coords = _lonlat(row)
    survivor_coords = _lonlat(survivor)
    if row_coords is None or survivor_coords is None:
        distance_m: float | None = None
        lon: float | None = row_coords[0] if row_coords else None
        lat: float | None = row_coords[1] if row_coords else None
    else:
        lon, lat = row_coords
        distance_m = round(haversine_m(lon, lat, survivor_coords[0], survivor_coords[1]), 2)
    return {
        "poi_id": row["poi_id"],
        "dedupe_key": row["dedupe_key"],
        "name": row["name"],
        "lon": lon,
        "lat": lat,
        "distance_m": distance_m,
    }


def merge_cluster(cluster: Cluster) -> tuple[Row, dict[str, Any]]:
    """Collapse a cluster to one row plus a manifest entry. Singletons pass through."""
    survivor = dict(select_survivor(cluster.rows))
    chosen_name, aliases = choose_display_name(cluster.rows)
    dropped = [row for row in cluster.rows if row["poi_id"] != survivor["poi_id"]]

    survivor["name"] = chosen_name
    survivor["preferred_aliases"] = _union_pipe(
        [survivor.get("preferred_aliases", "")] + aliases
    )
    survivor["evidence_sources"] = _union_pipe(
        [row.get("evidence_sources", "") for row in cluster.rows]
    )
    survivor["active_themes"] = _union_pipe(
        [row.get("active_themes", "") for row in cluster.rows]
    )
    if not survivor.get("wikipedia_title", "").strip():
        for row in sorted(dropped, key=lambda r: -_quality(r)):
            title = row.get("wikipedia_title", "").strip()
            if title:
                survivor["wikipedia_title"] = title
                break

    # Audit columns. Ignore any pre-existing merged_from/merge_reason (idempotency).
    survivor["merged_from"] = "|".join(sorted(row["dedupe_key"] for row in dropped))
    survivor["merge_reason"] = "+".join(sorted(cluster.reasons)) if dropped else ""

    entry: dict[str, Any] = {
        "survivor_poi_id": survivor["poi_id"],
        "survivor_dedupe_key": survivor["dedupe_key"],
        "chosen_display_name": chosen_name,
        "alias_names": aliases,
        "dropped": [_dropped_entry(row, survivor) for row in dropped],
        "merge_reason": survivor["merge_reason"],
    }
    return survivor, entry


MANIFEST_SCHEMA_VERSION = 1


def canonicalize(rows: list[Row]) -> tuple[list[Row], dict[str, Any]]:
    result = build_clusters(rows)
    merged_rows: list[Row] = []
    cluster_entries: list[dict[str, Any]] = []
    clusters_collapsed = 0
    clusters_left_colocated = 0

    for cluster in result.clusters:
        row, entry = merge_cluster(cluster)
        merged_rows.append(row)
        if len(cluster.rows) > 1:
            clusters_collapsed += 1
            cluster_entries.append(entry)

    # Count multi-row spatial co-locations we intentionally did NOT merge: any two
    # surviving rows within ABSORB_RADIUS_M of each other.
    for i, left in enumerate(merged_rows):
        left_coords = _lonlat(left)
        if left_coords is None:
            continue
        for right in merged_rows[i + 1 :]:
            right_coords = _lonlat(right)
            if right_coords is None:
                continue
            if (
                haversine_m(left_coords[0], left_coords[1], right_coords[0], right_coords[1])
                <= ABSORB_RADIUS_M
            ):
                clusters_left_colocated += 1
                break

    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "summary": {
            "rows_before": len(rows),
            "rows_after": len(merged_rows),
            "clusters_collapsed": clusters_collapsed,
            "clusters_left_colocated": clusters_left_colocated,
            "review_candidates": len(result.review_candidates),
        },
        "clusters": cluster_entries,
        "review_candidates": [
            {
                "cluster_survivor_poi_id": rc.cluster_survivor_poi_id,
                "candidate_poi_id": rc.candidate_poi_id,
                "candidate_name": rc.candidate_name,
                "distance_m": rc.distance_m,
                "shared_tokens": rc.shared_tokens,
            }
            for rc in result.review_candidates
        ],
        "secondary_flags": [],
    }
    return merged_rows, manifest
