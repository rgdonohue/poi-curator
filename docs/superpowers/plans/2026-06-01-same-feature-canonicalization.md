# Same-Feature Canonicalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse OSM relation+member-way+node duplicates (e.g. Roque Tudesque House) in the Detour export into one canonical row, while provably preserving legitimately co-located features, with a full audit manifest.

**Architecture:** A committed lineage artifact (`reports/osm_relation_lineage.csv`) is extracted once from `poi_source_raw`. The export joins it onto seed rows as `parent_relation_id`/`osm_member_refs` columns, then a pure, testable module (`packages/editorial/poi_curator_editorial/feature_canonicalization.py`) clusters rows by shared relation lineage (plus a tight 35 m + significant-token absorber for non-member nodes), picks a survivor, merges provenance, and emits `query_capable_pois_merged_v2.csv` + a JSON manifest. No DB writes, no migration, no matcher changes.

**Tech Stack:** Python 3.12, stdlib `csv`/`json`/`math`, SQLAlchemy (extractor only), pytest, ruff, mypy. Reuses `poi_curator_ingestion.matching.normalize_name_tokens`.

---

## Spec reference

`docs/superpowers/specs/2026-06-01-same-feature-canonicalization-design.md`. Read it before starting.

## Key confirmed facts (do not re-derive)

- OSM identity forms: `source_record_id` / `POI.osm_id` / seed `osm_id` = `way/461729208`. `dedupe_key` = `osm:way/461729208`. Conversion: `dedupe_key = "osm:" + osm_id`.
- `OSM_SOURCE_NAME = "osm_overpass"` (`pipeline.py:42`). `POISourceRaw.raw_payload_json` stores the verbatim Overpass element (`pipeline.py:373,381`), so a relation payload carries `members: [{type, ref, role}, ...]`.
- `POISourceRaw` columns: `source_name`, `source_record_id`, `raw_payload_json` (JSONB), `is_current` (`db.py:74-90`).
- DB session: `from poi_curator_domain.db import get_session_factory`; `with get_session_factory()() as session:` (pattern from `scripts/run_check_suite.py:46-51`).
- Reusable name normalization: `from poi_curator_ingestion.matching import normalize_name_tokens` (`matching.py:176`). It already strips `COMMON_AFFIXES` (the, of, de, la, san, santa, fe, historic, …) and singularizes. We layer a structural-stopword set on top.
- Export row schema and helpers: `scripts/export_query_capable_pois_merged_v1.py`. `FIELDNAMES` (line 69) is the v1 column order. Helpers `split_pipe`, `merge_pipe_values`, `clean`, `row_quality` (lines 316-368). The current dedupe-by-key collapse is `build_export_rows` (lines 131-164); `write_csv` uses `extrasaction="ignore"` (line 374).
- The Tudesque cluster (from v1 CSV): relation `osm:relation/13422888` "Tudesque House" q=80 (`claim_basis=historic_district|wikidata_id`); way `osm:way/461729209` "Roque Tudesque House East" q=67.5; way `osm:way/461729208` "Roque Tudesque House West" q=67.5; node `osm:node/6479254097` "Roque Tudesque House" q=62.5 (`claim_basis=state_register|historic_district`). Node sits ~9 m from the West wing.
- Non-duplicates that MUST survive: Santa Fe River Park East/West (~570 m apart, no shared relation); Pueblo Alegre North/South Park (~250 m, different streets, no shared relation).
- Tooling: `pytest -q` (config `pyproject.toml:61`), `ruff check`, `mypy` with `disallow_untyped_defs = true` (every function needs annotations). Line length 100.

## File structure

- **Create** `packages/editorial/poi_curator_editorial/feature_canonicalization.py` — pure clustering + merge logic, no I/O. The heart.
- **Create** `scripts/extract_osm_relation_lineage.py` — one-shot DB reader → `reports/osm_relation_lineage.csv` (+ pure parse helper for testing).
- **Create** `reports/osm_relation_lineage.csv` — committed artifact (generated in Task 10).
- **Create** `reports/query_capable_pois_merged_v2.csv` — output (generated in Task 10).
- **Create** `reports/query_capable_pois_merged_v2_merge_manifest.json` — output (generated in Task 10).
- **Modify** `scripts/export_query_capable_pois_merged_v1.py` — load lineage, join columns, call canonicalization, write v2 + manifest, staleness warning, stdout counts.
- **Create** `tests/unit/test_feature_canonicalization.py` — unit tests for the module.
- **Create** `tests/unit/test_osm_relation_lineage.py` — unit tests for the lineage parser.
- **Create** `tests/unit/test_export_merged_v2.py` — end-to-end export test.

---

## Task 1: Geometry + significant-token helpers

**Files:**
- Create: `packages/editorial/poi_curator_editorial/feature_canonicalization.py`
- Test: `tests/unit/test_feature_canonicalization.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_feature_canonicalization.py
import math

from poi_curator_editorial.feature_canonicalization import (
    haversine_m,
    significant_tokens,
)


def test_haversine_known_short_distance() -> None:
    # Tudesque node vs West wing way: ~9 m apart.
    d = haversine_m(-105.938944, 35.6841299, -105.93903457267577, 35.6841571533804)
    assert 5.0 < d < 15.0


def test_haversine_river_park_ends_far_apart() -> None:
    d = haversine_m(-105.94965210201538, 35.68855565878708, -105.9559119, 35.6884733)
    assert d > 500.0


def test_significant_tokens_drops_structural_and_directional() -> None:
    assert significant_tokens("Roque Tudesque House East") == {"roque", "tudesque"}
    assert significant_tokens("Tudesque House") == {"tudesque"}


def test_significant_tokens_two_generic_house_names_do_not_share() -> None:
    assert not (significant_tokens("Adobe House") & significant_tokens("Stone House"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_feature_canonicalization.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'poi_curator_editorial.feature_canonicalization'`.

