from __future__ import annotations

from typing import Any, cast

from geoalchemy2.shape import from_shape
from poi_curator_domain.db import POI, POIEvidence
from poi_curator_ingestion.matching import IncomingSourceRecord, match_incoming_record
from poi_curator_ingestion.sources.nm_dca import (
    DCA_RECORD_TYPE_POLICY,
    NM_DCA_SOURCE_ID,
    ingest_dca_records,
    parse_dca_records,
    should_create_canonical,
    upsert_dca_evidence,
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
        self.new = self.added
        self.committed = False

    def get(self, model: Any, key: Any) -> Any:
        del model, key
        return None

    def scalar(self, statement: Any) -> Any:
        del statement
        return None

    def execute(self, statement: Any) -> FakeExecuteResult:
        del statement
        return FakeExecuteResult(self.pois)

    def add(self, value: Any) -> None:
        self.added.append(value)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        self.committed = True


def test_dca_parser_accepts_bootstrap_institution_rows() -> None:
    records = parse_dca_records(
        [
            {
                "external_id": "dca-1",
                "name": "Fixture Museum",
                "record_type": "state_museum",
                "division": "Fixture Division",
                "city": "Santa Fe",
                "address": "1 Fixture Way",
                "lon": "-105.9",
                "lat": "35.7",
                "source_url": "https://example.org/fixture",
            }
        ]
    )

    assert len(records) == 1
    assert records[0].name == "Fixture Museum"
    assert records[0].lon == -105.9
    assert records[0].lat == 35.7


def test_dca_canonical_policy_is_limited_to_visitor_facing_records() -> None:
    for record_type in DCA_RECORD_TYPE_POLICY["canonical_create"]:
        assert should_create_canonical(make_record(record_type=record_type)) is True
    for record_type in DCA_RECORD_TYPE_POLICY["evidence_only"]:
        assert should_create_canonical(make_record(record_type=record_type)) is False


def test_dca_institution_uses_shared_spatial_name_matching() -> None:
    poi = fake_poi("museum-1", "New Mexico History Museum", -105.938, 35.6883)
    session = FakeSession([poi])

    result = match_incoming_record(
        cast(Session, session),
        IncomingSourceRecord(
            source_id=NM_DCA_SOURCE_ID,
            external_id="nm-dca-history-museum",
            name="New Mexico History Museum",
            lon=-105.93802,
            lat=35.68829,
            region="santa-fe",
        ),
    )

    assert result.decision == "match"
    assert result.poi is poi
    assert result.strategy == "spatial_name"


def test_dca_evidence_attachment_writes_membership_evidence() -> None:
    session = FakeSession()
    record = make_record()

    created = upsert_dca_evidence(cast(Session, session), "poi-1", record)

    assert created is True
    assert any(
        isinstance(item, POIEvidence)
        and item.source_id == NM_DCA_SOURCE_ID
        and item.evidence_type == "dca_institution_membership"
        for item in session.added
    )


def test_dca_ingest_attaches_evidence_when_existing_canonical_matches() -> None:
    poi = fake_poi("museum-1", "New Mexico History Museum", -105.9380178, 35.6882912)
    session = FakeSession([poi])

    summary = ingest_dca_records(
        cast(Session, session),
        "santa-fe",
        row_loader=lambda: [
            {
                "external_id": "nm-dca-history-museum",
                "name": "New Mexico History Museum",
                "record_type": "state_museum",
                "division": "New Mexico History Museum",
                "city": "Santa Fe",
                "address": "113 Lincoln Avenue, Santa Fe, NM 87501",
                "lon": "-105.9380178",
                "lat": "35.6882912",
                "source_url": "https://www.nmhistorymuseum.org/",
            }
        ],
    )

    assert summary.canonical_created == 0
    assert summary.evidence_attached == 1
    assert not any(
        isinstance(item, POI) and item.primary_source == NM_DCA_SOURCE_ID
        for item in session.added
    )
    assert any(isinstance(item, POIEvidence) for item in session.added)
    assert session.committed is True


def test_dca_ingest_creates_canonical_for_unmatched_institution() -> None:
    session = FakeSession()

    summary = ingest_dca_records(
        cast(Session, session),
        "santa-fe",
        row_loader=lambda: [
            {
                "external_id": "nm-dca-fixture-museum",
                "name": "Fixture DCA Museum",
                "record_type": "state_museum",
                "division": "Fixture DCA Museum",
                "city": "Santa Fe",
                "address": "100 Fixture Way, Santa Fe, NM",
                "lon": "-105.85",
                "lat": "35.70",
                "source_url": "https://example.org/fixture",
            }
        ],
    )

    assert summary.canonical_created == 1
    assert summary.evidence_attached == 1
    assert any(
        isinstance(item, POI) and item.primary_source == NM_DCA_SOURCE_ID
        for item in session.added
    )


def make_record(*, record_type: str = "state_museum") -> Any:
    return parse_dca_records(
        [
            {
                "external_id": "dca-1",
                "name": "Fixture Museum",
                "record_type": record_type,
                "division": "Fixture Division",
                "city": "Santa Fe",
                "address": "1 Fixture Way",
                "lon": "-105.9",
                "lat": "35.7",
                "source_url": "https://example.org/fixture",
            }
        ]
    )[0]


def fake_poi(poi_id: str, name: str, lon: float, lat: float) -> Any:
    return type(
        "FakePOI",
        (),
        {
            "poi_id": poi_id,
            "canonical_name": name,
            "centroid": from_shape(Point(lon, lat), srid=4326),
            "aliases": [],
            "signals": None,
        },
    )()
