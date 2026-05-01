#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from poi_curator_domain.db import get_session_factory
from poi_curator_domain.settings import get_settings
from poi_curator_scoring.backend import get_database_scoring_backend
from poi_curator_scoring.check_suites import (
    SuiteRunArtifact,
    default_suite_run_dir,
    get_check_suite,
    list_check_suites,
    render_suite_index_markdown,
    resolve_suite_cases,
)
from poi_curator_scoring.checks import (
    DEFAULT_FIXTURES_PATH,
    CheckReport,
    build_report,
    render_terminal_run,
    run_check_case,
    write_report_files,
)
from sqlalchemy.engine import make_url


def main() -> int:
    args = parse_args()

    if args.list_suites:
        print_available_suites()
        return 0

    suite_names = args.suite or ["core-product"]
    generated_at = parse_frozen_time(args.frozen_time)
    out_dir = resolve_output_dir(args.out_dir, args.run_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    backend = get_database_scoring_backend(
        allow_fixture_fallback=args.allow_fixture_fallback,
    )
    session_factory = get_session_factory()
    suite_artifacts: list[SuiteRunArtifact] = []
    database_target = summarize_database_target()
    backend_mode = "hybrid" if args.allow_fixture_fallback else "database_only"

    with session_factory() as session:
        for suite_name in suite_names:
            suite = get_check_suite(suite_name)
            cases = resolve_suite_cases(args.fixtures, suite_name)
            runs = [
                run_check_case(backend, session, case, expectation_based=True) for case in cases
            ]
            report = build_report(
                runs,
                fixtures_path=args.fixtures,
                backend_mode=backend_mode,
                fixture_fallback_allowed=args.allow_fixture_fallback,
                database_target=database_target,
                generated_at=generated_at,
            )
            json_path = out_dir / f"{suite.name}.json"
            markdown_path = out_dir / f"{suite.name}.md"
            write_report_files(
                report,
                json_out=json_path,
                md_out=markdown_path,
                verbose_markdown=args.verbose,
            )
            suite_artifacts.append(
                SuiteRunArtifact(
                    suite=suite,
                    report=report,
                    json_path=json_path,
                    markdown_path=markdown_path,
                )
            )
            print_suite_summary(suite_name=suite.name, report=report, verbose=args.verbose)

            if args.split_cases:
                case_dir = out_dir / suite.name
                case_dir.mkdir(parents=True, exist_ok=True)
                for run in runs:
                    case_report = build_report(
                        [run],
                        fixtures_path=args.fixtures,
                        backend_mode=backend_mode,
                        fixture_fallback_allowed=args.allow_fixture_fallback,
                        database_target=database_target,
                        generated_at=generated_at,
                    )
                    write_report_files(
                        case_report,
                        json_out=case_dir / f"{run.case_id}.json",
                        md_out=case_dir / f"{run.case_id}.md",
                        verbose_markdown=args.verbose,
                    )

    index_path = out_dir / "index.md"
    index_path.write_text(
        render_suite_index_markdown(fixtures=args.fixtures, suite_runs=suite_artifacts),
        encoding="utf-8",
    )

    print("")
    print(f"index={index_path}")
    print(f"out_dir={out_dir}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run saved poi-curator-check suites and write grouped review artifacts.",
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FIXTURES_PATH,
        help="Evaluation fixture file (.json).",
    )
    parser.add_argument(
        "--suite",
        action="append",
        help="Named suite to run. Repeatable. Defaults to core-product.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Output directory. Defaults to reports/check_runs/<timestamp>.",
    )
    parser.add_argument(
        "--run-id",
        help="Stable run directory name under reports/check_runs/ when --out-dir is omitted.",
    )
    parser.add_argument(
        "--frozen-time",
        help="ISO timestamp to use for generated_at fields.",
    )
    parser.add_argument(
        "--split-cases",
        action="store_true",
        help="Also write per-case JSON and Markdown files inside suite subdirectories.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Write fuller score breakdowns into markdown reports.",
    )
    parser.add_argument(
        "--allow-fixture-fallback",
        action="store_true",
        help=(
            "Allow fixture fallback instead of hard-failing on DB query errors "
            "or empty DB results."
        ),
    )
    parser.add_argument(
        "--list-suites",
        action="store_true",
        help="Print available suite names and exit.",
    )
    return parser.parse_args()


def resolve_output_dir(out_dir: Path | None, run_id: str | None) -> Path:
    if out_dir is not None:
        return out_dir
    if run_id is not None:
        return Path("reports/check_runs") / run_id
    return default_suite_run_dir()


def parse_frozen_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def print_available_suites() -> None:
    for suite in list_check_suites():
        print(f"{suite.name}: {suite.description}")


def print_suite_summary(*, suite_name: str, report: CheckReport, verbose: bool) -> None:
    print(f"[suite] {suite_name}")
    print(f"runs={report.run_count}")
    print(f"passed={report.passed_count or 0}")
    print(f"failed={report.failed_count or 0}")
    for index, run in enumerate(report.runs):
        if index:
            print("")
        print(render_terminal_run(run, verbose=verbose))
    print("")


def summarize_database_target() -> str:
    settings = get_settings()
    url = make_url(settings.database_url)
    host = url.host or "unknown-host"
    port = str(url.port) if url.port is not None else "default"
    database = url.database or "unknown-db"
    return f"{host}:{port}/{database}"


if __name__ == "__main__":
    sys.exit(main())
