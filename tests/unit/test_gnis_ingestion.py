from __future__ import annotations

from typing import Any, cast

from geoalchemy2.shape import from_shape
from poi_curator_domain.db import POIEvidence, POIFieldProvenance
from poi_curator_ingestion.matching import IncomingSourceRecord, match_incoming_record
from poi_curator_ingestion.sources.gnis import (
    GNIS_FEATURE_CLASS_POLICY,
    GNISRecord,
    attach_variant_name_evidence,
    parse_gnis_records,
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
        self.added: list[Any] = []

    def scalar(self, statement: Any) -> Any:
        del statement
        return None

    def execute(self, statement: Any) -> FakeExecuteResult:
        del statement
        return FakeExecuteResult(self.pois)

    def add(self, value: Any) -> None:
        self.added.append(value)


def test_gnis_fixture_uses_shared_spatial_name_matching() -> None:
    poi = fake_poi("acequia-madre", "Acequia Madre", -105.928, 35.681)
    session = FakeSession([poi])

    result = match_incoming_record(
        cast(Session, session),
        IncomingSourceRecord(
            source_id="gnis",
            external_id="gnis-1",
            name="Acequia Madre",
            lon=-105.92802,
            lat=35.68101,
            region="santa-fe",
        ),
    )

    assert result.decision == "match"
    assert result.poi is poi
    assert result.strategy == "spatial_name"


def test_gnis_parser_attaches_variant_names() -> None:
    records = parse_gnis_records(
        [
            {
                "feature_id": "100",
                "feature_name": "Fixture Pueblo",
                "feature_class": "Populated Place",
                "state_name": "New Mexico",
                "county_name": "Santa Fe",
                "prim_lat_dec": "35.7",
                "prim_long_dec": "-105.9",
            }
        ],
        variant_rows=[
            {
                "feature_id": "100",
                "feature_name": "Old Fixture Pueblo",
                "feature_name_official": "Variant",
            },
            {
                "feature_id": "100",
                "feature_name": "Fixture Pueblo",
                "feature_name_official": "Official",
            },
        ],
    )

    assert records[0].variant_names == ("Old Fixture Pueblo",)


def test_gnis_variant_names_create_evidence_and_name_provenance() -> None:
    session = FakeSession()
    record = make_record(variant_names=("Old Fixture Pueblo",))

    count = attach_variant_name_evidence(cast(Session, session), "poi-1", record)

    assert count == 1
    assert any(
        isinstance(item, POIEvidence) and item.evidence_type == "variant_name"
        for item in session.added
    )
    assert any(
        isinstance(item, POIFieldProvenance)
        and item.field_name == "name"
        and item.value == "Old Fixture Pueblo"
        for item in session.added
    )


def test_historical_gnis_feature_does_not_create_canonical() -> None:
    records = parse_gnis_records(
        [
            {
                "feature_id": "200",
                "feature_name": "Fixture Camp",
                "feature_class": "Populated Place",
                "state_name": "New Mexico",
                "county_name": "Santa Fe",
                "prim_lat_dec": "35.71",
                "prim_long_dec": "-105.91",
            }
        ],
        historical_rows=[
            {
                "feature_id": "200",
                "feature_name": "Fixture Camp",
                "feature_class": "Populated Place",
            }
        ],
    )

    assert records[0].is_historical is True
    assert should_create_canonical(records[0]) is False


def test_gnis_canonical_policy_creates_only_stop_shaped_classes() -> None:
    for feature_class in GNIS_FEATURE_CLASS_POLICY["canonical_create"]:
        record = make_record(feature_class=feature_class)

        assert should_create_canonical(record) is True


def test_gnis_evidence_only_policy_does_not_create_canonical() -> None:
    for feature_class in GNIS_FEATURE_CLASS_POLICY["evidence_only"]:
        record = make_record(feature_class=feature_class)

        assert should_create_canonical(record) is False


def make_record(
    *,
    variant_names: tuple[str, ...] = (),
    feature_class: str = "Populated Place",
) -> GNISRecord:
    return GNISRecord(
        feature_id="100",
        feature_name="Fixture Pueblo",
        feature_class=feature_class,
        state_name="New Mexico",
        county_name="Santa Fe",
        map_name=None,
        date_created=None,
        date_edited=None,
        lon=-105.9,
        lat=35.7,
        variant_names=variant_names,
        is_historical=False,
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
