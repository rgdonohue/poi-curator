from pathlib import Path
from typing import Annotated, Literal, Protocol, cast

import orjson
from poi_curator_domain.schemas import (
    GeoLineString,
    LatLonPoint,
    NamedPoint,
    NearbyResult,
    NearbySuggestRequest,
    NearbySuggestResponse,
    PublicCategory,
    RouteResult,
    RouteSuggestRequest,
    RouteSuggestResponse,
    TravelMode,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session


class EvaluationExpectations(BaseModel):
    expected_empty: bool = False
    expected_any_names: list[str] = Field(default_factory=list)
    forbidden_names: list[str] = Field(default_factory=list)
    preferred_top_names: list[str] = Field(default_factory=list)
    min_results: int | None = Field(default=None, ge=0)
    max_results: int | None = Field(default=None, ge=0)


class BaseEvaluationCase(BaseModel):
    id: str
    label: str
    purpose: str
    category: str
    travel_mode: TravelMode
    region_hint: str | None = None
    limit: int = Field(default=5, ge=1, le=20)
    expectations: EvaluationExpectations = Field(default_factory=EvaluationExpectations)


class RouteEvaluationCase(BaseEvaluationCase):
    mode: Literal["route"] = "route"
    route_geometry: GeoLineString
    origin: NamedPoint
    destination: NamedPoint
    max_detour_meters: int = Field(gt=0)
    max_extra_minutes: int = Field(gt=0)

    def to_request(self) -> RouteSuggestRequest:
        return RouteSuggestRequest(
            route_geometry=self.route_geometry,
            origin=self.origin,
            destination=self.destination,
            travel_mode=self.travel_mode,
            category=cast(PublicCategory, self.category),
            max_detour_meters=self.max_detour_meters,
            max_extra_minutes=self.max_extra_minutes,
            region_hint=self.region_hint,
            limit=self.limit,
        )


class NearbyEvaluationCase(BaseEvaluationCase):
    mode: Literal["nearby"] = "nearby"
    center: LatLonPoint
    radius_meters: int = Field(gt=0)

    def to_request(self) -> NearbySuggestRequest:
        return NearbySuggestRequest(
            center=self.center,
            travel_mode=self.travel_mode,
            category=cast(PublicCategory, self.category),
            radius_meters=self.radius_meters,
            region_hint=self.region_hint,
            limit=self.limit,
        )


EvaluationCase = Annotated[
    RouteEvaluationCase | NearbyEvaluationCase,
    Field(discriminator="mode"),
]


class EvaluationFixtureSet(BaseModel):
    cases: list[EvaluationCase]


class EvaluatedResult(BaseModel):
    name: str
    score: float
    primary_category: str
    category_match_type: str | None
    short_description: str
    distance_label: str
    score_breakdown: dict[str, float] | None


class EvaluationCaseResult(BaseModel):
    case_id: str
    label: str
    mode: Literal["route", "nearby"]
    purpose: str
    passed: bool
    result_count: int
    query_summary: dict[str, object]
    matched_expected_names: list[str]
    violated_forbidden_names: list[str]
    top_result_names: list[str]
    soft_warnings: list[str]
    notes: list[str]
    results: list[EvaluatedResult]


class EvaluationSummary(BaseModel):
    fixture_count: int
    passed_count: int
    failed_count: int
    results: list[EvaluationCaseResult]


class CombinedSuggestBackend(Protocol):
    def suggest_places(self, db: Session, payload: RouteSuggestRequest) -> RouteSuggestResponse:
        ...

    def suggest_nearby_places(
        self,
        db: Session,
        payload: NearbySuggestRequest,
    ) -> NearbySuggestResponse:
        ...


class RouteFixture(BaseModel):
    name: str
    description: str
    request: RouteSuggestRequest
    expected_non_empty: bool = True
    expected_any_names: list[str] = Field(default_factory=list)
    forbidden_names: list[str] = Field(default_factory=list)


class RouteFixtureSet(BaseModel):
    fixtures: list[RouteFixture]


class RouteEvaluationResult(BaseModel):
    fixture_name: str
    passed: bool
    result_count: int
    expected_non_empty: bool
    matched_expected_names: list[str]
    violated_forbidden_names: list[str]
    top_result_names: list[str]
    notes: list[str]
    results: list[EvaluatedResult]


class RouteEvaluationSummary(BaseModel):
    fixture_count: int
    passed_count: int
    failed_count: int
    results: list[RouteEvaluationResult]


def load_evaluation_cases(path: Path) -> list[EvaluationCase]:
    payload = orjson.loads(path.read_bytes())
    return EvaluationFixtureSet.model_validate(payload).cases


def evaluate_cases(
    backend: CombinedSuggestBackend,
    db: Session,
    cases: list[EvaluationCase],
) -> EvaluationSummary:
    results = [evaluate_case(backend, db, case) for case in cases]
    passed_count = sum(1 for result in results if result.passed)
    return EvaluationSummary(
        fixture_count=len(cases),
        passed_count=passed_count,
        failed_count=len(cases) - passed_count,
        results=results,
    )


def evaluate_case(
    backend: CombinedSuggestBackend,
    db: Session,
    case: EvaluationCase,
) -> EvaluationCaseResult:
    results: list[RouteResult | NearbyResult]
    query_summary: dict[str, object]
    if case.mode == "route":
        route_response = backend.suggest_places(db, case.to_request())
        results = list(route_response.results)
        query_summary = route_response.query_summary.model_dump()
    else:
        nearby_response = backend.suggest_nearby_places(db, case.to_request())
        results = list(nearby_response.results)
        query_summary = nearby_response.query_summary.model_dump()
    names = [result.name for result in results]
    matched_expected_names = [
        name for name in case.expectations.expected_any_names if name in names
    ]
    violated_forbidden_names = [
        name for name in case.expectations.forbidden_names if name in names
    ]
    soft_warnings = _evaluate_soft_preferences(case.expectations.preferred_top_names, names)
    notes = _evaluate_hard_expectations(
        case.expectations,
        names,
        len(results),
        matched_expected_names,
        violated_forbidden_names,
    )
    passed = not notes

    return EvaluationCaseResult(
        case_id=case.id,
        label=case.label,
        mode=case.mode,
        purpose=case.purpose,
        passed=passed,
        result_count=len(results),
        query_summary=query_summary,
        matched_expected_names=matched_expected_names,
        violated_forbidden_names=violated_forbidden_names,
        top_result_names=names,
        soft_warnings=soft_warnings,
        notes=notes,
        results=[_evaluated_result_from_output(result) for result in results],
    )


def write_evaluation_report(
    path: Path,
    summary: EvaluationSummary | RouteEvaluationSummary,
) -> None:
    if path.suffix.lower() == ".md":
        if isinstance(summary, RouteEvaluationSummary):
            path.write_text(render_markdown_report(summary), encoding="utf-8")
        else:
            path.write_text(render_combined_markdown_report(summary), encoding="utf-8")
        return
    path.write_bytes(orjson.dumps(summary.model_dump(), option=orjson.OPT_INDENT_2))


def render_combined_markdown_report(summary: EvaluationSummary) -> str:
    lines = [
        "# Santa Fe Evaluation Report",
        "",
        f"- Cases: {summary.fixture_count}",
        f"- Passed: {summary.passed_count}",
        f"- Failed: {summary.failed_count}",
        "",
    ]
    for result in summary.results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"## {status} {result.case_id} · {result.label}")
        lines.append(f"- Mode: {result.mode}")
        lines.append(f"- Purpose: {result.purpose}")
        lines.append(f"- Query: {_format_query_summary(result.query_summary)}")
        lines.append(f"- Result count: {result.result_count}")
        if result.matched_expected_names:
            lines.append(f"- Matched expected: {', '.join(result.matched_expected_names)}")
        if result.violated_forbidden_names:
            lines.append(f"- Violated forbidden: {', '.join(result.violated_forbidden_names)}")
        for warning in result.soft_warnings:
            lines.append(f"- Soft warning: {warning}")
        for note in result.notes:
            lines.append(f"- Note: {note}")
        if result.results:
            lines.append("- Results:")
            for ranked in result.results[:5]:
                lines.append(
                    f"  - {ranked.name} ({ranked.primary_category}) "
                    f"match={ranked.category_match_type} score={ranked.score} "
                    f"{ranked.distance_label}"
                )
                lines.append(f"    summary: {ranked.short_description}")
                if ranked.score_breakdown:
                    lines.append(
                        f"    breakdown: {_format_score_breakdown_excerpt(ranked.score_breakdown)}"
                    )
        else:
            lines.append("- Results: none")
        lines.append("")
    return "\n".join(lines)


