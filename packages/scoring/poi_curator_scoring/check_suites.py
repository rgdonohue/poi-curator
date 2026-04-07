from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from poi_curator_scoring.checks import CheckReport, load_named_cases
from poi_curator_scoring.evaluation import EvaluationCase, load_evaluation_cases


@dataclass(frozen=True)
class CheckSuite:
    name: str
    description: str
    case_ids: tuple[str, ...]


@dataclass(frozen=True)
class SuiteRunArtifact:
    suite: CheckSuite
    report: CheckReport
    json_path: Path
    markdown_path: Path


CHECK_SUITES: tuple[CheckSuite, ...] = (
    CheckSuite(
        name="core-product",
        description=(
            "Balanced product smoke suite across nearby, route, themes, and strong anchors."
        ),
        case_ids=(
            "nearby-plaza-history",
            "nearby-canyon-art",
            "nearby-railyard-rail",
            "route-historic-center-driving",
            "route-railyard-rail",
            "route-arts-corridor-walk",
        ),
    ),
    CheckSuite(
        name="rail-smoke",
        description=(
            "Rail-focused cases that protect depot anchors and keep weaker corridor traces behind."
        ),
        case_ids=(
            "nearby-railyard-civic",
            "nearby-railyard-rail",
            "route-railyard-civic",
            "route-railyard-rail",
        ),
    ),
    CheckSuite(
        name="water-smoke",
        description="Water-theme and water-adjacent nearby/route behavior around acequia cases.",
        case_ids=(
            "nearby-acequia-water",
            "nearby-plaza-water-empty",
            "route-acequia-water",
        ),
    ),
    CheckSuite(
        name="empty-result-guardrails",
        description="Cases where honest empty results are better than decorative filler.",
        case_ids=(
            "nearby-plaza-water-empty",
            "nearby-plaza-rail-empty",
            "nearby-downtown-scenic-empty",
            "route-downtown-scenic-empty",
        ),
    ),
    CheckSuite(
        name="nearby-smoke",
        description="Broad nearby-only product smoke suite across current fixture cases.",
        case_ids=(
            "nearby-acequia-water",
            "nearby-plaza-history",
            "nearby-canyon-art",
            "nearby-railyard-civic",
            "nearby-railyard-rail",
            "nearby-plaza-water-empty",
            "nearby-plaza-rail-empty",
            "nearby-downtown-scenic-empty",
        ),
    ),
    CheckSuite(
        name="route-smoke",
        description="Broad route-only product smoke suite across current fixture cases.",
        case_ids=(
            "route-acequia-water",
            "route-historic-center-driving",
            "route-railyard-civic",
            "route-railyard-rail",
            "route-arts-corridor-walk",
            "route-downtown-scenic-empty",
        ),
    ),
    CheckSuite(
        name="all-fixtures",
        description="Every saved evaluation case in the fixture file.",
        case_ids=(),
    ),
)


def list_check_suites() -> tuple[CheckSuite, ...]:
    return CHECK_SUITES


def get_check_suite(name: str) -> CheckSuite:
    for suite in CHECK_SUITES:
        if suite.name == name:
            return suite
    available = ", ".join(suite.name for suite in CHECK_SUITES)
    raise KeyError(f"{name} (available: {available})")


def resolve_suite_cases(fixtures: Path, suite_name: str) -> list[EvaluationCase]:
    suite = get_check_suite(suite_name)
    if suite.name == "all-fixtures":
        return load_evaluation_cases(fixtures)
    return load_named_cases(fixtures, suite.case_ids)


def default_suite_run_dir(base_dir: Path = Path("reports/check_runs")) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return base_dir / timestamp


def render_suite_index_markdown(
    *,
    fixtures: Path,
    suite_runs: Sequence[SuiteRunArtifact],
) -> str:
    total_runs = sum(run.report.run_count for run in suite_runs)
    total_passed = sum(run.report.passed_count or 0 for run in suite_runs)
    total_failed = sum(run.report.failed_count or 0 for run in suite_runs)

    lines = [
        "# POI Curator Check Suite Run",
        "",
        f"- Fixtures: {fixtures}",
        f"- Suites: {len(suite_runs)}",
        f"- Case runs: {total_runs}",
        f"- Passed: {total_passed}",
        f"- Failed: {total_failed}",
        "",
    ]

    for run in suite_runs:
        lines.append(f"## {run.suite.name}")
        lines.append(f"- Description: {run.suite.description}")
        lines.append(f"- Cases: {run.report.run_count}")
        lines.append(f"- Passed: {run.report.passed_count or 0}")
        lines.append(f"- Failed: {run.report.failed_count or 0}")
        lines.append(f"- JSON: {run.json_path.name}")
        lines.append(f"- Markdown: {run.markdown_path.name}")
        lines.append("")

    return "\n".join(lines)