- [ ] **Step 3: Write minimal implementation**

```python
# packages/editorial/poi_curator_editorial/feature_canonicalization.py
"""Same-feature canonicalization for the Detour merged POI export.

Pure functions only: no DB access, no file I/O. Collapses OSM
relation+member-way+node duplicates into a single canonical row while
preserving legitimately co-located distinct features.
"""

from __future__ import annotations

import math

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_feature_canonicalization.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add packages/editorial/poi_curator_editorial/feature_canonicalization.py tests/unit/test_feature_canonicalization.py
git commit -m "feat: add geometry and significant-token helpers for canonicalization

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Cluster model and lineage grouping

**Files:**
- Modify: `packages/editorial/poi_curator_editorial/feature_canonicalization.py`
- Test: `tests/unit/test_feature_canonicalization.py`

Rows are plain `dict[str, str]` (the export rows), enriched with two extra columns: `parent_relation_id` (the `osm:relation/<id>` a member belongs to, else `""`) and `osm_member_refs` (pipe list on a relation row, else `""`). The cluster key groups by shared relation lineage — by `parent_relation_id` itself, so members stay grouped even when the relation row was filtered out.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_feature_canonicalization.py
from poi_curator_editorial.feature_canonicalization import build_clusters


def _row(**kw: str) -> dict[str, str]:
    base = {
        "poi_id": "", "dedupe_key": "", "name": "", "lon": "0", "lat": "0",
        "quality_score": "50", "parent_relation_id": "", "osm_member_refs": "",
    }
    base.update(kw)
    return base


def _tudesque_rows() -> list[dict[str, str]]:
    rel = _row(poi_id="p-rel", dedupe_key="osm:relation/13422888", name="Tudesque House",
               lon="-105.93883405", lat="35.68407725", quality_score="80",
               osm_member_refs="osm:way/461729208|osm:way/461729209")
    way_e = _row(poi_id="p-e", dedupe_key="osm:way/461729209", name="Roque Tudesque House East",
                 lon="-105.9387482642101", lat="35.684025653980406", quality_score="67.5",
                 parent_relation_id="osm:relation/13422888")
    way_w = _row(poi_id="p-w", dedupe_key="osm:way/461729208", name="Roque Tudesque House West",
                 lon="-105.93903457267577", lat="35.6841571533804", quality_score="67.5",
                 parent_relation_id="osm:relation/13422888")
    node = _row(poi_id="p-node", dedupe_key="osm:node/6479254097", name="Roque Tudesque House",
                lon="-105.938944", lat="35.6841299", quality_score="62.5")
    return [rel, way_e, way_w, node]


def test_lineage_groups_relation_with_members() -> None:
    result = build_clusters(_tudesque_rows())
    cluster = next(c for c in result.clusters if len(c.rows) > 1)
    keys = {r["dedupe_key"] for r in cluster.rows}
    # relation + 2 ways + absorbed node = 4 rows, one cluster.
    assert keys == {
        "osm:relation/13422888", "osm:way/461729208",
        "osm:way/461729209", "osm:node/6479254097",
    }


def test_absorbed_node_marked_node_proximity() -> None:
    result = build_clusters(_tudesque_rows())
    cluster = next(c for c in result.clusters if len(c.rows) > 1)
    assert "node_proximity" in cluster.reasons
    assert "osm_relation_members" in cluster.reasons


def test_orphaned_relation_members_still_cluster() -> None:
    # Relation row filtered out; member ways must still group via parent_relation_id.
    rows = [r for r in _tudesque_rows() if r["dedupe_key"] != "osm:relation/13422888"]
    result = build_clusters(rows)
    cluster = next(c for c in result.clusters if len(c.rows) > 1)
    keys = {r["dedupe_key"] for r in cluster.rows}
    assert {"osm:way/461729208", "osm:way/461729209"} <= keys


def test_distinct_far_apart_features_not_merged() -> None:
    rows = [
        _row(poi_id="rpe", dedupe_key="osm:way/473591088", name="Santa Fe River Park East",
             lon="-105.94965210201538", lat="35.68855565878708", quality_score="77.5"),
        _row(poi_id="rpw", dedupe_key="osm:node/357605718", name="Santa Fe River Park West",
             lon="-105.9559119", lat="35.6884733", quality_score="67.5"),
        _row(poi_id="pan", dedupe_key="osm:way/310660233", name="Pueblo Alegre North Park",
             lon="-105.98274917932312", lat="35.66904224454074", quality_score="62.5"),
        _row(poi_id="pas", dedupe_key="osm:way/611738952", name="Pueblo Alegre South Park",
             lon="-105.98280489311009", lat="35.666776524204224", quality_score="67.5"),
    ]
    result = build_clusters(rows)
    assert all(len(c.rows) == 1 for c in result.clusters)


def test_review_candidate_in_near_miss_band() -> None:
    # A same-token non-member ~50 m from the cluster: flagged, not merged.
    rows = _tudesque_rows()
    # ~50 m from the West wing (-105.93903): inside the 35-75 m review band, not 35 m.
    rows.append(_row(poi_id="near", dedupe_key="osm:node/999", name="Tudesque Annex",
                     lon="-105.93958", lat="35.68416", quality_score="40"))
    result = build_clusters(rows)
    big = next(c for c in result.clusters if len(c.rows) > 1)
    assert all(r["poi_id"] != "near" for r in big.rows)
    assert any(rc.candidate_poi_id == "near" for rc in result.review_candidates)


def test_two_generic_house_rows_within_35m_do_not_merge() -> None:
    rows = [
        _row(poi_id="a", dedupe_key="osm:node/1", name="Adobe House",
             lon="-105.9390", lat="35.6841", quality_score="50"),
        _row(poi_id="b", dedupe_key="osm:node/2", name="Stone House",
             lon="-105.93902", lat="35.68411", quality_score="50"),
    ]
    result = build_clusters(rows)
    assert all(len(c.rows) == 1 for c in result.clusters)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_feature_canonicalization.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_clusters'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to packages/editorial/poi_curator_editorial/feature_canonicalization.py
from dataclasses import dataclass, field

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


def _lonlat(row: Row) -> tuple[float, float]:
    return float(row["lon"]), float(row["lat"])


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
        lon, lat = _lonlat(row)
        tokens = significant_tokens(row["name"])
        best_cluster: Cluster | None = None
        best_distance = ABSORB_RADIUS_M
        review_hit: tuple[Cluster, float, set[str]] | None = None
        for cluster in lineage.values():
            for member in cluster.rows:
                shared = tokens & significant_tokens(member["name"])
                if not shared:
                    continue
                m_lon, m_lat = _lonlat(member)
                distance = haversine_m(lon, lat, m_lon, m_lat)
                if distance <= best_distance:
                    best_distance = distance
                    best_cluster = cluster
                elif distance <= REVIEW_RADIUS_M and review_hit is None:
                    review_hit = (cluster, distance, shared)
        if best_cluster is not None:
            best_cluster.rows.append(row)
            best_cluster.reasons.add("node_proximity")
        elif review_hit is not None:
            cluster, distance, shared = review_hit
            survivor = _select_survivor(cluster.rows)
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
```

