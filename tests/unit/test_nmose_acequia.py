from __future__ import annotations

from typing import Any, cast

from geoalchemy2.shape import from_shape
from poi_curator_domain.db import POIEvidence
from poi_curator_ingestion.matching import IncomingSourceRecord, match_incoming_record
from poi_curator_ingestion.sources.nmose_acequia import (
    NMOSE_ACEQUIA_SOURCE_ID,
    NMOSE_POD_SOURCE_ID,
    distance_point_to_geometry_m,
    parse_conveyance_features,
    parse_pod_records,
    upsert_acequia_membership_evidence,
)
from shapely.geometry import LineString, Point, mapping
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

    def scalar(self, statement: Any) -> Any:
        del statement
        return None

    def execute(self, statement: Any) -> FakeExecuteResult:
        del statement
        return FakeExecuteResult(self.pois)

    def add(self, value: Any) -> None:
        self.added.append(value)


def test_nmose_pod_uses_shared_spatial_name_matching() -> None:
    poi = fake_poi("acequia-madre", "Acequia Madre Headgate", -105.928, 35.681)
    session = FakeSession([poi])

    result = match_incoming_record(
        cast(Session, session),
        IncomingSourceRecord(
            source_id=NMOSE_POD_SOURCE_ID,
            external_id="pod-1",
            name="Acequia Madre Headgate",
            lon=-105.92802,
            lat=35.68101,
            region="santa-fe",
        ),
    )

    assert result.decision == "match"
    assert result.poi is poi
    assert result.strategy == "spatial_name"


def test_pod_parser_filters_to_active_named_santa_fe_conveyances() -> None:
    payload = {
        "features": [
            pod_feature("1", "SF", "ACT", "Acequia Madre"),
            pod_feature("2", "SF", "INC", "Acequia Madre"),
            pod_feature("3", "TA", "ACT", "Acequia Madre"),
            pod_feature("4", "SF", "ACT", "Unknown"),
            pod_feature("5", "SF", "ACT", "`"),
        ]
    }

    records = parse_pod_records(payload)

    assert len(records) == 1
    assert records[0].external_id == "1"
    assert records[0].name == "Point of Diversion - Acequia Madre"


def test_conveyance_parser_accepts_only_linear_acequia_like_features() -> None:
    line = LineString([(-105.928, 35.681), (-105.927, 35.681)])
    payload = {
        "features": [
            conveyance_feature("1", "ACQ", "Active", "Acequia Madre", mapping(line)),
            conveyance_feature("2", "RIV", "Active", "Santa Fe River", mapping(line)),
            conveyance_feature("3", "ACQ", "Inactive", "Old Acequia", mapping(line)),
            conveyance_feature("4", "ACQ", "Active", "Unknown", mapping(line)),
            conveyance_feature(
                "5",
                "ACQ",
                "Active",
                "Acequia Polygon",
                {"type": "Point", "coordinates": [-105.9, 35.7]},
            ),
        ]
    }

    features = parse_conveyance_features(payload)

    assert len(features) == 1
    assert features[0].external_id == "1"
    assert features[0].name == "Acequia Madre"


def test_acequia_line_buffer_distance_and_membership_evidence() -> None:
    line = LineString([(-105.928, 35.681), (-105.927, 35.681)])
    feature = parse_conveyance_features(
        {"features": [conveyance_feature("1", "ACQ", "Active", "Acequia Madre", mapping(line))]}
    )[0]
    near_point = Point(-105.928, 35.6812)
    far_point = Point(-105.928, 35.684)
    session = FakeSession()

    assert distance_point_to_geometry_m(near_point, feature.geometry) < 50
    assert distance_point_to_geometry_m(far_point, feature.geometry) > 50

    created = upsert_acequia_membership_evidence(cast(Session, session), "poi-1", feature)

    assert created is True
    assert any(
        isinstance(item, POIEvidence)
        and item.source_id == NMOSE_ACEQUIA_SOURCE_ID
        and item.evidence_type == "acequia_membership"
        for item in session.added
    )


def pod_feature(object_id: str, county: str, status: str, ditch_name: str) -> dict[str, Any]:
    return {
        "type": "Feature",
        "id": object_id,
        "geometry": {"type": "Point", "coordinates": [-105.928, 35.681]},
        "properties": {
            "OBJECTID": object_id,
            "county": county,
            "pod_status": status,
            "ditch_name": ditch_name,
            "pod_name": " ",
        },
    }


def conveyance_feature(
    object_id: str,
    conveyance_type: str,
    status: str,
    name: str,
    geometry: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "Feature",
        "id": object_id,
        "geometry": geometry,
        "properties": {
            "OBJECTID": object_id,
            "Type": conveyance_type,
            "Status": status,
            "CnvyName": name,
        },
    }


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
