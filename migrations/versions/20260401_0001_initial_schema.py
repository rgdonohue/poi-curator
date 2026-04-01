"""Initial schema scaffold."""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision = "20260401_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "ingest_run",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("region", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("canonical_insert_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("canonical_update_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "poi_source_raw",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("source_record_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("geom", Geometry("GEOMETRY", srid=4326), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("license", sa.String(length=128), nullable=True),
        sa.Column("ingest_run_id", sa.Integer(), sa.ForeignKey("ingest_run.id"), nullable=True),
    )
    op.create_index(
        "ix_poi_source_raw_geom",
        "poi_source_raw",
        ["geom"],
        unique=False,
        postgresql_using="gist",
    )

    op.create_table(
        "poi",
        sa.Column("poi_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("geom", Geometry("GEOMETRY", srid=4326), nullable=False),
        sa.Column("centroid", Geometry("POINT", srid=4326), nullable=False),
        sa.Column("city", sa.String(length=128), nullable=False),
        sa.Column("region", sa.String(length=128), nullable=False),
        sa.Column("country", sa.String(length=128), nullable=False),
        sa.Column("normalized_category", sa.String(length=64), nullable=False),
        sa.Column("normalized_subcategory", sa.String(length=128), nullable=True),
        sa.Column("display_categories", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("primary_source", sa.String(length=64), nullable=False),
        sa.Column("osm_id", sa.String(length=128), nullable=True),
        sa.Column("wikidata_id", sa.String(length=128), nullable=True),
        sa.Column("wikipedia_title", sa.String(length=255), nullable=True),
        sa.Column("heritage_id", sa.String(length=128), nullable=True),
        sa.Column("raw_tag_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("historical_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cultural_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("scenic_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("infrastructure_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("food_identity_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("walk_relevance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("drive_relevance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("base_significance_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "review_status",
            sa.String(length=32),
            nullable=False,
            server_default="needs_review",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uq_poi_slug"),
    )
    op.create_index("ix_poi_geom", "poi", ["geom"], unique=False, postgresql_using="gist")
    op.create_index("ix_poi_city_region_category", "poi", ["city", "region", "normalized_category"])

    op.create_table(
        "poi_signals",
        sa.Column(
            "poi_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("poi.poi_id"),
            primary_key=True,
        ),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("has_wikidata", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_wikipedia", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "has_official_heritage_match",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("osm_tag_richness", sa.Float(), nullable=False, server_default="0"),
        sa.Column("description_quality", sa.Float(), nullable=False, server_default="0"),
        sa.Column("entity_type_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("local_identity_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("interpretive_value_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("genericity_penalty", sa.Float(), nullable=False, server_default="0"),
        sa.Column("editorial_priority_seed", sa.Float(), nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "poi_editorial",
        sa.Column(
            "poi_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("poi.poi_id"),
            primary_key=True,
        ),
        sa.Column(
            "editorial_status",
            sa.String(length=32),
            nullable=False,
            server_default="needs_review",
        ),
        sa.Column("editorial_title_override", sa.String(length=255), nullable=True),
        sa.Column("editorial_description_override", sa.Text(), nullable=True),
        sa.Column("editorial_category_override", sa.String(length=64), nullable=True),
        sa.Column("editorial_boost", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("editorial_notes", sa.Text(), nullable=True),
        sa.Column("city_pack", sa.String(length=128), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("poi_editorial")
    op.drop_table("poi_signals")
    op.drop_index("ix_poi_city_region_category", table_name="poi")
    op.drop_index("ix_poi_geom", table_name="poi", postgresql_using="gist")
    op.drop_table("poi")
    op.drop_index("ix_poi_source_raw_geom", table_name="poi_source_raw", postgresql_using="gist")
    op.drop_table("poi_source_raw")
    op.drop_table("ingest_run")
