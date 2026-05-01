from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from poi_curator_api.dependencies import get_db_session, get_default_scoring_backend
from poi_curator_api.main import app
from poi_curator_api.routes import admin as admin_routes
from poi_curator_api.routes import public as public_routes
from poi_curator_domain.db import QueryLog
from poi_curator_domain.query_logging import write_query_log_if_enabled
from poi_curator_domain.schemas import (
    NearbyQuerySummary,
    NearbySuggestRequest,
    NearbySuggestResponse,
    QueryLogItem,
    QueryLogListResponse,
    QueryLogResultItem,
    QuerySummary,
    RouteResult,
    RouteSuggestRequest,
    RouteSuggestResponse,
)
from poi_curator_domain.settings import get_settings

client = TestClient(app)


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False
        self.rolled_back = False

    def add(self, row: object) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakeBackend:
    def current_scoring_source(self) -> str:
        return "database"

    def suggest_places(self, db: object, payload: RouteSuggestRequest) -> RouteSuggestResponse:
        del db
        return route_response(payload)

    def suggest_nearby_places(
        self,
        db: object,
        payload: NearbySuggestRequest,
    ) -> NearbySuggestResponse:
        del db
        return NearbySuggestResponse(
            data_source="database",
            query_summary=NearbyQuerySummary(
                travel_mode=payload.travel_mode,
                category=payload.category,
                theme=payload.theme,
                radius_meters=payload.radius_meters,
                limit=payload.limit,
            ),
            results=[],
        )


def route_response(payload: RouteSuggestRequest) -> RouteSuggestResponse:
    return RouteSuggestResponse(
        data_source="database",
        query_summary=QuerySummary(
            travel_mode=payload.travel_mode,
            category=payload.category,
            theme=payload.theme,
            max_detour_meters=payload.max_detour_meters,
            limit=payload.limit,
        ),
        results=[
            RouteResult(
                data_source="database",
                poi_id="poi-log",
                name="Log POI",
                primary_category="history",
                secondary_categories=[],
                category_match_type="primary",
                coordinates=[-105.93, 35.68],
                short_description="desc",
                distance_from_route_m=10,
                estimated_detour_m=20,
                estimated_extra_minutes=1,
                score=91.0,
                score_breakdown={"total": 91.0},
                why_it_matters=[],
                badges=[],
            )
        ],
    )


def fake_db_session() -> Iterator[object]:
    yield object()


def route_payload() -> dict[str, Any]:
    return {
        "route_geometry": {
            "type": "LineString",
            "coordinates": [[-105.94, 35.68], [-105.93, 35.67]],
        },
        "origin": {"name": "A", "coordinates": [-105.94, 35.68]},
        "destination": {"name": "B", "coordinates": [-105.93, 35.67]},
        "travel_mode": "driving",
        "category": "history",
        "max_detour_meters": 1600,
        "max_extra_minutes": 8,
        "limit": 3,
    }


def test_query_log_written_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POI_CURATOR_QUERY_LOGGING", "true")
    get_settings.cache_clear()
    session = FakeSession()
    payload = RouteSuggestRequest.model_validate(route_payload())

    try:
        written = write_query_log_if_enabled(
            session,  # type: ignore[arg-type]
            endpoint="route_suggest",
            request_payload=payload.model_dump(mode="json"),
            scoring_profile_version="v-test",
            response=route_response(payload),
            duration_ms=12,
        )
    finally:
        get_settings.cache_clear()

    assert written is True
    assert session.committed is True
    assert len(session.added) == 1
    log = cast(QueryLog, session.added[0])
    assert log.endpoint == "route_suggest"
    assert log.results[0]["poi_id"] == "poi-log"


def test_query_log_not_written_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POI_CURATOR_QUERY_LOGGING", raising=False)
    get_settings.cache_clear()
    session = FakeSession()
    payload = RouteSuggestRequest.model_validate(route_payload())

    try:
        written = write_query_log_if_enabled(
            session,  # type: ignore[arg-type]
            endpoint="route_suggest",
            request_payload=payload.model_dump(mode="json"),
            scoring_profile_version="v-test",
            response=route_response(payload),
            duration_ms=12,
        )
    finally:
        get_settings.cache_clear()

    assert written is False
    assert session.added == []
    assert session.committed is False


def test_query_logging_failure_does_not_block_response(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_log(*args: object, **kwargs: object) -> bool:
        del args, kwargs
        raise RuntimeError("db down")

    monkeypatch.setattr(public_routes, "write_query_log_if_enabled", fail_log)
    app.dependency_overrides[get_default_scoring_backend] = lambda: FakeBackend()
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        response = client.post("/v1/route/suggest", json=route_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "query logging failed: db down" in capsys.readouterr().err


def test_admin_query_logs_returns_paginated_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POI_CURATOR_ADMIN_KEY", "unit-admin")
    get_settings.cache_clear()

    def fake_list_query_logs(*args: object, **kwargs: object) -> QueryLogListResponse:
        del args
        assert kwargs["endpoint"] == "route_suggest"
        assert kwargs["limit"] == 1
        assert kwargs["offset"] == 2
        return QueryLogListResponse(
            items=[
                QueryLogItem(
                    id="00000000-0000-0000-0000-000000000001",
                    timestamp=datetime(2026, 4, 30, tzinfo=UTC),
                    endpoint="route_suggest",
                    request_payload={"category": "history"},
                    scoring_profile_version="v-test",
                    data_source="database",
                    result_count=1,
                    results=[
                        QueryLogResultItem(
                            poi_id="poi-log",
                            score=91.0,
                            score_breakdown={"total": 91.0},
                            rank=1,
                        )
                    ],
                    duration_ms=12,
                )
            ],
            total=3,
            limit=1,
            offset=2,
        )

    monkeypatch.setattr(admin_routes, "list_query_logs", fake_list_query_logs)
    app.dependency_overrides[get_db_session] = fake_db_session
    try:
        response = client.get(
            "/v1/admin/query-logs?endpoint=route_suggest&limit=1&offset=2",
            headers={"X-POI-Curator-Admin-Key": "unit-admin"},
        )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert payload["items"][0]["results"][0]["poi_id"] == "poi-log"