def load_route_fixtures(path: Path) -> list[RouteFixture]:
    payload = orjson.loads(path.read_bytes())
    return RouteFixtureSet.model_validate(payload).fixtures


def evaluate_route_fixtures(
    backend: CombinedSuggestBackend,
    db: Session,
    fixtures: list[RouteFixture],
) -> RouteEvaluationSummary:
    results = [evaluate_route_fixture(backend, db, fixture) for fixture in fixtures]
    passed_count = sum(1 for result in results if result.passed)
    return RouteEvaluationSummary(
        fixture_count=len(fixtures),
        passed_count=passed_count,
        failed_count=len(fixtures) - passed_count,
        results=results,
    )


def evaluate_route_fixture(
    backend: CombinedSuggestBackend,
    db: Session,
    fixture: RouteFixture,
) -> RouteEvaluationResult:
    case = RouteEvaluationCase(
        id=fixture.name.lower().replace(" ", "-"),
        label=fixture.name,
        purpose=fixture.description,
        mode="route",
        category=fixture.request.category,
        travel_mode=fixture.request.travel_mode,
        region_hint=fixture.request.region_hint,
        limit=fixture.request.limit,
        route_geometry=fixture.request.route_geometry,
        origin=fixture.request.origin,
        destination=fixture.request.destination,
        max_detour_meters=fixture.request.max_detour_meters,
        max_extra_minutes=fixture.request.max_extra_minutes,
        expectations=EvaluationExpectations(
            expected_empty=not fixture.expected_non_empty,
            expected_any_names=fixture.expected_any_names,
            forbidden_names=fixture.forbidden_names,
        ),
    )
    result = evaluate_case(backend, db, case)
    return RouteEvaluationResult(
        fixture_name=fixture.name,
        passed=result.passed,
        result_count=result.result_count,
        expected_non_empty=fixture.expected_non_empty,
        matched_expected_names=result.matched_expected_names,
        violated_forbidden_names=result.violated_forbidden_names,
        top_result_names=result.top_result_names,
        notes=result.notes,
        results=result.results,
    )