Note: `_select_survivor` is defined in Task 3. To keep this task green on its own, add a temporary forward stub at the bottom of the file now and replace it in Task 3:

```python
def _select_survivor(rows: list[Row]) -> Row:  # replaced in Task 3
    return max(rows, key=_quality)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_feature_canonicalization.py -q`
Expected: PASS (all clustering tests green).

- [ ] **Step 5: Commit**

```bash
git add packages/editorial/poi_curator_editorial/feature_canonicalization.py tests/unit/test_feature_canonicalization.py
git commit -m "feat: cluster export rows by OSM relation lineage with tight absorber

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Survivor selection and display-name choice

**Files:**
- Modify: `packages/editorial/poi_curator_editorial/feature_canonicalization.py`
- Test: `tests/unit/test_feature_canonicalization.py`

Survivor = canonical row (geometry, score, poi_id): highest `quality_score`; tie-break `relation > way > node`; then lowest `poi_id`. Display name is chosen separately: prefer the member whose provenance carries the strongest identity evidence (`state_register` > `nrhp` > `historic`), then the most specific name (most significant tokens, then longest). Other names become aliases.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_feature_canonicalization.py
from poi_curator_editorial.feature_canonicalization import (
    choose_display_name,
    select_survivor,
)


def test_survivor_is_highest_quality_relation() -> None:
    survivor = select_survivor(_tudesque_rows())
    assert survivor["dedupe_key"] == "osm:relation/13422888"  # q=80


def test_survivor_tie_break_relation_over_way() -> None:
    rows = [
        _row(poi_id="w", dedupe_key="osm:way/1", name="W", quality_score="70"),
        _row(poi_id="r", dedupe_key="osm:relation/1", name="R", quality_score="70"),
    ]
    assert select_survivor(rows)["dedupe_key"] == "osm:relation/1"


def test_survivor_tie_break_lowest_poi_id_when_same_type() -> None:
    rows = [
        _row(poi_id="zzz", dedupe_key="osm:node/2", name="Z", quality_score="70"),
        _row(poi_id="aaa", dedupe_key="osm:node/1", name="A", quality_score="70"),
    ]
    assert select_survivor(rows)["poi_id"] == "aaa"


def test_display_name_prefers_state_register_over_relation_label() -> None:
    rows = [
        _row(poi_id="p-rel", dedupe_key="osm:relation/13422888", name="Tudesque House",
             quality_score="80", claim_basis="historic_district|wikidata_id"),
        _row(poi_id="p-node", dedupe_key="osm:node/6479254097", name="Roque Tudesque House",
             quality_score="62.5", claim_basis="state_register|historic_district"),
    ]
    chosen, aliases = choose_display_name(rows)
    assert chosen == "Roque Tudesque House"
    assert "Tudesque House" in aliases
    assert "Roque Tudesque House" not in aliases
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_feature_canonicalization.py -q`
Expected: FAIL — `ImportError: cannot import name 'select_survivor'`.

- [ ] **Step 3: Write minimal implementation**

Replace the temporary `_select_survivor` stub from Task 2 with the real implementation and add the public helpers:

```python
# in packages/editorial/poi_curator_editorial/feature_canonicalization.py

_TYPE_RANK = {"relation": 0, "way": 1, "node": 2}

# Identity-evidence weights scanned across provenance columns for display-name choice.
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
```

Then update the internal reference in `build_clusters` to call `select_survivor` (rename the stub usage):

```python
# in build_clusters, the review-candidate branch:
            survivor = select_survivor(cluster.rows)
```

Delete the temporary `_select_survivor` stub.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_feature_canonicalization.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/editorial/poi_curator_editorial/feature_canonicalization.py tests/unit/test_feature_canonicalization.py
git commit -m "feat: survivor selection and identity-evidence display-name choice

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Merge a cluster into one row with audit columns + idempotency

