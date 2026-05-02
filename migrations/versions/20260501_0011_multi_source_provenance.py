"""add multi-source field provenance and match logs

Revision ID: 20260501_0011
Revises: 20260430_0010
Create Date: 2026-05-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260501_0011"
down_revision: str | None = "20260430_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "poi_field_provenance",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "poi_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("poi.poi_id"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_canonical", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_poi_field_provenance_poi_field",
        "poi_field_provenance",
        ["poi_id", "field_name"],
    )
    op.create_index(
        "ix_poi_field_provenance_source",
        "poi_field_provenance",
        ["source_id"],
    )

    op.create_table(
        "poi_match_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "canonical_poi_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("poi.poi_id"),
            nullable=True,
        ),
        sa.Column("candidate_source", sa.String(length=128), nullable=False),
        sa.Column("candidate_external_id", sa.String(length=255), nullable=True),
        sa.Column("match_strategy", sa.String(length=64), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_poi_match_log_poi", "poi_match_log", ["canonical_poi_id"])
    op.create_index(
        "ix_poi_match_log_source_decision",
        "poi_match_log",
        ["candidate_source", "decision"],
    )

    op.execute(
        """
        INSERT INTO poi_field_provenance
            (poi_id, field_name, source_id, value, confidence, observed_at, is_canonical)
        SELECT poi_id, 'name', 'osm', to_jsonb(canonical_name), 0.80, updated_at, true
        FROM poi
        WHERE primary_source = 'osm_overpass'
        """
    )
    op.execute(
        """
        INSERT INTO poi_field_provenance
            (poi_id, field_name, source_id, value, confidence, observed_at, is_canonical)
        SELECT
            poi_id,
            'primary_category',
            'osm',
            to_jsonb(normalized_category),
            0.75,
            updated_at,
            true
        FROM poi
        WHERE primary_source = 'osm_overpass'
        """
    )
    op.execute(
        """
        INSERT INTO poi_field_provenance
            (poi_id, field_name, source_id, value, confidence, observed_at, is_canonical)
        SELECT
            poi_id,
            'coordinates',
            'osm',
            jsonb_build_object('lon', ST_X(centroid::geometry), 'lat', ST_Y(centroid::geometry)),
            0.75,
            updated_at,
            true
        FROM poi
        WHERE primary_source = 'osm_overpass'
        """
    )
    op.execute(
        """
        INSERT INTO poi_field_provenance
            (poi_id, field_name, source_id, value, confidence, observed_at, is_canonical)
        SELECT
            poi_id,
            'short_description',
            'osm',
            to_jsonb(short_description),
            0.60,
            updated_at,
            true
        FROM poi
        WHERE primary_source = 'osm_overpass' AND short_description IS NOT NULL
        """
    )
    op.execute(
        """
        INSERT INTO poi_field_provenance
            (poi_id, field_name, source_id, value, confidence, observed_at, is_canonical)
        SELECT poi_id, 'wikidata_id', 'wikidata', to_jsonb(wikidata_id), 0.90, updated_at, true
        FROM poi
        WHERE wikidata_id IS NOT NULL
        """
    )
    op.execute(
        """
        INSERT INTO poi_field_provenance
            (poi_id, field_name, source_id, value, confidence, observed_at, is_canonical)
        SELECT
            poi_id,
            'wikipedia_title',
            'wikidata',
            to_jsonb(wikipedia_title),
            0.85,
            updated_at,
            true
        FROM poi
        WHERE wikipedia_title IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE VIEW poi_field_conflicts AS
        SELECT
            poi_id,
            field_name,
            array_agg(DISTINCT source_id ORDER BY source_id) AS source_ids,
            count(DISTINCT value) AS distinct_value_count,
            max(observed_at) AS last_observed_at
        FROM poi_field_provenance
        GROUP BY poi_id, field_name
        HAVING count(DISTINCT value) > 1
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS poi_field_conflicts")
    op.drop_index("ix_poi_match_log_source_decision", table_name="poi_match_log")
    op.drop_index("ix_poi_match_log_poi", table_name="poi_match_log")
    op.drop_table("poi_match_log")
    op.drop_index("ix_poi_field_provenance_source", table_name="poi_field_provenance")
    op.drop_index("ix_poi_field_provenance_poi_field", table_name="poi_field_provenance")
    op.drop_table("poi_field_provenance")
