from pathlib import Path
from typing import cast

from poi_curator_domain.schemas import QuerySummary, RouteResult, RouteSuggestResponse
from poi_curator_scoring.evaluation import (
    RouteEvaluationSummary,
    RouteFixture,
    evaluate_route_fixture,
    load_route_fixtures,
    render_markdown_report,
)
from sqlalchemy.orm import Session


class FakeBackend:
    def __init__(self, response: RouteSuggestResponse) -> None:
        self.response = response

    def suggest_places(self, db: object, payload: object) -> RouteSuggestResponse:
        del db, payload
        return self.response


def test_load_route_fixtures() -> None:
    fixtures = load_route_fixtures(Path("data/fixtures/routes_santa_fe.json"))

    assert len(fixtures) >= 5
    assert fixtures[0].name == "Historic Center Driving"


def test_evaluate_route_fixture_passes_on_expected_match() -> None:
    fixture = RouteFixture.model_validate(
        {
            "name": "Test Route",
            "description": "desc",
            "request": {
                "route_geometry": {
                    "type": "LineString",
                    "coordinates": [[-105.94, 35.68], [-105.93, 35.67]],
                },
                "origin": {"name": "A", "coordinates": [-105.94, 35.68]},
                "destination": {"name": "B", "coordinates": [-105.93, 35.67]},
                "travel_mode": "driving",
                "category": "history",
                "max_detour_meters": 1600,
                "max_extra_minutes": 8,
                "region_hint": "santa-fe",
                "limit": 5,
            },
            "expected_non_empty": True,
            "expected_any_names": ["De Vargas Street House"],
            "forbidden_names": ["Bad Result"],
        }
    )
    response = RouteSuggestResponse(
        query_summary=QuerySummary(
            travel_mode="driving",
            category="history",
            max_detour_meters=1600,
            limit=5,
        ),
        results=[
            RouteResult(
                poi_id="1",
                name="De Vargas Street House",
                primary_category="history",
                secondary_categories=[],
                category_match_type="primary",
                coordinates=[-105.93, 35.68],
                short_description="desc",
                distance_from_route_m=100,
                estimated_detour_m=200,
                estimated_extra_minutes=1,
                score=80.0,
                score_breakdown={"route_proximity": 10.0},
                why_it_matters=["good"],
                badges=["history"],
            )
        ],
    )

    result = evaluate_route_fixture(FakeBackend(response), cast(Session, object()), fixture)

    assert result.passed is True
    assert result.matched_expected_names == ["De Vargas Street House"]


def test_render_markdown_report_contains_status_lines() -> None:
    fixture = RouteFixture.model_validate(
        {
            "name": "Empty Route",
            "description": "desc",
            "request": {
                "route_geometry": {
                    "type": "LineString",
                    "coordinates": [[-105.94, 35.68], [-105.93, 35.67]],
                },
                "origin": {"name": "A", "coordinates": [-105.94, 35.68]},
                "destination": {"name": "B", "coordinates": [-105.93, 35.67]},
                "travel_mode": "driving",
                "category": "scenic",
                "max_detour_meters": 1600,
                "max_extra_minutes": 8,
                "region_hint": "santa-fe",
                "limit": 5,
            },
            "expected_non_empty": False,
            "expected_any_names": [],
            "forbidden_names": [],
        }
    )
    response = RouteSuggestResponse(
        query_summary=QuerySummary(
            travel_mode="driving",
            category="scenic",
            max_detour_meters=1600,
            limit=5,
        ),
        results=[],
    )
    result = evaluate_route_fixture(FakeBackend(response), cast(Session, object()), fixture)

    report = render_markdown_report(
        RouteEvaluationSummary(
            fixture_count=1,
            passed_count=1,
            failed_count=0,
            results=[result],
        )
    )

    assert "PASS Empty Route" in report
