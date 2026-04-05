from poi_curator_domain.schemas import LatLonPoint, NearbySuggestRequest
from poi_curator_scoring.engine import suggest_nearby_places


def test_fixture_nearby_history_prefers_primary_match_near_plaza() -> None:
    response = suggest_nearby_places(
        NearbySuggestRequest(
            center=LatLonPoint(lat=35.6828, lon=-105.9319),
            travel_mode="walking",
            category="history",
            radius_meters=500,
            region_hint="santa-fe",
            limit=3,
        )
    )

    assert response.results
    assert response.results[0].name == "Acequia Madre"
    assert response.results[0].category_match_type == "primary"


def test_fixture_nearby_scenic_can_be_empty_for_tiny_radius() -> None:
    response = suggest_nearby_places(
        NearbySuggestRequest(
            center=LatLonPoint(lat=35.6870, lon=-105.9378),
            travel_mode="walking",
            category="scenic",
            radius_meters=50,
            region_hint="santa-fe",
            limit=5,
        )
    )

    assert response.results == []
