from datetime import UTC, datetime

from poi_curator_scoring.checks import (
    CheckRun,
    ReviewArtifact,
    build_inline_route_case,
    build_report,
    render_terminal_run,
    write_report_files,
    write_review_files,
)
from poi_curator_scoring.evaluation import EvaluatedResult


def test_build_inline_route_case_uses_first_and_last_coords() -> None:
    case = build_inline_route_case(
        coordinates=[(-105.955, 35.679), (-105.952, 35.681), (-105.948, 35.6835)],
        category="mixed",
        travel_mode="walking",
        theme="rail",
        region_hint="santa-fe",
        limit=5,
        max_detour_meters=900,
        max_extra_minutes=10,
        origin_name="Depot South",
        destination_name="Depot North",
        label="Rail Corridor",
    )

    assert case.origin.name == "Depot South"
    assert case.origin.coordinates == [-105.955, 35.679]
    assert case.destination.name == "Depot North"
    assert case.destination.coordinates == [-105.948, 35.6835]
    assert len(case.route_geometry.coordinates) == 3


def test_render_terminal_run_and_write_report_files(tmp_path) -> None:
    run = CheckRun(
        case_id="nearby-railyard-rail",
        label="Railyard Rail Nearby",
        mode="nearby",
        purpose="Check rail nearby behavior.",
        category="mixed",
        theme="rail",
        travel_mode="walking",
        region_hint="santa-fe",
        limit=5,
        expectation_based=True,
        passed=True,
        result_count=1,
        query_summary={
            "travel_mode": "walking",
            "category": "mixed",
            "theme": "rail",
            "radius_meters": 900,
            "limit": 5,
        },
        request_payload={"center": {"lat": 35.6815, "lon": -105.9520}},
        top_result_names=["Atchison, Topeka & Santa Fe Railway Depot"],
        results=[
            EvaluatedResult(
                name="Atchison, Topeka & Santa Fe Railway Depot",
                score=49.0,
                primary_category="history",
                category_match_type="mixed",
                short_description="Historic depot anchor.",
                distance_label="distance_from_center_m=707 access_min=9",
                score_breakdown={
                    "point_proximity": 3.9,
                    "significance": 20.4,
                    "rail_anchor_bonus": 4.0,
                    "nearby_rail_anchor_prominence": 8.0,
                },
            )
        ],
    )

    terminal = render_terminal_run(run)

    assert "PASS nearby-railyard-rail" in terminal
    assert "Atchison, Topeka & Santa Fe Railway Depot" in terminal
    assert "nearby_rail_anchor_prominence=8.0" in terminal

    report = build_report([run])
    json_out = tmp_path / "check.json"
    md_out = tmp_path / "check.md"
    written = write_report_files(report, json_out=json_out, md_out=md_out)

    assert written == [json_out, md_out]
    assert json_out.exists()
    assert md_out.exists()
    assert "POI Curator Check Report" in md_out.read_text(encoding="utf-8")


def test_write_review_files_defaults_to_timestamped_json(tmp_path) -> None:
    review = ReviewArtifact(
        case_id="nearby-railyard-rail",
        label="Railyard Rail Nearby",
        mode="nearby",
        category="mixed",
        theme="rail",
        timestamp=datetime(2026, 4, 7, 12, 0, tzinfo=UTC),
        reviewer="richard",
        verdict="good",
        note="Depot anchors now read first.",
        query_summary={"category": "mixed", "theme": "rail", "radius_meters": 900},
        top_returned_names=["Atchison, Topeka & Santa Fe Railway Depot"],
    )

    written = write_review_files(review, review_dir=tmp_path)

    assert len(written) == 1
    assert written[0].name == "20260407T120000Z_nearby-railyard-rail.json"
    assert written[0].exists()
    assert "\"verdict\": \"good\"" in written[0].read_text(encoding="utf-8")
