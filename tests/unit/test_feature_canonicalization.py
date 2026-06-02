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


def test_haversine_identical_points_is_zero() -> None:
    assert haversine_m(-105.9, 35.6, -105.9, 35.6) == 0.0


def test_significant_tokens_empty_name_is_empty_set() -> None:
    assert significant_tokens("") == set()
