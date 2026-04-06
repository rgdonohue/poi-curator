from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from poi_curator_domain.theme_service import evaluate_theme_memberships, evaluate_water_theme


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