**Files:**
- Modify: `packages/editorial/poi_curator_editorial/feature_canonicalization.py`
- Test: `tests/unit/test_feature_canonicalization.py`

Produces the surviving row: survivor fields, chosen display name, pipe-unioned `evidence_sources`/`active_themes`/`preferred_aliases` (aliases include dropped names), `wikipedia_title` filled only if empty, and audit columns `merged_from` + `merge_reason`. Idempotent: ignores incoming `merged_from`/`merge_reason`; alias/provenance unions are set-stable.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_feature_canonicalization.py
from poi_curator_editorial.feature_canonicalization import merge_cluster


def test_merge_cluster_produces_single_audited_row() -> None:
    cluster = build_clusters(_tudesque_rows()).clusters
    big = next(c for c in cluster if len(c.rows) > 1)
    row, entry = merge_cluster(big)
    assert row["poi_id"] == "p-rel"
    assert row["name"] == "Roque Tudesque House"  # state_register node name wins
    assert set(row["merged_from"].split("|")) == {
        "osm:way/461729208", "osm:way/461729209", "osm:node/6479254097",
    }
    assert "osm_relation_members" in row["merge_reason"]
    assert "node_proximity" in row["merge_reason"]
    assert "Tudesque House" in row["preferred_aliases"]
    assert entry["survivor_poi_id"] == "p-rel"
    assert entry["chosen_display_name"] == "Roque Tudesque House"


def test_merge_cluster_unions_evidence_sources() -> None:
    rows = _tudesque_rows()
    rows[0]["evidence_sources"] = "city_gis_historic_districts|wikidata_id"
    rows[3]["evidence_sources"] = "nm_hpd_register_workbook|city_gis_historic_districts"
    big = next(c for c in build_clusters(rows).clusters if len(c.rows) > 1)
    row, _ = merge_cluster(big)
    sources = row["evidence_sources"].split("|")
    assert sorted(sources) == sorted(set(sources))  # no dupes
    assert "nm_hpd_register_workbook" in sources
    assert "wikidata_id" in sources


def test_merge_is_idempotent_on_already_merged_row() -> None:
    big = next(c for c in build_clusters(_tudesque_rows()).clusters if len(c.rows) > 1)
    merged_once, _ = merge_cluster(big)
    # Second pass: a singleton cluster of the already-merged row must not grow lists.
    from poi_curator_editorial.feature_canonicalization import Cluster
    again, _ = merge_cluster(Cluster(rows=[dict(merged_once)], reasons=set()))
    assert again["preferred_aliases"] == merged_once["preferred_aliases"]
    assert again["merged_from"] == ""  # singleton: nothing collapsed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_feature_canonicalization.py -q`
Expected: FAIL — `ImportError: cannot import name 'merge_cluster'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to packages/editorial/poi_curator_editorial/feature_canonicalization.py
from typing import Any


def _union_pipe(values: list[str]) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        for item in (part.strip() for part in value.split("|")):
            if item and item not in seen:
                seen.add(item)
                out.append(item)
    return "|".join(out)


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
        "dropped": [
            {
                "poi_id": row["poi_id"],
                "dedupe_key": row["dedupe_key"],
                "name": row["name"],
                "lon": float(row["lon"]),
                "lat": float(row["lat"]),
                "distance_m": round(
                    haversine_m(
                        float(row["lon"]), float(row["lat"]),
                        float(survivor["lon"]), float(survivor["lat"]),
                    ),
                    2,
                ),
            }
            for row in dropped
        ],
        "merge_reason": survivor["merge_reason"],
    }
    return survivor, entry
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_feature_canonicalization.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/editorial/poi_curator_editorial/feature_canonicalization.py tests/unit/test_feature_canonicalization.py
git commit -m "feat: merge clusters into one audited row, idempotently

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Top-level `canonicalize` + manifest assembly

**Files:**
- Modify: `packages/editorial/poi_curator_editorial/feature_canonicalization.py`
- Test: `tests/unit/test_feature_canonicalization.py`

`canonicalize(rows)` returns `(merged_rows, manifest)` where the manifest has `schema_version`, a `summary` block, `clusters` (only multi-row collapses), `review_candidates`, and an empty `secondary_flags` list (populated by the export in Task 6). Singleton rows still get empty `merged_from`/`merge_reason` columns so the CSV schema is uniform.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_feature_canonicalization.py
from poi_curator_editorial.feature_canonicalization import canonicalize


def test_canonicalize_collapses_tudesque_only() -> None:
    rows = _tudesque_rows() + [
        _row(poi_id="rpe", dedupe_key="osm:way/473591088", name="Santa Fe River Park East",
             lon="-105.94965210201538", lat="35.68855565878708", quality_score="77.5"),
        _row(poi_id="rpw", dedupe_key="osm:node/357605718", name="Santa Fe River Park West",
             lon="-105.9559119", lat="35.6884733", quality_score="67.5"),
    ]
    merged, manifest = canonicalize(rows)
    assert manifest["schema_version"] == 1
    assert manifest["summary"]["rows_before"] == 6
    assert manifest["summary"]["rows_after"] == 3  # 1 Tudesque + 2 river park
    assert manifest["summary"]["clusters_collapsed"] == 1
    assert len(manifest["clusters"]) == 1
    # Every output row carries the audit columns.
    assert all("merged_from" in row and "merge_reason" in row for row in merged)


def test_canonicalize_is_idempotent() -> None:
    rows = _tudesque_rows()
    merged_once, _ = canonicalize(rows)
    merged_twice, manifest2 = canonicalize(merged_once)
    assert len(merged_twice) == len(merged_once)
    alias_once = next(r["preferred_aliases"] for r in merged_once if r["merged_from"])
    alias_twice = next(r["preferred_aliases"] for r in merged_twice if r["poi_id"] == "p-rel")
    assert alias_once == alias_twice  # lists do not grow
    assert manifest2["summary"]["clusters_collapsed"] == 0  # nothing left to collapse
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_feature_canonicalization.py -q`
Expected: FAIL — `ImportError: cannot import name 'canonicalize'`.

