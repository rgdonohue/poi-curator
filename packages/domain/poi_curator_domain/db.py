from collections.abc import Generator
from datetime import datetime
from functools import lru_cache
from uuid import uuid4

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from poi_curator_domain.settings import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def dispose_engine() -> None:
    get_engine().dispose()


class IngestRun(Base):
    __tablename__ = "ingest_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    canonical_insert_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    canonical_update_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_records: Mapped[list["POISourceRaw"]] = relationship(back_populates="ingest_run")


class POISourceRaw(Base):
    __tablename__ = "poi_source_raw"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    raw_payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    geom = mapped_column(Geometry("GEOMETRY", srid=4326), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    license: Mapped[str | None] = mapped_column(String(128))
    ingest_run_id: Mapped[int | None] = mapped_column(ForeignKey("ingest_run.id"))
    canonical_poi_id: Mapped[str | None] = mapped_column(ForeignKey("poi.poi_id"))

    ingest_run: Mapped[IngestRun | None] = relationship(back_populates="raw_records")
    canonical_poi: Mapped["POI | None"] = relationship(back_populates="raw_sources")


class POI(Base):
    __tablename__ = "poi"

    poi_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    geom = mapped_column(Geometry("GEOMETRY", srid=4326), nullable=False)
    centroid = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    country: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_category: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_subcategory: Mapped[str | None] = mapped_column(String(128))
    display_categories: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    short_description: Mapped[str | None] = mapped_column(Text)
    primary_source: Mapped[str] = mapped_column(String(64), nullable=False)
    osm_id: Mapped[str | None] = mapped_column(String(128))
    wikidata_id: Mapped[str | None] = mapped_column(String(128))
    wikipedia_title: Mapped[str | None] = mapped_column(String(255))
    heritage_id: Mapped[str | None] = mapped_column(String(128))
    raw_tag_summary_json: Mapped[dict | None] = mapped_column(JSONB)
    historical_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cultural_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scenic_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    infrastructure_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    food_identity_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    walk_affinity_hint: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    drive_affinity_hint: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    base_significance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), default="needs_review", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    raw_sources: Mapped[list[POISourceRaw]] = relationship(back_populates="canonical_poi")
    aliases: Mapped[list["POIAlias"]] = relationship(back_populates="poi")
    evidence_items: Mapped[list["POIEvidence"]] = relationship(back_populates="poi")
    match_diagnostics: Mapped[list["OfficialMatchDiagnostic"]] = relationship(
        back_populates="poi",
        foreign_keys="OfficialMatchDiagnostic.matched_poi_id",
    )
    signals: Mapped["POISignals | None"] = relationship(back_populates="poi", uselist=False)
    editorial: Mapped["POIEditorial | None"] = relationship(back_populates="poi", uselist=False)


class POISignals(Base):
    __tablename__ = "poi_signals"

    poi_id: Mapped[str] = mapped_column(ForeignKey("poi.poi_id"), primary_key=True)
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    has_wikidata: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_wikipedia: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_official_heritage_match: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    official_corroboration_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    district_membership_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    institutional_identity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    osm_tag_richness: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    description_quality: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    entity_type_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    local_identity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    interpretive_value_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    genericity_penalty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    editorial_priority_seed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    poi: Mapped[POI] = relationship(back_populates="signals")


class POIEditorial(Base):
    __tablename__ = "poi_editorial"

    poi_id: Mapped[str] = mapped_column(ForeignKey("poi.poi_id"), primary_key=True)
    editorial_status: Mapped[str] = mapped_column(
        String(32),
        default="needs_review",
        nullable=False,
    )
    editorial_title_override: Mapped[str | None] = mapped_column(String(255))
    editorial_description_override: Mapped[str | None] = mapped_column(Text)
    editorial_category_override: Mapped[str | None] = mapped_column(String(64))
    editorial_boost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    editorial_notes: Mapped[str | None] = mapped_column(Text)
    city_pack: Mapped[str | None] = mapped_column(String(128))
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(255))

    poi: Mapped[POI] = relationship(back_populates="editorial")


class SourceRegistry(Base):
    __tablename__ = "source_registry"

    source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    trust_class: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text)
    license_notes: Mapped[str | None] = mapped_column(Text)
    crawl_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ingest_method: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    evidence_items: Mapped[list["POIEvidence"]] = relationship(back_populates="source")
    match_diagnostics: Mapped[list["OfficialMatchDiagnostic"]] = relationship(
        back_populates="source"
    )


class POIAlias(Base):
    __tablename__ = "poi_alias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poi_id: Mapped[str] = mapped_column(ForeignKey("poi.poi_id"), nullable=False)
    alias_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False)
    alias_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    poi: Mapped[POI] = relationship(back_populates="aliases")


class POIEvidence(Base):
    __tablename__ = "poi_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    poi_id: Mapped[str] = mapped_column(ForeignKey("poi.poi_id"), nullable=False)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.source_id"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_label: Mapped[str | None] = mapped_column(String(255))
    evidence_text: Mapped[str | None] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(Text)
    external_record_id: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    raw_evidence_json: Mapped[dict | None] = mapped_column(JSONB)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    poi: Mapped[POI] = relationship(back_populates="evidence_items")
    source: Mapped[SourceRegistry] = relationship(back_populates="evidence_items")


class OfficialMatchDiagnostic(Base):
    __tablename__ = "official_match_diagnostic"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.source_id"), nullable=False)
    region: Mapped[str] = mapped_column(String(128), nullable=False)
    external_record_id: Mapped[str | None] = mapped_column(String(255))
    external_name: Mapped[str] = mapped_column(String(255), nullable=False)
    matched_poi_id: Mapped[str | None] = mapped_column(ForeignKey("poi.poi_id"))
    resolved_poi_id: Mapped[str | None] = mapped_column(ForeignKey("poi.poi_id"))
    best_candidate_name: Mapped[str | None] = mapped_column(String(255))
    best_similarity: Mapped[float | None] = mapped_column(Float)
    match_strategy: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    resolution_method: Mapped[str | None] = mapped_column(String(32))
    raw_payload_json: Mapped[dict | None] = mapped_column(JSONB)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    source: Mapped[SourceRegistry] = relationship(back_populates="match_diagnostics")
    poi: Mapped[POI | None] = relationship(
        back_populates="match_diagnostics",
        foreign_keys=[matched_poi_id],
    )
    resolved_poi: Mapped[POI | None] = relationship(foreign_keys=[resolved_poi_id])
