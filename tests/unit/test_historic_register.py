from types import SimpleNamespace
from typing import Any, cast

from poi_curator_enrichment.historic_register import (
    HistoricRegisterRow,
    evaluate_register_row_match,
    filter_rows_for_region,
    match_register_row_to_poi,
    normalize_historic_name,
    rows_from_hpd_workbook,
)
from poi_curator_enrichment.pipeline import summarize_evidence_signals


def test_filter_rows_for_region_limits_state_and_city() -> None:
    rows = [
        HistoricRegisterRow(
            reference_number="1",
            property_name="Palace of the Governors",
            state="NEW MEXICO",
            county="Santa Fe",
            city="santa-fe",
            street_address="105 W Palace Ave",
            category_of_property="BUILDING",
            listed_date="1/1/1966",
            external_link=None,
            other_names=None,
        ),
        HistoricRegisterRow(
            reference_number="2",
            property_name="Other Place",
            state="NEW MEXICO",
            county="Bernalillo",
            city="albuquerque",
            street_address="",
            category_of_property="BUILDING",
            listed_date="1/1/1966",
            external_link=None,
            other_names=None,
        ),
    ]

    filtered = filter_rows_for_region(rows, state="NEW MEXICO", city="santa-fe")

    assert [row.reference_number for row in filtered] == ["1"]


def test_match_register_row_to_poi_uses_name_similarity() -> None:
    row = HistoricRegisterRow(
        reference_number="123",
        property_name="Palace of the Governors",
        state="NEW MEXICO",
        county="Santa Fe",
        city="santa-fe",
        street_address="105 W Palace Ave",
        category_of_property="BUILDING",
        listed_date="1/1/1966",
        external_link=None,
        other_names="Palace of the Governor's",
    )
    pois = [
        cast(
            Any,
            SimpleNamespace(
                poi_id="palace",
                canonical_name="Palace of the Governors",
                historical_flag=True,
            ),
        ),
        cast(
            Any,
            SimpleNamespace(
                poi_id="plaza",
                canonical_name="The Santa Fe Plaza",
                historical_flag=False,
            ),
        ),
    ]

    match = match_register_row_to_poi(row, pois)

    assert match is not None
    assert match.poi_id == "palace"
    assert match.confidence >= 0.8
    assert match.match_strategy == "canonical_exact"


def test_match_register_row_to_poi_uses_aliases_before_fuzzy_fallback() -> None:
    row = HistoricRegisterRow(
        reference_number="456",
        property_name="San Miguel Chapel",
        state="NEW MEXICO",
        county="Santa Fe",
        city="santa-fe",
        street_address="401 Old Santa Fe Trail",
        category_of_property="BUILDING",
        listed_date="1/1/1966",
        external_link=None,
        other_names="San Miguel Mission Church",
    )
    pois = [
        cast(
            Any,
            SimpleNamespace(
                poi_id="san-miguel",
                canonical_name="San Miguel",
                historical_flag=True,
                aliases=[SimpleNamespace(alias_name="San Miguel Chapel")],
            ),
        )
    ]

    match = match_register_row_to_poi(row, pois)

    assert match is not None
    assert match.poi_id == "san-miguel"
    assert match.match_strategy == "alias_exact"


def test_evaluate_register_row_match_keeps_best_candidate_for_unmatched_rows() -> None:
    row = HistoricRegisterRow(
        reference_number="789",
        property_name="Old Barrio Resource",
        state="NEW MEXICO",
        county="Santa Fe",
        city="santa-fe",
        street_address="",
        category_of_property="DISTRICT",
        listed_date="1/1/1966",
        external_link=None,
        other_names=None,
    )
    pois = [
        cast(
            Any,
            SimpleNamespace(
                poi_id="analco",
                canonical_name="Barrio de Analco Historic District",
                historical_flag=True,
                aliases=[],
            ),
        )
    ]

    evaluation = evaluate_register_row_match(row, pois, threshold=0.95)

    assert evaluation.match is None
    assert evaluation.best_candidate is not None
    assert evaluation.best_candidate.poi_id == "analco"
    assert evaluation.best_candidate.match_strategy == "fuzzy_fallback"


def test_historic_designation_increases_official_signal() -> None:
    evidence_rows = [
        cast(
            Any,
            SimpleNamespace(
                evidence_type="historic_designation",
                raw_evidence_json={"category_of_property": "DISTRICT"},
            ),
        )
    ]

    summary = summarize_evidence_signals(evidence_rows)

    assert summary.has_official_heritage_match is True
    assert summary.official_corroboration_score == 1.0
    assert summary.district_membership_score == 0.9


def test_rows_from_hpd_workbook_maps_generic_headers() -> None:
    rows = rows_from_hpd_workbook(
        [
            {
                "Name": "Loretto Chapel",
                "City": "Santa Fe",
                "County": "Santa Fe",
                "Number": "1234",
                "Type": "BUILDING",
                "STATE REGISTER": "1963",
            }
        ]
    )

    assert len(rows) == 1
    assert rows[0].property_name == "Loretto Chapel"
    assert rows[0].city == "santa-fe"
    assert rows[0].reference_number == "1234"
    assert rows[0].state_register_year == "1963"


def test_rows_from_hpd_workbook_uses_real_header_variants_and_requires_state_year() -> None:
    rows = rows_from_hpd_workbook(
        [
            {
                "SR#": "4",
                "Name of Property": "Barrio de Analco National Register Historic District NHL",
                "County": "Santa Fe",
                "Property Category": "District",
                "STATE\nREGISTER": "1966",
                "City": "Santa Fe",
            },
            {
                "SR#": "5",
                "Name of Property": "National Register Only Example",
                "County": "Santa Fe",
                "Property Category": "Building",
                "STATE\nREGISTER": "",
                "City": "Santa Fe",
            },
        ]
    )

    assert len(rows) == 1
    assert rows[0].reference_number == "4"
    assert rows[0].state_register_year == "1966"


def test_normalize_historic_name_strips_register_suffixes() -> None:
    normalized = normalize_historic_name(
        "Barrio de Analco National Register Historic District NHL",
        relaxed=True,
    )

    assert normalized == "barrio analco"


def test_normalize_historic_name_strips_documentation_noise() -> None:
    normalized = normalize_historic_name(
        "Chapel of San Miguel and Collections (Additional Documentation)",
        relaxed=True,
    )

    assert normalized == "chapel san miguel"
