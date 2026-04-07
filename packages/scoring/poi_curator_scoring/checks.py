from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from poi_curator_scoring.evaluation import (
    EvaluatedResult,
    EvaluationCase,
    EvaluationCaseResult,
    NearbyEvaluationCase,
    RouteEvaluationCase,
    _format_query_summary,
    _format_score_breakdown_excerpt,
    evaluate_case,
    load_evaluation_cases,
)

DEFAULT_FIXTURES_PATH = Path("data/fixtures/eval_santa_fe.json")
DEFAULT_REVIEW_DIR = Path("reports/reviews")


class CheckRun(BaseModel):
    case_id: str
    label: str
    mode: str
    purpose: str
    category: str
    theme: str | None = None
    travel_mode: str
    region_hint: str | None = None
    limit: int
    expectation_based: bool = True
    passed: bool | None = None
    result_count: int
    query_summary: dict[str, object]
    request_payload: dict[str, Any]
    matched_expected_names: list[str] = Field(default_factory=list)
    violated_forbidden_names: list[str] = Field(default_factory=list)
    top_result_names: list[str] = Field(default_factory=list)
    soft_warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    results: list[EvaluatedResult] = Field(default_factory=list)


class CheckReport(BaseModel):
    generated_at: datetime
    fixtures_path: str | None = None
    run_count: int
    passed_count: int | None = None
    failed_count: int | None = None
    runs: list[CheckRun]


class ReviewArtifact(BaseModel):
    case_id: str
    label: str
    mode: str
    category: str
    theme: str | None = None
    timestamp: datetime
    reviewer: str
    verdict: str
    note: str | None = None
    query_summary: dict[str, object]
    top_returned_names: list[str] = Field(default_factory=list)
    fixtures_path: str | None = None


def load_named_cases(
    fixtures: Path,
    requested_ids: Sequence[str] | None = None,
) -> list[EvaluationCase]:
    cases = load_evaluation_cases(fixtures)
    if not requested_ids:
        return cases

    indexed = {case.id: case for case in cases}
    missing = [case_id for case_id in requested_ids if case_id not in indexed]
    if missing:
        raise KeyError(", ".join(missing))
    return [indexed[case_id] for case_id in requested_ids]


def build_inline_nearby_case(
    *,
    lat: float,
    lon: float,
    radius_meters: int,
    category: str,
    travel_mode: str,
    theme: str | None,
    region_hint: str | None,
    limit: int,
    label: str | None = None,
) -> NearbyEvaluationCase:
    resolved_label = label or "Inline Nearby Check"
    return NearbyEvaluationCase(
        id=_slugify_case_id("inline-nearby", label),
        label=resolved_label,
        purpose="Inline nearby check from the CLI.",
        category=category,
        theme=theme,
        travel_mode=travel_mode,
        region_hint=region_hint,
        limit=limit,
        center={"lat": lat, "lon": lon},
        radius_meters=radius_meters,
    )


def build_inline_route_case(
    *,
    coordinates: Sequence[tuple[float, float]],
    category: str,
    travel_mode: str,
    theme: str | None,
    region_hint: str | None,
    limit: int,
    max_detour_meters: int,
    max_extra_minutes: int,
    origin_name: str,
    destination_name: str,
    label: str | None = None,
) -> RouteEvaluationCase:
    resolved_label = label or "Inline Route Check"
    return RouteEvaluationCase(
        id=_slugify_case_id("inline-route", label),
        label=resolved_label,
        purpose="Inline route check from the CLI.",
        category=category,
        theme=theme,
        travel_mode=travel_mode,
        region_hint=region_hint,
        limit=limit,
        route_geometry={
            "type": "LineString",
            "coordinates": [[lon, lat] for lon, lat in coordinates],
        },
        origin={"name": origin_name, "coordinates": list(coordinates[0])},
        destination={"name": destination_name, "coordinates": list(coordinates[-1])},
        max_detour_meters=max_detour_meters,
        max_extra_minutes=max_extra_minutes,
    )


def run_check_case(
    backend: object,
    db: Session,
    case: EvaluationCase,
    *,
    expectation_based: bool,
) -> CheckRun:
    result = evaluate_case(backend, db, case)
    return _run_from_evaluation_result(
        case=case,
        result=result,
        expectation_based=expectation_based,
    )


