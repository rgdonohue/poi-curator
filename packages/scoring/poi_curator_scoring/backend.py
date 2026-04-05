from functools import lru_cache
from typing import Protocol

from poi_curator_domain.schemas import (
    AdminAliasFromDiagnosticRequest,
    AdminAliasMutationResponse,
    AdminCreateAliasRequest,
    AdminMatchDiagnosticItem,
    AdminPOIEvidenceResponse,
    AdminPOIItem,
    AdminPOIPatchRequest,
    AdminPOIPatchResponse,
    AdminResolveDiagnosticRequest,
    AdminSuppressDiagnosticRequest,
    NearbySuggestRequest,
    NearbySuggestResponse,
    POIDetailResponse,
    RouteSuggestRequest,
    RouteSuggestResponse,
)
from poi_curator_editorial import service as editorial_service
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from poi_curator_scoring import engine, query_service


class ScoringBackend(Protocol):
    def suggest_places(self, db: Session, payload: RouteSuggestRequest) -> RouteSuggestResponse:
        ...

    def suggest_nearby_places(
        self,
        db: Session,
        payload: NearbySuggestRequest,
    ) -> NearbySuggestResponse:
        ...

    def get_poi_detail(self, db: Session, poi_id: str) -> POIDetailResponse | None:
        ...

    def get_admin_queue(
        self,
        db: Session,
        *,
        status: str,
        city: str | None,
    ) -> list[AdminPOIItem]:
        ...

    def get_admin_poi_evidence(
        self,
        db: Session,
        poi_id: str,
    ) -> AdminPOIEvidenceResponse | None:
        ...

    def get_admin_match_diagnostics(
        self,
        db: Session,
        *,
        region: str | None,
        source_id: str | None,
        status: str,
        limit: int,
    ) -> list[AdminMatchDiagnosticItem]:
        ...

    def patch_admin_poi(
        self,
        db: Session,
        poi_id: str,
        payload: AdminPOIPatchRequest,
    ) -> AdminPOIPatchResponse | None:
        ...

    def resolve_match_diagnostic(
        self,
        db: Session,
        diagnostic_id: int,
        payload: AdminResolveDiagnosticRequest,
    ) -> AdminMatchDiagnosticItem | None:
        ...

    def create_alias_from_diagnostic(
        self,
        db: Session,
        diagnostic_id: int,
        payload: AdminAliasFromDiagnosticRequest,
    ) -> AdminMatchDiagnosticItem | None:
        ...

    def suppress_match_diagnostic(
        self,
        db: Session,
        diagnostic_id: int,
        payload: AdminSuppressDiagnosticRequest,
    ) -> AdminMatchDiagnosticItem | None:
        ...

    def add_poi_alias(
        self,
        db: Session,
        poi_id: str,
        payload: AdminCreateAliasRequest,
    ) -> AdminAliasMutationResponse | None:
        ...


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

    def patch_admin_poi(
        self,
        db: Session,
        poi_id: str,
        payload: AdminPOIPatchRequest,
    ) -> AdminPOIPatchResponse | None:
        del db
        return AdminPOIPatchResponse(
            poi_id=poi_id,
            applied_changes=payload.model_dump(exclude_none=True),
            persisted=False,
            message="Scaffold response only. Persistence will be added with the editorial layer.",
        )

    def resolve_match_diagnostic(
        self,
        db: Session,
        diagnostic_id: int,
        payload: AdminResolveDiagnosticRequest,
    ) -> AdminMatchDiagnosticItem | None:
        del db, diagnostic_id, payload
        return None

    def create_alias_from_diagnostic(
        self,
        db: Session,
        diagnostic_id: int,
        payload: AdminAliasFromDiagnosticRequest,
    ) -> AdminMatchDiagnosticItem | None:
        del db, diagnostic_id, payload
        return None

    def suppress_match_diagnostic(
        self,
        db: Session,
        diagnostic_id: int,
        payload: AdminSuppressDiagnosticRequest,
    ) -> AdminMatchDiagnosticItem | None:
        del db, diagnostic_id, payload
        return None

    def add_poi_alias(
        self,
        db: Session,
        poi_id: str,
        payload: AdminCreateAliasRequest,
    ) -> AdminAliasMutationResponse | None:
        del db, poi_id, payload
        return None


class HybridScoringBackend(FixtureScoringBackend):
    def __init__(self, *, allow_fixture_fallback: bool = True) -> None:
        self.allow_fixture_fallback = allow_fixture_fallback

    def suggest_places(self, db: Session, payload: RouteSuggestRequest) -> RouteSuggestResponse:
        try:
            response = query_service.suggest_places(db, payload)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().suggest_places(db, payload)
        if response.results or not self.allow_fixture_fallback:
            return response
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
                raise
            return super().suggest_nearby_places(db, payload)
        if response.results or not self.allow_fixture_fallback:
            return response
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

    def patch_admin_poi(
        self,
        db: Session,
        poi_id: str,
        payload: AdminPOIPatchRequest,
    ) -> AdminPOIPatchResponse | None:
        try:
            response = query_service.patch_admin_poi(db, poi_id, payload)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().patch_admin_poi(db, poi_id, payload)
        if response is not None or not self.allow_fixture_fallback:
            return response
        return super().patch_admin_poi(db, poi_id, payload)

    def resolve_match_diagnostic(
        self,
        db: Session,
        diagnostic_id: int,
        payload: AdminResolveDiagnosticRequest,
    ) -> AdminMatchDiagnosticItem | None:
        try:
            item = editorial_service.resolve_match_diagnostic(db, diagnostic_id, payload)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().resolve_match_diagnostic(db, diagnostic_id, payload)
        if item is not None or not self.allow_fixture_fallback:
            return item
        return super().resolve_match_diagnostic(db, diagnostic_id, payload)

    def create_alias_from_diagnostic(
        self,
        db: Session,
        diagnostic_id: int,
        payload: AdminAliasFromDiagnosticRequest,
    ) -> AdminMatchDiagnosticItem | None:
        try:
            item = editorial_service.create_alias_from_diagnostic(db, diagnostic_id, payload)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().create_alias_from_diagnostic(db, diagnostic_id, payload)
        if item is not None or not self.allow_fixture_fallback:
            return item
        return super().create_alias_from_diagnostic(db, diagnostic_id, payload)

    def suppress_match_diagnostic(
        self,
        db: Session,
        diagnostic_id: int,
        payload: AdminSuppressDiagnosticRequest,
    ) -> AdminMatchDiagnosticItem | None:
        try:
            item = editorial_service.suppress_match_diagnostic(db, diagnostic_id, payload)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().suppress_match_diagnostic(db, diagnostic_id, payload)
        if item is not None or not self.allow_fixture_fallback:
            return item
        return super().suppress_match_diagnostic(db, diagnostic_id, payload)

    def add_poi_alias(
        self,
        db: Session,
        poi_id: str,
        payload: AdminCreateAliasRequest,
    ) -> AdminAliasMutationResponse | None:
        try:
            response = editorial_service.add_poi_alias(db, poi_id, payload)
        except SQLAlchemyError:
            if not self.allow_fixture_fallback:
                raise
            return super().add_poi_alias(db, poi_id, payload)
        if response is not None or not self.allow_fixture_fallback:
            return response
        return super().add_poi_alias(db, poi_id, payload)


@lru_cache
def get_default_scoring_backend() -> ScoringBackend:
    return HybridScoringBackend()


def get_database_scoring_backend() -> ScoringBackend:
    return HybridScoringBackend(allow_fixture_fallback=False)
