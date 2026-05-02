from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from geoalchemy2.shape import from_shape
from poi_curator_domain.db import POIFieldProvenance
from poi_curator_domain.provenance import provenance_conflicts
from poi_curator_ingestion.matching import (
    IncomingSourceRecord,
    match_incoming_record,
    normalized_name_similarity,
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
    def __init__(self, pois: list[Any], identifier_match: Any | None = None) -> None:
        self.pois = pois
        self.identifier_match = identifier_match
        self.added: list[Any] = []

    def scalar(self, statement: Any) -> Any:
        del statement
        return self.identifier_match

    def execute(self, statement: Any) -> FakeExecuteResult:
        del statement
        return FakeExecuteResult(self.pois)

    def add(self, value: Any) -> None:
        self.added.append(value)


def test_identifier_match_uses_wikidata_evidence() -> None:
    poi = fake_poi("palace", "Palace of the Governors", -105.9383, 35.6878)
    session = FakeSession([], identifier_match=poi)

    result = match_incoming_record(cast(Session, session), incoming(wikidata_id="Q1"))

    assert result.decision == "match"
    assert result.poi is poi
    assert result.strategy == "identifier:wikidata"


def test_spatial_name_match_requires_single_candidate() -> None:
    poi = fake_poi("palace", "The Palace of the Governors", -105.9383, 35.6878)
    session = FakeSession([poi])

    result = match_incoming_record(cast(Session, session), incoming(name="Palace Governors"))

    assert result.decision == "match"
    assert result.poi is poi
    assert result.score is not None and result.score >= 0.85


def test_spatial_name_match_marks_multi_candidate_ambiguous() -> None:
    session = FakeSession(
        [
            fake_poi("one", "Palace of the Governors", -105.9383, 35.6878),
            fake_poi("two", "Palace Governors Site", -105.93831, 35.68781),
        ]
    )

    result = match_incoming_record(cast(Session, session), incoming(name="Palace Governors"))

    assert result.decision == "ambiguous"
    assert result.candidate_count == 2
    assert any(getattr(item, "status", None) == "ambiguous" for item in session.added)


def test_no_match_creates_new_decision() -> None:
    session = FakeSession([fake_poi("plaza", "Santa Fe Plaza", -105.9378, 35.687)])

    result = match_incoming_record(
        cast(Session, session),
        incoming(name="Remote Listed House", lon=-106.2),
    )

    assert result.decision == "new"
    assert result.poi is None


def test_normalized_similarity_removes_common_affixes() -> None:
    assert normalized_name_similarity("The Santa Fe Depot", "Depot") == 1.0


def test_provenance_conflicts_detect_field_disagreement() -> None:
    now = datetime.now(UTC)
    rows = [
        POIFieldProvenance(
            poi_id="poi-1",
            field_name="name",
            source_id="osm",
            value="Old Name",
            confidence=0.8,
            observed_at=now,
            is_canonical=True,
        ),
        POIFieldProvenance(
            poi_id="poi-1",
            field_name="name",
            source_id="nrhp",
            value="Register Name",
            confidence=0.9,
            observed_at=now,
            is_canonical=False,
        ),
    ]

    assert "name" in provenance_conflicts(rows)


def incoming(
    *,
    name: str = "Palace of the Governors",
    lon: float = -105.93832,
    lat: float = 35.68782,
    wikidata_id: str | None = None,
) -> IncomingSourceRecord:
    return IncomingSourceRecord(
        source_id="nrhp",
        external_id="123",
        name=name,
        lon=lon,
        lat=lat,
        region="santa-fe",
        wikidata_id=wikidata_id,
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
