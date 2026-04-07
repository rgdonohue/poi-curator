#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from poi_curator_domain.db import get_session_factory
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
    build_report,
    render_terminal_run,
    run_check_case,
    write_report_files,
)


def main() -> int:
    args = parse_args()

    if args.list_suites:
        print_available_suites()
        return 0

    suite_names = args.suite or ["core-product"]
    out_dir = args.out_dir or default_suite_run_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    backend = get_database_scoring_backend()
    session_factory = get_session_factory()
    suite_artifacts: list[SuiteRunArtifact] = []

    with session_factory() as session:
        for suite_name in suite_names:
            suite = get_check_suite(suite_name)
            cases = resolve_suite_cases(args.fixtures, suite_name)
            runs = [
                run_check_case(backend, session, case, expectation_based=True) for case in cases
            ]
            report = build_report(runs, fixtures_path=args.fixtures)
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
                    case_report = build_report([run], fixtures_path=args.fixtures)
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
        "--list-suites",
        action="store_true",
        help="Print available suite names and exit.",
    )
    return parser.parse_args()


def print_available_suites() -> None:
    for suite in list_check_suites():
        print(f"{suite.name}: {suite.description}")


def print_suite_summary(*, suite_name: str, report: object, verbose: bool) -> None:
    print(f"[suite] {suite_name}")
    print(f"runs={report.run_count}")
    print(f"passed={report.passed_count or 0}")
    print(f"failed={report.failed_count or 0}")
    for index, run in enumerate(report.runs):
        if index:
            print("")
        print(render_terminal_run(run, verbose=verbose))
    print("")


if __name__ == "__main__":
    sys.exit(main())
