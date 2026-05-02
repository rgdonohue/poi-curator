import logging
from datetime import datetime
from functools import lru_cache
from typing import Literal, Protocol

from poi_curator_domain.logging_utils import log_event
from poi_curator_domain.schemas import (
    AdminConflictListResponse,
    AdminCoverageResponse,
    AdminMatchDiagnosticItem,
    AdminMatchLogListResponse,
    AdminPOIDetailResponse,
    AdminPOIEvidenceResponse,
    AdminPOIItem,
    AdminPOIListResponse,
    AdminPOIMapFeatureCollection,
    AdminPOIMapResponse,
    AdminPOIProvenanceResponse,
    AdminThemeMembershipDetailResponse,
    AdminThemeMembershipQueueItem,
    AdminThemeSummaryItem,
    DataSource,
    NearbySuggestRequest,
    NearbySuggestResponse,
    POIDetailResponse,
    RouteSuggestRequest,
    RouteSuggestResponse,
)
from poi_curator_domain.settings import get_settings
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from poi_curator_scoring import engine, query_service

logger = logging.getLogger(__name__)


class ScoringBackend(Protocol):
    def suggest_places(self, db: Session, payload: RouteSuggestRequest) -> RouteSuggestResponse: ...

    def suggest_nearby_places(
        self,
        db: Session,
        payload: NearbySuggestRequest,
    ) -> NearbySuggestResponse: ...

    def get_poi_detail(self, db: Session, poi_id: str) -> POIDetailResponse | None: ...

    def get_admin_queue(
        self,
        db: Session,
        *,
        status: str,
        city: str | None,
    ) -> list[AdminPOIItem]: ...

    def get_admin_poi_list(
        self,
        db: Session,
        *,
        search: str | None,
        category: str | None,
        review_state: str | None,
        source: str | None,
        themes: list[str],
        theme_match: str,
        has_diagnostics: bool | None,
        has_editorial_overrides: bool | None,
        active_only: bool,
        limit: int,
        offset: int,
    ) -> AdminPOIListResponse: ...

    def get_admin_poi_map(
        self,
        db: Session,
        *,
        search: str | None,
        category: str | None,
        review_state: str | None,
        source: str | None,
        themes: list[str],
        theme_match: str,
        has_diagnostics: bool | None,
        has_editorial_overrides: bool | None,
        active_only: bool,
        bbox: str | None,
        limit: int,
    ) -> AdminPOIMapResponse: ...

    def get_admin_poi_detail(
        self,
        db: Session,
        poi_id: str,
    ) -> AdminPOIDetailResponse | None: ...

    def get_admin_poi_evidence(
        self,
        db: Session,
        poi_id: str,
    ) -> AdminPOIEvidenceResponse | None: ...

    def get_admin_match_diagnostics(
        self,
        db: Session,
        *,
        region: str | None,
        source_id: str | None,
        status: str,
        limit: int,
    ) -> list[AdminMatchDiagnosticItem]: ...

    def get_admin_poi_provenance(
        self,
        db: Session,
        poi_id: str,
    ) -> AdminPOIProvenanceResponse | None: ...

    def get_admin_conflicts(
        self,
        db: Session,
        *,
        source_pair: str | None,
        field_name: str | None,
        limit: int,
        offset: int,
    ) -> AdminConflictListResponse: ...

    def get_admin_coverage(self, db: Session) -> AdminCoverageResponse: ...

    def get_admin_match_logs(
        self,
        db: Session,
        *,
        source: str | None,
        decision: str | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
        offset: int,
    ) -> AdminMatchLogListResponse: ...

    def get_admin_theme_summaries(
        self,
        db: Session,
        *,
        city: str | None,
    ) -> list[AdminThemeSummaryItem]: ...

    def get_admin_theme_memberships(
        self,
        db: Session,
        *,
        theme_slug: str | None,
        city: str | None,
        automated_status: str | None,
        review_state: str | None,
        editorial_decision: str | None,
        limit: int,
    ) -> list[AdminThemeMembershipQueueItem]: ...

    def get_admin_theme_membership_detail(
        self,
        db: Session,
        *,
        poi_id: str,
        theme_slug: str,
    ) -> AdminThemeMembershipDetailResponse | None: ...

    def current_scoring_source(self) -> DataSource | Literal["unknown"]: ...


