from pathlib import Path
from typing import cast

from poi_curator_domain.schemas import (
    NearbyQuerySummary,
    NearbyResult,
    NearbySuggestResponse,
    QuerySummary,
    RouteResult,
    RouteSuggestResponse,
)
from poi_curator_scoring.evaluation import (
    EvaluationExpectations,
    EvaluationSummary,
    RouteEvaluationSummary,
    evaluate_case,
    evaluate_route_fixture,
    load_evaluation_cases,
    load_route_fixtures,
    render_combined_markdown_report,
    render_markdown_report,
)
from sqlalchemy.orm import Session


class FakeBackend:
    def __init__(
        self,
        *,
        route_response: RouteSuggestResponse | None = None,
        nearby_response: NearbySuggestResponse | None = None,
    ) -> None:
        self.route_response = route_response
        self.nearby_response = nearby_response

    def suggest_places(self, db: object, payload: object) -> RouteSuggestResponse:
        del db, payload
        if self.route_response is None:
            raise AssertionError("Route response was not configured.")
        return self.route_response

    def suggest_nearby_places(self, db: object, payload: object) -> NearbySuggestResponse:
        del db, payload
        if self.nearby_response is None:
            raise AssertionError("Nearby response was not configured.")
        return self.nearby_response


def test_load_combined_evaluation_cases() -> None:
    cases = load_evaluation_cases(Path("data/fixtures/eval_santa_fe.json"))

    assert len(cases) >= 8
    assert any(case.mode == "route" for case in cases)
    assert any(case.mode == "nearby" for case in cases)
    assert any(case.id == "nearby-plaza-history" for case in cases)


def test_evaluate_route_case_passes_on_expected_match() -> None:
    cases = load_evaluation_cases(Path("data/fixtures/eval_santa_fe.json"))
    route_case = next(
        case for case in cases if case.id == "route-historic-center-driving"
    ).model_copy(
        update={
            "expectations": EvaluationExpectations(
                expected_empty=False,
                expected_any_names=["De Vargas Street House"],
                forbidden_names=["Bad Result"],
            )
        },
    )
    response = RouteSuggestResponse(
        query_summary=QuerySummary(
            travel_mode="driving",
            category="history",
            max_detour_meters=1800,
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
                score_breakdown={"route_proximity": 10.0, "significance": 20.0},
                why_it_matters=["good"],
                badges=["history"],
            )
        ],
    )

    result = evaluate_case(
        FakeBackend(route_response=response),
        cast(Session, object()),
        route_case,
    )

    assert result.passed is True
    assert result.matched_expected_names == ["De Vargas Street House"]
    assert result.mode == "route"


def test_evaluate_nearby_case_dispatches_and_flags_soft_preference() -> None:
    cases = load_evaluation_cases(Path("data/fixtures/eval_santa_fe.json"))
    nearby_case = next(case for case in cases if case.id == "nearby-plaza-history")
    response = NearbySuggestResponse(
        query_summary=NearbyQuerySummary(
            travel_mode="walking",
            category="history",
            radius_meters=800,
            limit=5,
        ),
        results=[
            NearbyResult(
                poi_id="2",
                name="Museum of Contemporary Native Arts",
                primary_category="history",
                secondary_categories=[],
                category_match_type="primary",
                coordinates=[-105.93, 35.68],
                short_description="desc",
                distance_from_center_meters=80,
                estimated_access_m=80,
                estimated_access_minutes=1,
                score=79.0,
                score_breakdown={"point_proximity": 16.0, "significance": 20.0},
                why_it_matters=["good"],
                badges=["history"],
            )
        ],
    )

    result = evaluate_case(
        FakeBackend(nearby_response=response),
        cast(Session, object()),
        nearby_case,
    )

    assert result.passed is False
    assert result.mode == "nearby"
    assert "None of the expected candidate names appeared in the result set." in result.notes
    assert "None of the preferred top names appeared in the top 3 results." in result.soft_warnings


def test_render_combined_markdown_report_contains_mode_and_purpose() -> None:
    cases = load_evaluation_cases(Path("data/fixtures/eval_santa_fe.json"))
    nearby_case = next(case for case in cases if case.id == "nearby-downtown-scenic-empty")
    response = NearbySuggestResponse(
        query_summary=NearbyQuerySummary(
            travel_mode="walking",
            category="scenic",
            radius_meters=350,
            limit=5,
        ),
        results=[],
    )
    result = evaluate_case(
        FakeBackend(nearby_response=response),
        cast(Session, object()),
        nearby_case,
    )

    report = render_combined_markdown_report(
        EvaluationSummary(
            fixture_count=1,
            passed_count=1,
            failed_count=0,
            results=[result],
        )
    )

    assert "PASS nearby-downtown-scenic-empty" in report
    assert "Mode: nearby" in report
    assert "Purpose: Protect honest empty behavior" in report


def test_legacy_route_fixture_loader_and_report_still_work() -> None:
    fixtures = load_route_fixtures(Path("data/fixtures/routes_santa_fe.json"))
    assert len(fixtures) >= 5

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
    result = evaluate_route_fixture(
        FakeBackend(route_response=response),
        cast(Session, object()),
        fixtures[0],
    )
    report = render_markdown_report(
        RouteEvaluationSummary(
            fixture_count=1,
            passed_count=1,
            failed_count=0,
            results=[result],
        )
    )

    assert result.passed is True
    assert "PASS Historic Center Driving" in report
