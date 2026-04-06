from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from poi_curator_domain.theme_service import (
    evaluate_rail_theme,
    evaluate_theme_memberships,
    evaluate_water_theme,
)


def test_evaluate_water_theme_accepts_canal_trace() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            canonical_name="Acequia Madre",
            normalized_subcategory="infrastructure_landmark",
            raw_tag_summary_json={"name": "Acequia Madre", "man_made": "canal"},
            aliases=[],
            evidence_items=[],
            theme_editorials=[],
        ),
    )

    membership = evaluate_water_theme(poi)

    assert membership is not None
    assert membership.theme_slug == "water"
    assert membership.status == "accepted"
    assert membership.assignment_basis == "rule"
    assert membership.confidence >= 0.6


def test_evaluate_rail_theme_accepts_historic_station_with_evidence() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            canonical_name="Atchison, Topeka & Santa Fe Railway Depot",
            normalized_category="history",
            normalized_subcategory="historic_site",
            raw_tag_summary_json={
                "name": "Atchison, Topeka & Santa Fe Railway Depot",
                "historic": "railway_station",
            },
            aliases=[],
            evidence_items=[
                SimpleNamespace(
                    id=7,
                    evidence_label="The Railyard",
                    evidence_text="The Railyard via City GIS",
                    evidence_url=None,
                    external_record_id="1",
                    raw_evidence_json={"label": "The Railyard"},
                )
            ],
            theme_editorials=[],
        ),
    )

    membership = evaluate_rail_theme(poi)

    assert membership is not None
    assert membership.theme_slug == "rail"
    assert membership.status == "accepted"
    assert membership.assignment_basis == "mixed"
    assert membership.evidence_ids == (7,)


def test_evaluate_theme_memberships_respects_force_exclude_editorial() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            canonical_name="Acequia Madre",
            normalized_subcategory="infrastructure_landmark",
            raw_tag_summary_json={"name": "Acequia Madre", "man_made": "canal"},
            aliases=[],
            evidence_items=[],
            theme_editorials=[
                SimpleNamespace(
                    theme_slug="water",
                    editorial_decision="force_exclude",
                    notes="Suppress for test.",
                    reviewed_at=datetime.now(UTC),
                )
            ],
        ),
    )

    memberships = evaluate_theme_memberships(poi)

    assert memberships == {}


def test_evaluate_theme_memberships_force_excludes_only_the_requested_theme() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            canonical_name="Atchison, Topeka & Santa Fe Railway Depot",
            normalized_category="history",
            normalized_subcategory="historic_site",
            raw_tag_summary_json={
                "name": "Atchison, Topeka & Santa Fe Railway Depot",
                "historic": "railway_station",
            },
            aliases=[],
            evidence_items=[],
            theme_editorials=[
                SimpleNamespace(
                    theme_slug="water",
                    editorial_decision="force_exclude",
                    notes="Suppress only water for test.",
                    reviewed_at=datetime.now(UTC),
                )
            ],
        ),
    )

    memberships = evaluate_theme_memberships(poi)

    assert set(memberships) == {"rail"}


def test_evaluate_water_theme_rejects_name_only_art_read() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            canonical_name="Acequia Mural",
            normalized_category="art",
            normalized_subcategory="mural_public_art",
            raw_tag_summary_json={"name": "Acequia Mural", "tourism": "artwork", "artwork_type": "mural"},
            aliases=[],
            evidence_items=[],
            theme_editorials=[],
        ),
    )

    membership = evaluate_water_theme(poi)

    assert membership is None


def test_evaluate_water_theme_accepts_name_only_infrastructure_read() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            canonical_name="Acequia Madre",
            normalized_category="civic",
            normalized_subcategory="infrastructure_landmark",
            raw_tag_summary_json={"name": "Acequia Madre"},
            aliases=[],
            evidence_items=[],
            theme_editorials=[],
        ),
    )

    membership = evaluate_water_theme(poi)

    assert membership is not None
    assert membership.status == "accepted"
    assert membership.assignment_basis == "rule"


def test_evaluate_rail_theme_rejects_name_only_art_read() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            canonical_name="Railyard Mural",
            normalized_category="art",
            normalized_subcategory="mural_public_art",
            raw_tag_summary_json={
                "name": "Railyard Mural",
                "tourism": "artwork",
                "artwork_type": "mural",
            },
            aliases=[],
            evidence_items=[],
            theme_editorials=[],
        ),
    )

    membership = evaluate_rail_theme(poi)

    assert membership is None


def test_evaluate_rail_theme_accepts_name_only_repurposed_corridor_read() -> None:
    poi = cast(
        Any,
        SimpleNamespace(
            canonical_name="Santa Fe Railyard Park",
            normalized_category="scenic",
            normalized_subcategory="trail_river_access",
            raw_tag_summary_json={"name": "Santa Fe Railyard Park", "leisure": "park"},
            aliases=[],
            evidence_items=[],
            theme_editorials=[],
        ),
    )

    membership = evaluate_rail_theme(poi)

    assert membership is not None
    assert membership.status == "accepted"
    assert membership.assignment_basis == "rule"