- [ ] **Step 3: Write minimal implementation**

```python
# append to packages/editorial/poi_curator_editorial/feature_canonicalization.py
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
        for right in merged_rows[i + 1 :]:
            if (
                haversine_m(
                    float(left["lon"]), float(left["lat"]),
                    float(right["lon"]), float(right["lat"]),
                )
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_feature_canonicalization.py -q`
Expected: PASS.

- [ ] **Step 5: Run full lint/type/test gate and commit**

Run: `python3 -m pytest tests/unit/test_feature_canonicalization.py -q && python3 -m ruff check packages/editorial && python3 -m mypy packages/editorial/poi_curator_editorial/feature_canonicalization.py`
Expected: all clean.

```bash
git add packages/editorial/poi_curator_editorial/feature_canonicalization.py tests/unit/test_feature_canonicalization.py
git commit -m "feat: top-level canonicalize() with merge manifest assembly

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Lineage parser (pure) + extractor script

**Files:**
- Create: `scripts/extract_osm_relation_lineage.py`
- Test: `tests/unit/test_osm_relation_lineage.py`

A pure function `relation_lineage_from_elements(elements)` turns Overpass elements into a list of `(relation_record_id, [member_record_ids])` rows, tested without a DB. The script wraps it: read `poi_source_raw`, write `reports/osm_relation_lineage.csv` with a provenance header.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_osm_relation_lineage.py
from scripts.extract_osm_relation_lineage import (
    LINEAGE_FIELDNAMES,
    relation_lineage_from_elements,
)


def test_relation_lineage_extracts_member_refs() -> None:
    elements = [
        {
            "type": "relation",
            "id": 13422888,
            "tags": {"name": "Tudesque House"},
            "members": [
                {"type": "way", "ref": 461729208, "role": "outer"},
                {"type": "way", "ref": 461729209, "role": "outer"},
            ],
        },
        {"type": "way", "id": 461729208, "tags": {}},
        {"type": "node", "id": 1, "tags": {}},
    ]
    lineage = relation_lineage_from_elements(elements)
    assert lineage == [("relation/13422888", ["way/461729208", "way/461729209"])]


def test_relation_without_members_is_skipped() -> None:
    elements = [{"type": "relation", "id": 7, "tags": {}, "members": []}]
    assert relation_lineage_from_elements(elements) == []


def test_lineage_fieldnames_shape() -> None:
    assert LINEAGE_FIELDNAMES == ["relation_record_id", "member_record_ids"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/test_osm_relation_lineage.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.extract_osm_relation_lineage'`.

(If `scripts` is not importable, add an empty `scripts/__init__.py` — check first with `ls scripts/__init__.py`; the repo already imports `scripts.*` patterns are absent, so create it if the import fails.)

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python3
# scripts/extract_osm_relation_lineage.py
"""Extract OSM relation->member lineage from poi_source_raw into a committed CSV.

Run once when the corpus is (re)ingested. Output feeds the export-time
same-feature canonicalization, which stays pure-CSV.
"""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

OUTPUT_CSV = Path("reports/osm_relation_lineage.csv")
OSM_SOURCE_NAME = "osm_overpass"
LINEAGE_FIELDNAMES = ["relation_record_id", "member_record_ids"]


def relation_lineage_from_elements(
    elements: list[dict[str, Any]],
) -> list[tuple[str, list[str]]]:
    lineage: list[tuple[str, list[str]]] = []
    for element in elements:
        if element.get("type") != "relation":
            continue
        members = element.get("members") or []
        member_ids = [
            f"{member['type']}/{member['ref']}"
            for member in members
            if member.get("type") and member.get("ref") is not None
        ]
        if not member_ids:
            continue
        lineage.append((f"relation/{element['id']}", member_ids))
    lineage.sort(key=lambda item: item[0])
    return lineage