def render_markdown_report(summary: RouteEvaluationSummary) -> str:
    lines = [
        "# Route Evaluation Report",
        "",
        f"- Fixtures: {summary.fixture_count}",
        f"- Passed: {summary.passed_count}",
        f"- Failed: {summary.failed_count}",
        "",
    ]
    for result in summary.results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"## {status} {result.fixture_name}")
        lines.append(f"- Result count: {result.result_count}")
        if result.matched_expected_names:
            lines.append(f"- Matched expected: {', '.join(result.matched_expected_names)}")
        if result.violated_forbidden_names:
            lines.append(f"- Violated forbidden: {', '.join(result.violated_forbidden_names)}")
        for note in result.notes:
            lines.append(f"- Note: {note}")
        if result.results:
            lines.append("- Top results:")
            for ranked in result.results[:5]:
                lines.append(
                    f"  - {ranked.name} ({ranked.primary_category}) "
                    f"match={ranked.category_match_type} "
                    f"score={ranked.score} {ranked.distance_label}"
                )
                if ranked.score_breakdown:
                    lines.append(
                        f"    breakdown: {_format_score_breakdown_excerpt(ranked.score_breakdown)}"
                    )
        lines.append("")
    return "\n".join(lines)


def _evaluate_hard_expectations(
    expectations: EvaluationExpectations,
    names: list[str],
    result_count: int,
    matched_expected_names: list[str],
    violated_forbidden_names: list[str],
) -> list[str]:
    notes: list[str] = []
    if expectations.expected_empty and result_count > 0:
        notes.append("Expected empty result set but got results.")
    if not expectations.expected_empty and result_count == 0:
        notes.append("Expected non-empty result set but got none.")
    if expectations.expected_any_names and not matched_expected_names:
        notes.append("None of the expected candidate names appeared in the result set.")
    if violated_forbidden_names:
        notes.append("Forbidden candidate appeared in the result set.")
    if expectations.min_results is not None and result_count < expectations.min_results:
        notes.append(
            f"Expected at least {expectations.min_results} results but got {result_count}."
        )
    if expectations.max_results is not None and result_count > expectations.max_results:
        notes.append(
            f"Expected at most {expectations.max_results} results but got {result_count}."
        )
    return notes


def _evaluate_soft_preferences(preferred_top_names: list[str], names: list[str]) -> list[str]:
    if not preferred_top_names or not names:
        return []
    if any(name in names[:3] for name in preferred_top_names):
        return []
    return ["None of the preferred top names appeared in the top 3 results."]


def _query_summary_for_case(case: EvaluationCase) -> dict[str, object]:
    summary: dict[str, object] = {
        "category": case.category,
        "travel_mode": case.travel_mode,
        "region_hint": case.region_hint,
        "limit": case.limit,
    }
    if case.mode == "route":
        summary["max_detour_meters"] = case.max_detour_meters
        summary["max_extra_minutes"] = case.max_extra_minutes
    else:
        summary["radius_meters"] = case.radius_meters
    return summary


def _evaluated_result_from_output(result: RouteResult | NearbyResult) -> EvaluatedResult:
    if isinstance(result, RouteResult):
        distance_label = (
            f"distance_from_route_m={result.distance_from_route_m} "
            f"detour_m={result.estimated_detour_m} extra_min={result.estimated_extra_minutes}"
        )
    else:
        distance_label = (
            f"distance_from_center_m={result.distance_from_center_meters} "
            f"access_min={result.estimated_access_minutes}"
        )
    return EvaluatedResult(
        name=result.name,
        score=result.score,
        primary_category=result.primary_category,
        category_match_type=result.category_match_type,
        short_description=result.short_description,
        distance_label=distance_label,
        score_breakdown=result.score_breakdown,
    )


def _format_score_breakdown_excerpt(score_breakdown: dict[str, float]) -> str:
    items = [item for item in score_breakdown.items() if abs(item[1]) >= 0.5]
    return ", ".join(f"{key}={value:.1f}" for key, value in items[:6])


def _format_query_summary(summary: dict[str, object]) -> str:
    return ", ".join(f"{key}={value}" for key, value in summary.items() if value is not None)
