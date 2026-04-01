from poi_curator_domain.schemas import GeoLineString, NamedPoint, RouteSuggestRequest
from poi_curator_scoring.engine import suggest_places


def test_history_query_returns_history_first() -> None:
    result = suggest_places(
        RouteSuggestRequest(
            route_geometry=GeoLineString(
                coordinates=[[-105.94, 35.68], [-105.93, 35.67]],
            ),
            origin=NamedPoint(name="A", coordinates=[-105.94, 35.68]),
            destination=NamedPoint(name="B", coordinates=[-105.93, 35.67]),
            travel_mode="driving",
            category="history",
            max_detour_meters=1600,
            max_extra_minutes=8,
            region_hint="santa-fe",
            limit=3,
        )
    )

    assert result.results
    assert result.results[0].primary_category == "history"


def test_budget_filters_out_longer_detour_candidates() -> None:
    result = suggest_places(
        RouteSuggestRequest(
            route_geometry=GeoLineString(
                coordinates=[[-105.94, 35.68], [-105.93, 35.67]],
            ),
            origin=NamedPoint(name="A", coordinates=[-105.94, 35.68]),
            destination=NamedPoint(name="B", coordinates=[-105.93, 35.67]),
            travel_mode="walking",
            category="scenic",
            max_detour_meters=400,
            max_extra_minutes=4,
            region_hint="santa-fe",
            limit=5,
        )
    )

    assert result.results == []
