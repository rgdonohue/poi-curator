from pathlib import Path
from typing import Protocol

import orjson
from poi_curator_domain.schemas import RouteSuggestRequest, RouteSuggestResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session


class RouteFixture(BaseModel):
    name: str
    description: str
    request: RouteSuggestRequest
    expected_non_empty: bool = True
    expected_any_names: list[str] = Field(default_factory=list)
    forbidden_names: list[str] = Field(default_factory=list)


class RouteFixtureSet(BaseModel):
    fixtures: list[RouteFixture]


class EvaluatedResult(BaseModel):
    name: str
    score: float
    primary_category: str
    category_match_type: str | None
    distance_from_route_m: int
    estimated_detour_m: int
    estimated_extra_minutes: int
    score_breakdown: dict[str, float] | None


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


class RouteSuggestBackend(Protocol):
    def suggest_places(self, db: Session, payload: RouteSuggestRequest) -> RouteSuggestResponse:
        ...


def load_route_fixtures(path: Path) -> list[RouteFixture]:
    payload = orjson.loads(path.read_bytes())
    return RouteFixtureSet.model_validate(payload).fixtures


def evaluate_route_fixtures(
    backend: RouteSuggestBackend,
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
    backend: RouteSuggestBackend,
    db: Session,
    fixture: RouteFixture,
) -> RouteEvaluationResult:
    response = backend.suggest_places(db, fixture.request)
    top_result_names = [result.name for result in response.results]
    matched_expected_names = [
        name for name in fixture.expected_any_names if name in top_result_names
    ]
    violated_forbidden_names = [
        name for name in fixture.forbidden_names if name in top_result_names
    ]

    notes: list[str] = []
    passed = True
    if fixture.expected_non_empty and not response.results:
        notes.append("Expected non-empty result set but got none.")
        passed = False
    if not fixture.expected_non_empty and response.results:
        notes.append("Expected empty result set but got results.")
        passed = False
    if fixture.expected_any_names and not matched_expected_names:
        notes.append("None of the expected candidate names appeared in the result set.")
        passed = False
    if violated_forbidden_names:
        notes.append("Forbidden candidate appeared in the result set.")
        passed = False

    return RouteEvaluationResult(
        fixture_name=fixture.name,
        passed=passed,
        result_count=len(response.results),
        expected_non_empty=fixture.expected_non_empty,
        matched_expected_names=matched_expected_names,
        violated_forbidden_names=violated_forbidden_names,
        top_result_names=top_result_names,
        notes=notes,
        results=[
            EvaluatedResult(
                name=result.name,
                score=result.score,
                primary_category=result.primary_category,
                category_match_type=result.category_match_type,
                distance_from_route_m=result.distance_from_route_m,
                estimated_detour_m=result.estimated_detour_m,
                estimated_extra_minutes=result.estimated_extra_minutes,
                score_breakdown=result.score_breakdown,
            )
            for result in response.results
        ],
    )


def write_evaluation_report(path: Path, summary: RouteEvaluationSummary) -> None:
    if path.suffix.lower() == ".md":
        path.write_text(render_markdown_report(summary), encoding="utf-8")
        return
    path.write_bytes(orjson.dumps(summary.model_dump(), option=orjson.OPT_INDENT_2))


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
                    f"score={ranked.score} detour_m={ranked.estimated_detour_m} "
                    f"extra_min={ranked.estimated_extra_minutes}"
                )
                if ranked.score_breakdown:
                    breakdown = ", ".join(
                        f"{key}={value:.2f}" for key, value in ranked.score_breakdown.items()
                    )
                    lines.append(f"    breakdown: {breakdown}")
        lines.append("")
    return "\n".join(lines)
