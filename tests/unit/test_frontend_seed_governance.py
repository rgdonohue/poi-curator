from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_module() -> ModuleType:
    script_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "validate_frontend_seed_governance.py"
    )
    spec = importlib.util.spec_from_file_location("validate_frontend_seed_governance", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_rows_accepts_governed_generated_draft_rows() -> None:
    module = _load_module()

    errors = module.validate_rows(
        [
            {
                "record_origin": "database",
                "source_basis": "osm_overpass|city_gis_historic_districts",
                "evidence_strength": "medium",
                "description_status": "generated_draft",
                "description_method": "deterministic_draft",
                "description_review_status": "unreviewed",
                "claim_basis": "historic_district|wikidata_id",
                "risk_flags": "history_sensitivity",
            },
            {
                "record_origin": "fixture_overlay",
                "source_basis": "fixture_overlay",
                "evidence_strength": "low",
                "description_status": "generated_draft",
                "description_method": "deterministic_draft",
                "description_review_status": "unreviewed",
                "claim_basis": "fixture_overlay",
                "risk_flags": "synthetic_fixture|low_evidence",
            },
        ]
    )

    assert errors == []


def test_validate_rows_rejects_missing_claim_basis_and_fixture_flag() -> None:
    module = _load_module()

    errors = module.validate_rows(
        [
            {
                "record_origin": "fixture_overlay",
                "source_basis": "fixture_overlay",
                "evidence_strength": "low",
                "description_status": "generated_draft",
                "description_method": "deterministic_draft",
                "description_review_status": "unreviewed",
                "claim_basis": "",
                "risk_flags": "low_evidence",
            }
        ]
    )

    assert any("missing claim_basis" in error for error in errors)
    assert any("synthetic_fixture" in error for error in errors)
