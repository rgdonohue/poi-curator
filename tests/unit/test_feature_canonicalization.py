from poi_curator_editorial.feature_canonicalization import (
    build_clusters,
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


def test_haversine_identical_points_is_zero() -> None:
    assert haversine_m(-105.9, 35.6, -105.9, 35.6) == 0.0


def test_significant_tokens_empty_name_is_empty_set() -> None:
    assert significant_tokens("") == set()


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
    rows = _tudesque_rows()
    # ~50 m from the West wing (-105.93903): inside the 35-75 m review band, not 35 m.
    rows.append(_row(poi_id="near", dedupe_key="osm:node/999", name="Tudesque Annex",
                     lon="-105.93958", lat="35.68416", quality_score="40"))
    result = build_clusters(rows)
    big = next(c for c in result.clusters if len(c.rows) > 1)
    assert all(r["poi_id"] != "near" for r in big.rows)
    assert any(rc.candidate_poi_id == "near" for rc in result.review_candidates)


def test_row_with_missing_coordinates_becomes_singleton() -> None:
    rows = _tudesque_rows()
    rows.append(_row(poi_id="bad", dedupe_key="osm:node/888", name="Tudesque House",
                     lon="", lat="", quality_score="30"))
    result = build_clusters(rows)
    bad_clusters = [c for c in result.clusters if any(r["poi_id"] == "bad" for r in c.rows)]
    assert len(bad_clusters) == 1
    assert len(bad_clusters[0].rows) == 1  # singleton, not merged


def test_review_candidate_reports_nearest_cluster() -> None:
    # Two lineage clusters; a same-token non-member ~50m from cluster B, far from A.
    rows = [
        _row(poi_id="a-rel", dedupe_key="osm:relation/1", name="Tudesque House",
             lon="-105.950", lat="35.690", quality_score="80",
             osm_member_refs="osm:way/10"),
        _row(poi_id="a-w", dedupe_key="osm:way/10", name="Tudesque House West",
             lon="-105.950", lat="35.690", quality_score="60",
             parent_relation_id="osm:relation/1"),
        _row(poi_id="b-rel", dedupe_key="osm:relation/2", name="Tudesque House",
             lon="-105.93903", lat="35.68416", quality_score="80",
             osm_member_refs="osm:way/20"),
        _row(poi_id="b-w", dedupe_key="osm:way/20", name="Tudesque House West",
             lon="-105.93903", lat="35.68416", quality_score="60",
             parent_relation_id="osm:relation/2"),
        # ~50m from cluster B (-105.93958,35.68416), >1km from cluster A.
        _row(poi_id="near", dedupe_key="osm:node/999", name="Tudesque Annex",
             lon="-105.93958", lat="35.68416", quality_score="40"),
    ]
    result = build_clusters(rows)
    near_candidates = [rc for rc in result.review_candidates if rc.candidate_poi_id == "near"]
    assert len(near_candidates) == 1
    assert near_candidates[0].cluster_survivor_poi_id in {"b-rel", "b-w"}
    assert near_candidates[0].distance_m < 60.0


def test_two_generic_house_rows_within_35m_do_not_merge() -> None:
    rows = [
        _row(poi_id="a", dedupe_key="osm:node/1", name="Adobe House",
             lon="-105.9390", lat="35.6841", quality_score="50"),
        _row(poi_id="b", dedupe_key="osm:node/2", name="Stone House",
             lon="-105.93902", lat="35.68411", quality_score="50"),
    ]
    result = build_clusters(rows)
    assert all(len(c.rows) == 1 for c in result.clusters)