def write_lineage_csv(
    path: Path, lineage: list[tuple[str, list[str]]], *, source_row_count: int
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with path.open("w", newline="", encoding="utf-8") as handle:
        handle.write(
            f"# extracted_at={stamp} source=poi_source_raw "
            f"source_current_rows={source_row_count}\n"
        )
        writer = csv.writer(handle)
        writer.writerow(LINEAGE_FIELDNAMES)
        for relation_id, member_ids in lineage:
            writer.writerow([relation_id, "|".join(member_ids)])


def main() -> int:
    from poi_curator_domain.db import get_session_factory
    from poi_curator_domain.db import POISourceRaw
    from sqlalchemy import select

    session_factory = get_session_factory()
    with session_factory() as session:
        rows = list(
            session.scalars(
                select(POISourceRaw).where(
                    POISourceRaw.source_name == OSM_SOURCE_NAME,
                    POISourceRaw.is_current.is_(True),
                )
            )
        )
        elements = [row.raw_payload_json for row in rows]
    lineage = relation_lineage_from_elements(elements)
    write_lineage_csv(OUTPUT_CSV, lineage, source_row_count=len(elements))
    print(f"wrote {OUTPUT_CSV}")
    print(f"relations_with_members={len(lineage)} source_current_rows={len(elements)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/test_osm_relation_lineage.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_osm_relation_lineage.py tests/unit/test_osm_relation_lineage.py
test -f scripts/__init__.py && git add scripts/__init__.py
git commit -m "feat: OSM relation lineage extractor (pure parser + DB script)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Wire canonicalization into the export script

**Files:**
- Modify: `scripts/export_query_capable_pois_merged_v1.py`
- Test: `tests/unit/test_export_merged_v2.py` (added in Task 8)

Add lineage loading, the two join columns, the canonicalization call, v2 + manifest writing, a staleness warning, and stdout counts. The existing `build_export_rows` already collapses exact `dedupe_key` duplicates — keep it; canonicalization runs on its output.

- [ ] **Step 1: Add module-level constants and lineage loader**

After the existing `OUTPUT_CSV` definition (line 14), add:

```python
OUTPUT_CSV_V2 = Path("reports/query_capable_pois_merged_v2.csv")
MANIFEST_JSON = Path("reports/query_capable_pois_merged_v2_merge_manifest.json")
LINEAGE_CSV = Path("reports/osm_relation_lineage.csv")
AUDIT_COLUMNS = ["merged_from", "merge_reason"]
```

Add `FIELDNAMES_V2 = FIELDNAMES + AUDIT_COLUMNS` immediately after the `FIELDNAMES` definition (line 69).

Add a loader function (near `load_contexts`):

```python
def load_relation_lineage(path: Path) -> tuple[dict[str, str], dict[str, str], int]:
    """Return (member_dedupe_key -> parent_relation_dedupe_key,
    relation_dedupe_key -> piped member dedupe_keys, stamped_source_row_count)."""
    parent_of: dict[str, str] = {}
    members_of: dict[str, str] = {}
    stamped_count = -1
    if not path.exists():
        return parent_of, members_of, stamped_count
    with path.open(newline="", encoding="utf-8") as handle:
        first = handle.readline()
        if first.startswith("#"):
            for field in first.lstrip("#").split():
                if field.startswith("source_current_rows="):
                    stamped_count = int(field.split("=", 1)[1])
        else:
            handle.seek(0)
        for row in csv.DictReader(handle):
            relation_key = f"osm:{row['relation_record_id']}"
            member_keys = [
                f"osm:{member}" for member in row["member_record_ids"].split("|") if member
            ]
            members_of[relation_key] = "|".join(member_keys)
            for member_key in member_keys:
                parent_of[member_key] = relation_key
    return parent_of, members_of, stamped_count
```

- [ ] **Step 2: Verify it parses**

Run: `python3 -c "import ast; ast.parse(open('scripts/export_query_capable_pois_merged_v1.py').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Add the staleness check and join helper**

```python
def warn_if_lineage_stale(
    lineage_path: Path, seed_path: Path, stamped_count: int, seed_row_count: int
) -> None:
    if not lineage_path.exists():
        print(f"WARNING: lineage artifact {lineage_path} missing; no relation merges applied")
        return
    if seed_path.exists() and lineage_path.stat().st_mtime < seed_path.stat().st_mtime:
        print(
            f"WARNING: lineage artifact {lineage_path} is older than seed {seed_path}; "
            "re-run scripts/extract_osm_relation_lineage.py"
        )
    if 0 <= stamped_count and abs(stamped_count - seed_row_count) > seed_row_count:
        print(
            f"WARNING: lineage source_current_rows={stamped_count} differs sharply from "
            f"seed rows={seed_row_count}; lineage may be stale"
        )


def attach_lineage_columns(
    rows: list[dict[str, str]],
    parent_of: dict[str, str],
    members_of: dict[str, str],
) -> None:
    for row in rows:
        key = row["dedupe_key"]
        row["parent_relation_id"] = parent_of.get(key, "")
        row["osm_member_refs"] = members_of.get(key, "")
```

- [ ] **Step 4: Rewrite `main` to produce v2**

Replace the body of `main` (lines 82-91) with:

```python
def main() -> int:
    from poi_curator_editorial.feature_canonicalization import canonicalize

    args = parse_args()
    seed_rows = read_csv(args.input)
    contexts = load_contexts(args.context)
    rows = build_export_rows(seed_rows, contexts)

    parent_of, members_of, stamped_count = load_relation_lineage(LINEAGE_CSV)
    warn_if_lineage_stale(LINEAGE_CSV, args.input, stamped_count, len(seed_rows))
    attach_lineage_columns(rows, parent_of, members_of)

    merged_rows, manifest = canonicalize(rows)

    write_csv(OUTPUT_CSV_V2, merged_rows, fieldnames=FIELDNAMES_V2)
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    validate_rows(merged_rows)

    summary = manifest["summary"]
    print(f"wrote {OUTPUT_CSV_V2}")
    print(f"wrote {MANIFEST_JSON}")
    print(
        "rows_before={rows_before} rows_after={rows_after} "
        "clusters_collapsed={clusters_collapsed} "
        "clusters_left_colocated={clusters_left_colocated} "
        "review_candidates={review_candidates}".format(**summary)
    )
    return 0
```

Update `write_csv` to take an optional `fieldnames` argument (default keeps old behavior):

```python
def write_csv(
    path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file, fieldnames=fieldnames or FIELDNAMES, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
```

`validate_rows` already tolerates extra columns (it iterates `FIELDNAMES`, and the audit columns are additive). It also asserts no duplicate `dedupe_key` survives — which now also confirms the merge produced unique keys.

- [ ] **Step 5: Verify it parses and lints**

Run: `python3 -c "import ast; ast.parse(open('scripts/export_query_capable_pois_merged_v1.py').read()); print('ok')" && python3 -m ruff check scripts/export_query_capable_pois_merged_v1.py`
Expected: `ok` and no ruff errors.

- [ ] **Step 6: Commit**

```bash
git add scripts/export_query_capable_pois_merged_v1.py
git commit -m "feat: wire same-feature canonicalization into the v2 export

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: End-to-end export test on a fixture seed

**Files:**
- Create: `tests/unit/test_export_merged_v2.py`

Drives the real export functions over a tiny in-memory seed (no DB), asserting the Tudesque collapse and that the manifest accounting matches the row delta.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_export_merged_v2.py
import csv
import json
from pathlib import Path

import scripts.export_query_capable_pois_merged_v1 as exporter


def _write_seed(path: Path) -> None:
    # Minimal seed: Tudesque relation + 2 ways + node, plus one unrelated row.
    header = [
        "poi_id", "dedupe_key", "name", "lon", "lat", "primary_category",
        "display_priority", "quality_score", "walk_affinity_hint", "drive_affinity_hint",
        "wikipedia_title", "short_description", "description_map_v1", "description_card_v1",
        "description_subcategory_v1", "description_confidence_v1", "description_basis_v1",
        "evidence_sources", "preferred_aliases", "active_themes", "record_origin",
        "source_basis", "evidence_strength", "description_status", "description_method",
        "description_review_status", "claim_basis", "risk_flags", "display_categories",
        "themes", "osm_id",
    ]

    def row(**kw: str) -> dict[str, str]:
        base = {col: "" for col in header}
        base.update({
            "primary_category": "history", "display_priority": "50",
            "walk_affinity_hint": "0.55", "drive_affinity_hint": "0.9",
            "description_confidence_v1": "medium", "record_origin": "database",
        })
        base.update(kw)
        return base

    rows = [
        row(poi_id="p-rel", dedupe_key="osm:relation/13422888", name="Tudesque House",
            lon="-105.93883405", lat="35.68407725", quality_score="80",
            claim_basis="historic_district"),
        row(poi_id="p-e", dedupe_key="osm:way/461729209", name="Roque Tudesque House East",
            lon="-105.9387482642101", lat="35.684025653980406", quality_score="67.5",
            claim_basis="historic_district"),
        row(poi_id="p-w", dedupe_key="osm:way/461729208", name="Roque Tudesque House West",
            lon="-105.93903457267577", lat="35.6841571533804", quality_score="67.5",
            claim_basis="historic_district"),
        row(poi_id="p-node", dedupe_key="osm:node/6479254097", name="Roque Tudesque House",
            lon="-105.938944", lat="35.6841299", quality_score="62.5",
            claim_basis="state_register|historic_district"),
        row(poi_id="solo", dedupe_key="osm:node/111", name="Cristo Rey Church",
            lon="-105.92", lat="35.69", quality_score="70", claim_basis="historic_district"),
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def _write_lineage(path: Path) -> None:
    path.write_text(
        "# extracted_at=2026-06-01T00:00:00Z source=poi_source_raw source_current_rows=5\n"
        "relation_record_id,member_record_ids\n"
        "relation/13422888,way/461729208|way/461729209\n",
        encoding="utf-8",
    )


def test_export_v2_collapses_tudesque(tmp_path: Path, monkeypatch) -> None:
    seed = tmp_path / "seed.csv"
    context = tmp_path / "context.csv"  # absent -> empty contexts is fine
    lineage = tmp_path / "lineage.csv"
    out_v2 = tmp_path / "v2.csv"
    manifest = tmp_path / "manifest.json"
    _write_seed(seed)
    _write_lineage(lineage)

    monkeypatch.setattr(exporter, "LINEAGE_CSV", lineage)
    monkeypatch.setattr(exporter, "OUTPUT_CSV_V2", out_v2)
    monkeypatch.setattr(exporter, "MANIFEST_JSON", manifest)
    monkeypatch.setattr(
        "sys.argv",
        ["export", "--input", str(seed), "--context", str(context), "--output", str(out_v2)],
    )

    assert exporter.main() == 0

    with out_v2.open(newline="", encoding="utf-8") as handle:
        out_rows = list(csv.DictReader(handle))
    names = {r["name"] for r in out_rows}
    # Tudesque collapses to 1 row (state-register display name) + the solo church = 2.
    assert len(out_rows) == 2
    assert "Roque Tudesque House" in names
    assert "Cristo Rey Church" in names

    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["summary"]["clusters_collapsed"] == 1
    assert data["summary"]["rows_before"] - data["summary"]["rows_after"] == 3
    survivor = next(r for r in out_rows if r["name"] == "Roque Tudesque House")
    assert set(survivor["merged_from"].split("|")) == {
        "osm:way/461729208", "osm:way/461729209", "osm:node/6479254097",
    }
```

- [ ] **Step 2: Run test to verify it fails (then passes)**

Run: `python3 -m pytest tests/unit/test_export_merged_v2.py -q`
Expected: PASS if Task 7 is correct. If it fails on `--output` being required-but-unused, note `main` ignores `args.output` (writes to `OUTPUT_CSV_V2`); that is intentional. Fix any real failures in `export_query_capable_pois_merged_v1.py`, not the test.

- [ ] **Step 3: Run the whole suite + lint + types**

Run: `python3 -m pytest -q && python3 -m ruff check packages scripts tests && python3 -m mypy packages/editorial/poi_curator_editorial/feature_canonicalization.py scripts/extract_osm_relation_lineage.py`
Expected: all green. Fix regressions before committing.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_export_merged_v2.py
git commit -m "test: end-to-end v2 export collapses Tudesque, manifest accounting holds

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Generate real artifacts and verify against live data

**Files:**
- Create: `reports/osm_relation_lineage.csv`
- Create: `reports/query_capable_pois_merged_v2.csv`
- Create: `reports/query_capable_pois_merged_v2_merge_manifest.json`

This task needs the DB up (for the lineage extractor only). If the DB is unavailable, STOP and report — the unit/e2e tests already prove the logic; this step produces the committed artifacts.

- [ ] **Step 1: Bring up the DB (if not running)**

Run: `make db-up && make migrate`
Expected: PostGIS reachable.

- [ ] **Step 2: Extract lineage**

Run: `python3 scripts/extract_osm_relation_lineage.py`
Expected: `wrote reports/osm_relation_lineage.csv` and a `relations_with_members=` count (≈16 OSM relations exist in the seed; expect a similar order).

- [ ] **Step 3: Run the v2 export**

Run: `python3 scripts/export_query_capable_pois_merged_v1.py`
Expected: `wrote reports/query_capable_pois_merged_v2.csv`, a manifest, and a counts line. Confirm `clusters_collapsed >= 1` and `review_candidates` is reported.

- [ ] **Step 4: Verify the Tudesque collapse and non-merges by hand**

Run:
```bash
python3 - <<'PY'
import csv, json
rows = list(csv.DictReader(open("reports/query_capable_pois_merged_v2.csv")))
names = [r["name"] for r in rows]
print("v2 rows:", len(rows))
print("Tudesque rows:", [n for n in names if "udesque" in n])
print("River Park rows:", [n for n in names if "River Park" in n])
print("Pueblo Alegre rows:", [n for n in names if "Pueblo Alegre" in n])
m = json.load(open("reports/query_capable_pois_merged_v2_merge_manifest.json"))
print("summary:", m["summary"])
PY
```
Expected: exactly one Tudesque row; River Park East/West BOTH present; Pueblo Alegre North/South BOTH present. If a non-duplicate was merged, STOP — the radius/token guard has a bug; do not commit artifacts.

- [ ] **Step 5: Idempotency check on the real file**

Run:
```bash
python3 - <<'PY'
import csv
import scripts.export_query_capable_pois_merged_v1 as e
from poi_curator_editorial.feature_canonicalization import canonicalize
rows = list(csv.DictReader(open("reports/query_capable_pois_merged_v2.csv")))
for r in rows:
    r.setdefault("parent_relation_id", ""); r.setdefault("osm_member_refs", "")
merged, manifest = canonicalize(rows)
assert manifest["summary"]["clusters_collapsed"] == 0, "second pass re-merged!"
print("idempotent: OK, rows unchanged =", len(merged) == len(rows))
PY
```
Expected: `idempotent: OK, rows unchanged = True`.

- [ ] **Step 6: Commit artifacts**

```bash
git add reports/osm_relation_lineage.csv reports/query_capable_pois_merged_v2.csv reports/query_capable_pois_merged_v2_merge_manifest.json
git commit -m "data: generate v2 merged export, lineage artifact, and merge manifest

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/DATA_QUALITY_GOVERNANCE.md`

- [ ] **Step 1: Document the v2 export + canonicalization**

Add a short subsection to `docs/DATA_QUALITY_GOVERNANCE.md` describing: the same-feature canonicalization step, that it is lineage-anchored (relation↔members) with a 35 m + significant-token absorber, the 35–75 m review-candidate band, the audit columns (`merged_from`, `merge_reason`), the manifest, and that `osm_relation_lineage.csv` must be regenerated via `scripts/extract_osm_relation_lineage.py` after re-ingestion. Reference the spec file.

Add one line to `README.md` near the export/seed bullets noting the v2 export and manifest.

- [ ] **Step 2: Verify docs build/read cleanly**

Run: `python3 -m pytest -q`
Expected: still green (docs don't affect tests; this re-confirms nothing regressed).

- [ ] **Step 3: Commit**

```bash
git add README.md docs/DATA_QUALITY_GOVERNANCE.md
git commit -m "docs: describe same-feature canonicalization and v2 export

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-review checklist (completed by plan author)

- **Spec coverage:** lineage extraction (T6/T9), carried lineage columns (T7), lineage-by-`parent_relation_id` incl. orphaned relation (T2), 35 m + significant-token absorber (T2), 35–75 m review band (T2/T5), survivor + relation>way>node tie-break (T3), decoupled display name via identity evidence (T3), provenance union + alias preservation (T4), audit columns (T4), idempotency (T4/T5/T9), JSON manifest with schema_version + summary + review_candidates + secondary_flags (T5), v2 CSV with v1 schema + 2 columns (T7), staleness warning + provenance stamp (T6/T7), stdout counts (T7), over-merge protection verified on real data (T9), secondary items flagged-not-fixed (manifest `secondary_flags`, left empty by default — acceptable per spec; populating is out of scope). All covered.
- **Placeholder scan:** no TBD/TODO; every code step has complete code.
- **Type consistency:** `Row = dict[str, str]`, `Cluster`, `ClusterResult`, `ReviewCandidate`, `canonicalize`, `merge_cluster`, `select_survivor`, `choose_display_name`, `build_clusters`, `significant_tokens`, `haversine_m`, `relation_lineage_from_elements`, `LINEAGE_FIELDNAMES`, `FIELDNAMES_V2`, `load_relation_lineage`, `attach_lineage_columns`, `warn_if_lineage_stale` — names consistent across tasks. `write_csv` gains an optional `fieldnames` param without breaking existing callers.