class FixtureScoringBackend:
    def suggest_places(self, db: Session, payload: RouteSuggestRequest) -> RouteSuggestResponse:
        del db
        return engine.suggest_places(payload)

    def suggest_nearby_places(
        self,
        db: Session,
        payload: NearbySuggestRequest,
    ) -> NearbySuggestResponse:
        del db
        return engine.suggest_nearby_places(payload)

    def get_poi_detail(self, db: Session, poi_id: str) -> POIDetailResponse | None:
        del db
        return engine.get_poi_detail(poi_id)

    def get_admin_queue(
        self,
        db: Session,
        *,
        status: str,
        city: str | None,
    ) -> list[AdminPOIItem]:
        del db
        return engine.get_admin_queue(status=status, city=city)

    def get_admin_poi_evidence(
        self,
        db: Session,
        poi_id: str,
    ) -> AdminPOIEvidenceResponse | None:
        del db
        return engine.get_admin_poi_evidence(poi_id)

    def get_admin_poi_list(
        self,
        db: Session,
        *,
        search: str | None,
        category: str | None,
        review_state: str | None,
        source: str | None,
        themes: list[str],
        theme_match: str,
        has_diagnostics: bool | None,
        has_editorial_overrides: bool | None,
        active_only: bool,
        limit: int,
        offset: int,
    ) -> AdminPOIListResponse:
        del (
            db,
            search,
            category,
            review_state,
            source,
            themes,
            theme_match,
            has_diagnostics,
            has_editorial_overrides,
            active_only,
        )
        return AdminPOIListResponse(items=[], total=0, limit=limit, offset=offset)

    def get_admin_poi_map(
        self,
        db: Session,
        *,
        search: str | None,
        category: str | None,
        review_state: str | None,
        source: str | None,
        themes: list[str],
        theme_match: str,
        has_diagnostics: bool | None,
        has_editorial_overrides: bool | None,
        active_only: bool,
        bbox: str | None,
        limit: int,
    ) -> AdminPOIMapResponse:
        del (
            db,
            search,
            category,
            review_state,
            source,
            themes,
            theme_match,
            has_diagnostics,
            has_editorial_overrides,
            active_only,
            bbox,
        )
        return AdminPOIMapResponse(
            feature_collection=AdminPOIMapFeatureCollection(features=[]),
            total_matching=0,
            returned=0,
            truncated=False,
            limit=limit,
        )

    def get_admin_poi_detail(
        self,
        db: Session,
        poi_id: str,
    ) -> AdminPOIDetailResponse | None:
        del db, poi_id
        return None

    def get_admin_match_diagnostics(
        self,
        db: Session,
        *,
        region: str | None,
        source_id: str | None,
        status: str,
        limit: int,
    ) -> list[AdminMatchDiagnosticItem]:
        del db
        return engine.get_admin_match_diagnostics(
            region=region,
            source_id=source_id,
            status=status,
            limit=limit,
        )

    def get_admin_poi_provenance(
        self,
        db: Session,
        poi_id: str,
    ) -> AdminPOIProvenanceResponse | None:
        del db, poi_id
        return None

    def get_admin_conflicts(
        self,
        db: Session,
        *,
        source_pair: str | None,
        field_name: str | None,
        limit: int,
        offset: int,
    ) -> AdminConflictListResponse:
        del db, source_pair, field_name
        return AdminConflictListResponse(items=[], total=0, limit=limit, offset=offset)

    def get_admin_coverage(self, db: Session) -> AdminCoverageResponse:
        del db
        return AdminCoverageResponse(
            by_source={},
            by_source_pair={},
            single_source_gaps={},
            total_pois=0,
        )

    def get_admin_match_logs(
        self,
        db: Session,
        *,
        source: str | None,
        decision: str | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
        offset: int,
    ) -> AdminMatchLogListResponse:
        del db, source, decision, start, end
        return AdminMatchLogListResponse(items=[], total=0, limit=limit, offset=offset)

    def get_admin_theme_summaries(
        self,
        db: Session,
        *,
        city: str | None,
    ) -> list[AdminThemeSummaryItem]:
        del db, city
        return []

    def get_admin_theme_memberships(
        self,
        db: Session,
        *,
        theme_slug: str | None,
        city: str | None,
        automated_status: str | None,
        review_state: str | None,
        editorial_decision: str | None,
        limit: int,
    ) -> list[AdminThemeMembershipQueueItem]:
        del db, theme_slug, city, automated_status, review_state, editorial_decision, limit
        return []

    def get_admin_theme_membership_detail(
        self,
        db: Session,
        *,
        poi_id: str,
        theme_slug: str,
    ) -> AdminThemeMembershipDetailResponse | None:
        del db, poi_id, theme_slug
        return None

    def current_scoring_source(self) -> DataSource | Literal["unknown"]:
        return "fixture_fallback"