def build_report(
    runs: Sequence[CheckRun],
    *,
    fixtures_path: Path | None = None,
) -> CheckReport:
    expectation_runs = [run for run in runs if run.passed is not None]
    return CheckReport(
        generated_at=datetime.now(UTC),
        fixtures_path=str(fixtures_path) if fixtures_path is not None else None,
        run_count=len(runs),
        passed_count=sum(1 for run in expectation_runs if run.passed) if expectation_runs else None,
        failed_count=(
            sum(1 for run in expectation_runs if run.passed is False) if expectation_runs else None
        ),
        runs=list(runs),
    )


def build_review_artifact(
    run: CheckRun,
    *,
    verdict: str,
    reviewer: str,
    note: str | None,
    fixtures_path: Path | None = None,
) -> ReviewArtifact:
    return ReviewArtifact(
        case_id=run.case_id,
        label=run.label,
        mode=run.mode,
        category=run.category,
        theme=run.theme,
        timestamp=datetime.now(UTC),
        reviewer=reviewer,
        verdict=verdict,
        note=note,
        query_summary=run.query_summary,
        top_returned_names=run.top_result_names[:5],
        fixtures_path=str(fixtures_path) if fixtures_path is not None else None,
    )


def render_terminal_run(run: CheckRun, *, verbose: bool = False) -> str:
    status = "RUN"
    if run.passed is True:
        status = "PASS"
    elif run.passed is False:
        status = "FAIL"

    meta = [
        f"mode={run.mode}",
        f"category={run.category}",
        f"travel_mode={run.travel_mode}",
    ]
    if run.theme is not None:
        meta.append(f"theme={run.theme}")
    if run.region_hint is not None:
        meta.append(f"region_hint={run.region_hint}")

    lines = [
        f"{status} {run.case_id} · {run.label}",
        " ".join(meta),
        f"query={_format_query_summary(run.query_summary)}",
        f"results={run.result_count}",
    ]
    if run.matched_expected_names:
        lines.append(f"matched_expected={', '.join(run.matched_expected_names)}")
    if run.violated_forbidden_names:
        lines.append(f"violated_forbidden={', '.join(run.violated_forbidden_names)}")
    for warning in run.soft_warnings:
        lines.append(f"warning={warning}")
    for note in run.notes:
        lines.append(f"note={note}")

    if not run.results:
        lines.append("returned=none")
        return "\n".join(lines)

    for index, ranked in enumerate(run.results, start=1):
        match = ranked.category_match_type or "n/a"
        lines.append(
            f"{index}. {ranked.name} | score={ranked.score:.1f} | "
            f"{ranked.primary_category} | match={match}"
        )
        lines.append(f"   summary={ranked.short_description}")
        if ranked.score_breakdown:
            breakdown = (
                _format_full_score_breakdown(ranked.score_breakdown)
                if verbose
                else _format_score_breakdown_excerpt(ranked.score_breakdown)
            )
            lines.append(f"   breakdown={breakdown or 'n/a'}")
    return "\n".join(lines)


def render_report_markdown(report: CheckReport, *, verbose: bool = False) -> str:
    lines = [
        "# POI Curator Check Report",
        "",
        f"- Generated: {report.generated_at.isoformat()}",
        f"- Runs: {report.run_count}",
    ]
    if report.fixtures_path is not None:
        lines.append(f"- Fixtures: {report.fixtures_path}")
    if report.passed_count is not None and report.failed_count is not None:
        lines.append(f"- Passed: {report.passed_count}")
        lines.append(f"- Failed: {report.failed_count}")
    lines.append("")

    for run in report.runs:
        status = "RUN"
        if run.passed is True:
            status = "PASS"
        elif run.passed is False:
            status = "FAIL"
        lines.append(f"## {status} {run.case_id} · {run.label}")
        lines.append(f"- Mode: {run.mode}")
        lines.append(f"- Category: {run.category}")
        lines.append(f"- Travel mode: {run.travel_mode}")
        if run.theme is not None:
            lines.append(f"- Theme: {run.theme}")
        lines.append(f"- Query: {_format_query_summary(run.query_summary)}")
        lines.append(f"- Result count: {run.result_count}")
        for warning in run.soft_warnings:
            lines.append(f"- Warning: {warning}")
        for note in run.notes:
            lines.append(f"- Note: {note}")
        if run.results:
            lines.append("- Results:")
            for ranked in run.results:
                lines.append(
                    f"  - {ranked.name} ({ranked.primary_category}) "
                    f"match={ranked.category_match_type} score={ranked.score:.1f}"
                )
                lines.append(f"    summary: {ranked.short_description}")
                if ranked.score_breakdown:
                    breakdown = (
                        _format_full_score_breakdown(ranked.score_breakdown)
                        if verbose
                        else _format_score_breakdown_excerpt(ranked.score_breakdown)
                    )
                    lines.append(f"    breakdown: {breakdown or 'n/a'}")
        else:
            lines.append("- Results: none")
        lines.append("")
    return "\n".join(lines)


