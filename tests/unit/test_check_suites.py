from pathlib import Path

from poi_curator_scoring.check_suites import (
    CheckSuite,
    SuiteRunArtifact,
    default_suite_run_dir,
    get_check_suite,
    render_suite_index_markdown,
    resolve_suite_cases,
)
from poi_curator_scoring.checks import CheckReport, CheckRun


def test_get_check_suite_finds_named_suite() -> None:
    suite = get_check_suite("rail-smoke")

    assert suite.name == "rail-smoke"
    assert "nearby-railyard-rail" in suite.case_ids


def test_resolve_suite_cases_loads_expected_fixture_cases() -> None:
    cases = resolve_suite_cases(Path("data/fixtures/eval_santa_fe.json"), "water-smoke")

    assert [case.id for case in cases] == [
        "nearby-acequia-water",
        "nearby-plaza-water-empty",
        "route-acequia-water",
    ]


def test_default_suite_run_dir_uses_timestamped_parent() -> None:
    out_dir = default_suite_run_dir(Path("reports/check_runs"))

    assert out_dir.parent == Path("reports/check_runs")
    assert out_dir.name.endswith("Z")


def test_render_suite_index_markdown_includes_paths_and_counts() -> None:
    suite = CheckSuite(
        name="rail-smoke",
        description="Rail checks.",
        case_ids=("nearby-railyard-rail",),
    )
    report = CheckReport(
        generated_at="2026-04-07T12:00:00Z",
        fixtures_path="data/fixtures/eval_santa_fe.json",
        run_count=1,
        passed_count=1,
        failed_count=0,
        runs=[
            CheckRun(
                case_id="nearby-railyard-rail",
                label="Railyard Rail Nearby",
                mode="nearby",
                purpose="Rail suite.",
                category="mixed",
                theme="rail",
                travel_mode="walking",
                region_hint="santa-fe",
                limit=5,
                expectation_based=True,
                passed=True,
                result_count=0,
                query_summary={},
                request_payload={},
            )
        ],
    )

    markdown = render_suite_index_markdown(
        fixtures=Path("data/fixtures/eval_santa_fe.json"),
        suite_runs=[
            SuiteRunArtifact(
                suite=suite,
                report=report,
                json_path=Path("rail-smoke.json"),
                markdown_path=Path("rail-smoke.md"),
            )
        ],
    )

    assert "POI Curator Check Suite Run" in markdown
    assert "rail-smoke" in markdown
    assert "rail-smoke.json" in markdown
    assert "Passed: 1" in markdown
