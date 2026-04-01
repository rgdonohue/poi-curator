"""Add raw source integrity, provenance linkage, and affinity hint cleanup."""

import sqlalchemy as sa
from alembic import op

revision = "20260401_0002"
down_revision = "20260401_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("poi", "walk_relevance", new_column_name="walk_affinity_hint")
    op.alter_column("poi", "drive_relevance", new_column_name="drive_affinity_hint")

    op.add_column(
        "poi_source_raw",
        sa.Column(
            "canonical_poi_id",
            sa.UUID(as_uuid=False),
            sa.ForeignKey("poi.poi_id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_poi_source_raw_current_record",
        "poi_source_raw",
        ["source_name", "source_record_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )
    op.create_index(
        "ix_poi_centroid",
        "poi",
        ["centroid"],
        unique=False,
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index("ix_poi_centroid", table_name="poi", postgresql_using="gist")
    op.drop_index("ix_poi_source_raw_current_record", table_name="poi_source_raw")
    op.drop_column("poi_source_raw", "canonical_poi_id")

    op.alter_column("poi", "drive_affinity_hint", new_column_name="drive_relevance")
    op.alter_column("poi", "walk_affinity_hint", new_column_name="walk_relevance")