def render_review_markdown(review: ReviewArtifact) -> str:
    lines = [
        f"# Review {review.case_id}",
        "",
        f"- Timestamp: {review.timestamp.isoformat()}",
        f"- Reviewer: {review.reviewer}",
        f"- Verdict: {review.verdict}",
        f"- Label: {review.label}",
        f"- Mode: {review.mode}",
        f"- Category: {review.category}",
    ]
    if review.theme is not None:
        lines.append(f"- Theme: {review.theme}")
    lines.append(f"- Query: {_format_query_summary(review.query_summary)}")
    if review.note:
        lines.append(f"- Note: {review.note}")
    if review.top_returned_names:
        lines.append(f"- Top returned names: {', '.join(review.top_returned_names)}")
    else:
        lines.append("- Top returned names: none")
    return "\n".join(lines)


def write_report_files(
    report: CheckReport,
    *,
    json_out: Path | None = None,
    md_out: Path | None = None,
    verbose_markdown: bool = False,
) -> list[Path]:
    written: list[Path] = []
    if json_out is not None:
        _write_json(json_out, report.model_dump(mode="json"))
        written.append(json_out)
    if md_out is not None:
        _write_text(md_out, render_report_markdown(report, verbose=verbose_markdown))
        written.append(md_out)
    return written


def write_review_files(
    review: ReviewArtifact,
    *,
    review_dir: Path = DEFAULT_REVIEW_DIR,
    json_out: Path | None = None,
    md_out: Path | None = None,
) -> list[Path]:
    written: list[Path] = []
    resolved_json_out = json_out
    if resolved_json_out is None and md_out is None:
        resolved_json_out = _default_review_output_path(review, review_dir, suffix=".json")

    if resolved_json_out is not None:
        _write_json(resolved_json_out, review.model_dump(mode="json"))
        written.append(resolved_json_out)
    if md_out is not None:
        _write_text(md_out, render_review_markdown(review))
        written.append(md_out)
    return written


def _run_from_evaluation_result(
    *,
    case: EvaluationCase,
    result: EvaluationCaseResult,
    expectation_based: bool,
) -> CheckRun:
    return CheckRun(
        case_id=result.case_id,
        label=result.label,
        mode=result.mode,
        purpose=result.purpose,
        category=case.category,
        theme=case.theme,
        travel_mode=case.travel_mode,
        region_hint=case.region_hint,
        limit=case.limit,
        expectation_based=expectation_based,
        passed=result.passed if expectation_based else None,
        result_count=result.result_count,
        query_summary=result.query_summary,
        request_payload=case.to_request().model_dump(mode="json"),
        matched_expected_names=result.matched_expected_names,
        violated_forbidden_names=result.violated_forbidden_names,
        top_result_names=result.top_result_names,
        soft_warnings=result.soft_warnings,
        notes=result.notes,
        results=result.results,
    )


def _slugify_case_id(prefix: str, label: str | None) -> str:
    if label is None:
        return prefix
    slug = re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-")
    return f"{prefix}-{slug}" if slug else prefix


def _format_full_score_breakdown(score_breakdown: dict[str, float]) -> str:
    return ", ".join(f"{key}={value:.1f}" for key, value in score_breakdown.items())


def _default_review_output_path(review: ReviewArtifact, review_dir: Path, *, suffix: str) -> Path:
    timestamp = review.timestamp.strftime("%Y%m%dT%H%M%SZ")
    safe_case_id = re.sub(r"[^a-zA-Z0-9._-]+", "-", review.case_id).strip("-")
    return review_dir / f"{timestamp}_{safe_case_id}{suffix}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
