from poi_curator_editorial.feature_canonicalization import (
    Cluster,
    _identity_score,
    build_clusters,
    canonicalize,
    choose_display_name,
    haversine_m,
    merge_cluster,
    select_survivor,
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
                lon="-105.938944", lat="35.6841299", quality_score="62.5",
                claim_basis="state_register|historic_district")
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


def test_identity_score_stacks_historic_district_with_state_register() -> None:
    # Intentional: state_register (3) + historic (from historic_district, 1) = 4.
    assert _identity_score(_row(claim_basis="state_register|historic_district")) == 4
    # Bare state_register alone scores 3.
    assert _identity_score(_row(claim_basis="state_register")) == 3


def test_identity_score_credits_embedded_register_tokens() -> None:
    # Substring matching is intentional: embedded source tokens still count.
    assert _identity_score(_row(source_basis="osm_overpass|nrhp_listed_properties")) == 3
    assert _identity_score(_row(source_basis="osm_overpass|nm_hpd_register_workbook")) == 0


def test_identity_score_zero_when_no_identity_evidence() -> None:
    assert _identity_score(_row(claim_basis="wikidata_id", source_basis="osm_overpass")) == 0


def test_merge_cluster_produces_single_audited_row() -> None:
    clusters = build_clusters(_tudesque_rows()).clusters
    big = next(c for c in clusters if len(c.rows) > 1)
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
    again, _ = merge_cluster(Cluster(rows=[dict(merged_once)], reasons=set()))
    assert again["preferred_aliases"] == merged_once["preferred_aliases"]
    assert again["merged_from"] == ""  # singleton: nothing collapsed


def test_merge_cluster_handles_blank_coord_member() -> None:
    # A lineage member with empty coords must not crash the merge.
    rows = _tudesque_rows()
    for r in rows:
        if r["poi_id"] == "p-e":
            r["lon"] = ""
            r["lat"] = ""
    big = next(c for c in build_clusters(rows).clusters if len(c.rows) > 1)
    row, entry = merge_cluster(big)  # must not raise
    blank = next(d for d in entry["dropped"] if d["poi_id"] == "p-e")
    assert blank["distance_m"] is None


def test_merge_cluster_blank_coord_survivor_does_not_crash() -> None:
    # Survivor with blank coords: distances become None, no crash.
    rows = [
        _row(poi_id="s", dedupe_key="osm:relation/1", name="A",
             lon="", lat="", quality_score="90", osm_member_refs="osm:way/2"),
        _row(poi_id="m", dedupe_key="osm:way/2", name="A",
             lon="-105.9", lat="35.6", quality_score="50",
             parent_relation_id="osm:relation/1"),
    ]
    big = next(c for c in build_clusters(rows).clusters if len(c.rows) > 1)
    row, entry = merge_cluster(big)  # must not raise
    assert all(d["distance_m"] is None for d in entry["dropped"])


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
