from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from poi_curator_domain.db import QueryLog
from poi_curator_domain.schemas import (
    DataSource,
    NearbyResult,
    NearbySuggestResponse,
    QueryLogItem,
    QueryLogListResponse,
    QueryLogResultItem,
    RouteResult,
    RouteSuggestResponse,
)
from poi_curator_domain.settings import get_settings

SuggestResponse = RouteSuggestResponse | NearbySuggestResponse


def write_query_log_if_enabled(
    db: Session,
    *,
    endpoint: str,
    request_payload: dict[str, Any],
    scoring_profile_version: str,
    response: SuggestResponse,
    duration_ms: int,
) -> bool:
    if not get_settings().query_logging:
        return False

    log = QueryLog(
        timestamp=datetime.now(UTC),
        endpoint=endpoint,
        request_payload=request_payload,
        scoring_profile_version=scoring_profile_version,
        data_source=response.data_source,
        result_count=len(response.results),
        results=serialize_results(response),
        duration_ms=duration_ms,
    )
    db.add(log)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return True


def serialize_results(response: SuggestResponse) -> list[dict[str, Any]]:
    results: list[RouteResult | NearbyResult]
    if isinstance(response, RouteSuggestResponse):
        results = list(response.results)
    else:
        results = list(response.results)
    return [
        {
            "poi_id": result.poi_id,
            "score": result.score,
            "score_breakdown": result.score_breakdown,
            "rank": rank,
        }
        for rank, result in enumerate(results, start=1)
    ]


def list_query_logs(
    db: Session,
    *,
    endpoint: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    min_result_count: int | None = None,
    max_result_count: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> QueryLogListResponse:
    query: Select[tuple[QueryLog]] = select(QueryLog)
    filters = []
    if endpoint is not None:
        filters.append(QueryLog.endpoint == endpoint)
    if start is not None:
        filters.append(QueryLog.timestamp >= start)
    if end is not None:
        filters.append(QueryLog.timestamp <= end)
    if min_result_count is not None:
        filters.append(QueryLog.result_count >= min_result_count)
    if max_result_count is not None:
        filters.append(QueryLog.result_count <= max_result_count)
    if filters:
        query = query.where(and_(*filters))

    count_query = select(func.count()).select_from(query.subquery())
    total = int(db.scalar(count_query) or 0)
    rows = db.scalars(
        query.order_by(QueryLog.timestamp.desc()).offset(offset).limit(limit)
    ).all()
    return QueryLogListResponse(
        items=[query_log_item_from_row(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def query_log_item_from_row(row: QueryLog) -> QueryLogItem:
    return QueryLogItem(
        id=row.id,
        timestamp=row.timestamp,
        endpoint=row.endpoint,
        request_payload=row.request_payload,
        scoring_profile_version=row.scoring_profile_version,
        data_source=cast(DataSource, row.data_source),
        result_count=row.result_count,
        results=[
            QueryLogResultItem(
                poi_id=str(item["poi_id"]),
                score=float(item["score"]),
                score_breakdown=item.get("score_breakdown"),
                rank=int(item["rank"]),
            )
            for item in row.results
        ],
        duration_ms=row.duration_ms,
    )