class HybridScoringBackend(FixtureScoringBackend):
    def __init__(self, *, allow_fixture_fallback: bool = True) -> None:
        self.allow_fixture_fallback = allow_fixture_fallback
        self.last_query_source: str | None = None

    def suggest_places(self, db: Session, payload: RouteSuggestRequest) -> RouteSuggestResponse:
        try:
            response = query_service.suggest_places(db, payload)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                self._set_last_query_source("database_error")
                raise
            self._set_last_query_source("fixture_fallback_db_error")
            return super().suggest_places(db, payload)
        if response.results or not self.allow_fixture_fallback:
            self._set_last_query_source("database" if response.results else "database_empty")
            return response
        self._set_last_query_source("fixture_fallback_empty_db")
        return super().suggest_places(db, payload)

    def suggest_nearby_places(
        self,
        db: Session,
        payload: NearbySuggestRequest,
    ) -> NearbySuggestResponse:
        try:
            response = query_service.suggest_nearby_places(db, payload)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                self._set_last_query_source("database_error")
                raise
            self._set_last_query_source("fixture_fallback_db_error")
            return super().suggest_nearby_places(db, payload)
        if response.results or not self.allow_fixture_fallback:
            self._set_last_query_source("database" if response.results else "database_empty")
            return response
        self._set_last_query_source("fixture_fallback_empty_db")
        return super().suggest_nearby_places(db, payload)

    def get_poi_detail(self, db: Session, poi_id: str) -> POIDetailResponse | None:
        try:
            detail = query_service.get_poi_detail(db, poi_id)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_poi_detail(db, poi_id)
        if detail is not None or not self.allow_fixture_fallback:
            return detail
        return super().get_poi_detail(db, poi_id)

    def get_admin_queue(
        self,
        db: Session,
        *,
        status: str,
        city: str | None,
    ) -> list[AdminPOIItem]:
        try:
            items = query_service.get_admin_queue(db, status=status, city=city)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_queue(db, status=status, city=city)
        if items or not self.allow_fixture_fallback:
            return items
        return super().get_admin_queue(db, status=status, city=city)

    def get_admin_poi_evidence(
        self,
        db: Session,
        poi_id: str,
    ) -> AdminPOIEvidenceResponse | None:
        try:
            response = query_service.get_admin_poi_evidence(db, poi_id)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_poi_evidence(db, poi_id)
        if response is not None or not self.allow_fixture_fallback:
            return response
        return super().get_admin_poi_evidence(db, poi_id)

    def get_admin_poi_list(
        self,
        db: Session,
        *,
        search: str | None,
        category: str | None,
        review_state: str | None,
        source: str | None,
        themes: list[str],
        theme_match: str,
        has_diagnostics: bool | None,
        has_editorial_overrides: bool | None,
        active_only: bool,
        limit: int,
        offset: int,
    ) -> AdminPOIListResponse:
        try:
            return query_service.get_admin_poi_list(
                db,
                search=search,
                category=category,
                review_state=review_state,
                source=source,
                themes=themes,
                theme_match=theme_match,
                has_diagnostics=has_diagnostics,
                has_editorial_overrides=has_editorial_overrides,
                active_only=active_only,
                limit=limit,
                offset=offset,
            )
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_poi_list(
                db,
                search=search,
                category=category,
                review_state=review_state,
                source=source,
                themes=themes,
                theme_match=theme_match,
                has_diagnostics=has_diagnostics,
                has_editorial_overrides=has_editorial_overrides,
                active_only=active_only,
                limit=limit,
                offset=offset,
            )

    def get_admin_poi_map(
        self,
        db: Session,
        *,
        search: str | None,
        category: str | None,
        review_state: str | None,
        source: str | None,
        themes: list[str],
        theme_match: str,
        has_diagnostics: bool | None,
        has_editorial_overrides: bool | None,
        active_only: bool,
        bbox: str | None,
        limit: int,
    ) -> AdminPOIMapResponse:
        try:
            return query_service.get_admin_poi_map(
                db,
                search=search,
                category=category,
                review_state=review_state,
                source=source,
                themes=themes,
                theme_match=theme_match,
                has_diagnostics=has_diagnostics,
                has_editorial_overrides=has_editorial_overrides,
                active_only=active_only,
                bbox=bbox,
                limit=limit,
            )
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_poi_map(
                db,
                search=search,
                category=category,
                review_state=review_state,
                source=source,
                themes=themes,
                theme_match=theme_match,
                has_diagnostics=has_diagnostics,
                has_editorial_overrides=has_editorial_overrides,
                active_only=active_only,
                bbox=bbox,
                limit=limit,
            )

    def get_admin_poi_detail(
        self,
        db: Session,
        poi_id: str,
    ) -> AdminPOIDetailResponse | None:
        try:
            return query_service.get_admin_poi_detail(db, poi_id)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_poi_detail(db, poi_id)

    def get_admin_match_diagnostics(
        self,
        db: Session,
        *,
        region: str | None,
        source_id: str | None,
        status: str,
        limit: int,
    ) -> list[AdminMatchDiagnosticItem]:
        try:
            items = query_service.get_admin_match_diagnostics(
                db,
                region=region,
                source_id=source_id,
                status=status,
                limit=limit,
            )
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_match_diagnostics(
                db,
                region=region,
                source_id=source_id,
                status=status,
                limit=limit,
            )
        if items or not self.allow_fixture_fallback:
            return items
        return super().get_admin_match_diagnostics(
            db,
            region=region,
            source_id=source_id,
            status=status,
            limit=limit,
        )

    def get_admin_poi_provenance(
        self,
        db: Session,
        poi_id: str,
    ) -> AdminPOIProvenanceResponse | None:
        try:
            return query_service.get_admin_poi_provenance(db, poi_id)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_poi_provenance(db, poi_id)

    def get_admin_conflicts(
        self,
        db: Session,
        *,
        source_pair: str | None,
        field_name: str | None,
        limit: int,
        offset: int,
    ) -> AdminConflictListResponse:
        try:
            return query_service.get_admin_conflicts(
                db,
                source_pair=source_pair,
                field_name=field_name,
                limit=limit,
                offset=offset,
            )
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_conflicts(
                db,
                source_pair=source_pair,
                field_name=field_name,
                limit=limit,
                offset=offset,
            )

    def get_admin_coverage(self, db: Session) -> AdminCoverageResponse:
        try:
            return query_service.get_admin_coverage(db)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_coverage(db)

    def get_admin_match_logs(
        self,
        db: Session,
        *,
        source: str | None,
        decision: str | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
        offset: int,
    ) -> AdminMatchLogListResponse:
        try:
            return query_service.get_admin_match_logs(
                db,
                source=source,
                decision=decision,
                start=start,
                end=end,
                limit=limit,
                offset=offset,
            )
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_match_logs(
                db,
                source=source,
                decision=decision,
                start=start,
                end=end,
                limit=limit,
                offset=offset,
            )

    def get_admin_theme_summaries(
        self,
        db: Session,
        *,
        city: str | None,
    ) -> list[AdminThemeSummaryItem]:
        try:
            items = query_service.get_admin_theme_summaries(db, city=city)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_theme_summaries(db, city=city)
        if items or not self.allow_fixture_fallback:
            return items
        return super().get_admin_theme_summaries(db, city=city)

    def get_admin_theme_memberships(
        self,
        db: Session,
        *,
        theme_slug: str | None,
        city: str | None,
        automated_status: str | None,
        review_state: str | None,
        editorial_decision: str | None,
        limit: int,
    ) -> list[AdminThemeMembershipQueueItem]:
        try:
            items = query_service.get_admin_theme_memberships(
                db,
                theme_slug=theme_slug,
                city=city,
                automated_status=automated_status,
                review_state=review_state,
                editorial_decision=editorial_decision,
                limit=limit,
            )
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_theme_memberships(
                db,
                theme_slug=theme_slug,
                city=city,
                automated_status=automated_status,
                review_state=review_state,
                editorial_decision=editorial_decision,
                limit=limit,
            )
        if items or not self.allow_fixture_fallback:
            return items
        return super().get_admin_theme_memberships(
            db,
            theme_slug=theme_slug,
            city=city,
            automated_status=automated_status,
            review_state=review_state,
            editorial_decision=editorial_decision,
            limit=limit,
        )

    def get_admin_theme_membership_detail(
        self,
        db: Session,
        *,
        poi_id: str,
        theme_slug: str,
    ) -> AdminThemeMembershipDetailResponse | None:
        try:
            response = query_service.get_admin_theme_membership_detail(
                db,
                poi_id=poi_id,
                theme_slug=theme_slug,
            )
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().get_admin_theme_membership_detail(
                db,
                poi_id=poi_id,
                theme_slug=theme_slug,
            )
        if response is not None or not self.allow_fixture_fallback:
            return response
        return super().get_admin_theme_membership_detail(
            db,
            poi_id=poi_id,
            theme_slug=theme_slug,
        )

    def current_scoring_source(self) -> DataSource | Literal["unknown"]:
        if self.last_query_source is None:
            return "unknown"
        if self.last_query_source.startswith("fixture_fallback"):
            return "fixture_fallback"
        if self.last_query_source.startswith("database"):
            return "database"
        return "unknown"

    def _set_last_query_source(self, source: str) -> None:
        self.last_query_source = source
        if source.startswith("fixture_fallback"):
            log_event(
                logger,
                "fixture_fallback_used",
                backend_mode="hybrid",
                source=source,
                allow_fixture_fallback=self.allow_fixture_fallback,
            )


@lru_cache
def get_default_scoring_backend() -> ScoringBackend:
    settings = get_settings()
    return HybridScoringBackend(allow_fixture_fallback=settings.allow_fixture_fallback)


def get_database_scoring_backend(*, allow_fixture_fallback: bool = False) -> ScoringBackend:
    return HybridScoringBackend(allow_fixture_fallback=allow_fixture_fallback)
