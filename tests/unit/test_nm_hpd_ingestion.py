from __future__ import annotations

from typing import Any, cast

from geoalchemy2.shape import from_shape
from poi_curator_ingestion.sources.nm_hpd import (
    NMHPDRecord,
    classify_legacy_hpd_diagnostic,
    display_name_for_register_name,
    is_district_designation,
    match_hpd_by_name_address,
    parse_hpd_rows,
    should_create_canonical,
)
from shapely.geometry import Point
from sqlalchemy.orm import Session


class FakeScalarResult:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def all(self) -> list[Any]:
        return self.values


class FakeExecuteResult:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def unique(self) -> FakeExecuteResult:
        return self

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self.values)


class FakeSession:
    def __init__(self, pois: list[Any] | None = None) -> None:
        self.pois = pois or []

    def execute(self, statement: Any) -> FakeExecuteResult:
        del statement
        return FakeExecuteResult(self.pois)


def test_hpd_parser_reads_state_register_rows_and_category() -> None:
    rows = list(
        parse_hpd_rows(
            [
                {
                    "SR#": "4",
                    "Name of Property": "Barrio de Analco National Register Historic District NHL",
                    "County": "Santa Fe",
                    "Property Category": "District",
                    "STATE\nREGISTER": "1966",
                    "NATIONAL REGISTER": "1968",
                    "NHL": "1",
                    "Address": "Rough bound: E. De Vargas & College St",
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
    )

    assert len(rows) == 1
    assert rows[0].register_number == "4"
    assert rows[0].property_category == "District"
    assert rows[0].is_nhl is True


def test_hpd_register_name_normalization_uses_common_person_name_order() -> None:
    assert display_name_for_register_name("Delgado, Felipe, House") == "Felipe Delgado House"
    assert display_name_for_register_name("Santa Fe Plaza NHL") == "Santa Fe Plaza NHL"


def test_hpd_policy_keeps_districts_evidence_only() -> None:
    district = make_record(
        property_name="Barrio de Analco Historic District",
        property_category="District",
        lon=-105.93,
        lat=35.68,
    )
    building = make_record(property_category="Building", lon=-105.93, lat=35.68)
    unlocated = make_record(property_category="Building")

    assert is_district_designation(district) is True
    assert should_create_canonical(district) is False
    assert should_create_canonical(building) is True
    assert should_create_canonical(unlocated) is False


def test_hpd_name_address_matching_uses_current_name_threshold() -> None:
    poi = fake_poi("delgado", "Felipe Delgado House", -105.93, 35.68)
    session = FakeSession([poi])
    record = make_record(property_name="Delgado, Felipe, House")

    result = match_hpd_by_name_address(cast(Session, session), record, "santa-fe")

    assert result.decision == "match"
    assert result.poi is poi
    assert result.strategy == "name_address"


def test_hpd_legacy_reconciliation_classification() -> None:
    current = {"58", "62"}

    assert (
        classify_legacy_hpd_diagnostic(
            external_record_id="58",
            external_name="Delgado, Felipe, House",
            current_register_numbers=current,
            has_new_evidence=True,
        )
        == "superseded_by_nm_hpd_run"
    )
    assert (
        classify_legacy_hpd_diagnostic(
            external_record_id="62",
            external_name="Gallegos, Padre, House",
            current_register_numbers=current,
            has_new_evidence=False,
        )
        == "retained_unreviewed_no_coordinates"
    )
    assert (
        classify_legacy_hpd_diagnostic(
            external_record_id="diag-a285dd4e",
            external_name="Theme Queue Case",
            current_register_numbers=current,
            has_new_evidence=False,
        )
        == "non_source_noise"
    )


def make_record(
    *,
    property_name: str = "Delgado, Felipe, House",
    property_category: str | None = "Building",
    lon: float | None = None,
    lat: float | None = None,
) -> NMHPDRecord:
    return NMHPDRecord(
        register_number="58",
        property_name=property_name,
        county="Santa Fe",
        city="Santa Fe",
        street_address="124 W. Palace Ave.",
        property_category=property_category,
        state_register_year="1969",
        national_register_year=None,
        is_nhl=False,
        common_notes=None,
        restricted=False,
        lon=lon,
        lat=lat,
        raw_payload={},
    )


def fake_poi(poi_id: str, name: str, lon: float, lat: float) -> Any:
    return type(
        "FakePOI",
        (),
        {
            "poi_id": poi_id,
            "canonical_name": name,
            "centroid": from_shape(Point(lon, lat), srid=4326),
            "aliases": [],
        },
    )()
