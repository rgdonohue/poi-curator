"""Add POI aliases and official match diagnostics."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260404_0004"
down_revision = "20260403_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "poi_alias",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "poi_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("poi.poi_id"),
            nullable=False,
        ),
        sa.Column("alias_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_alias", sa.String(length=255), nullable=False),
        sa.Column("alias_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("poi_id", "normalized_alias", name="uq_poi_alias_poi_normalized"),
    )
    op.create_index("ix_poi_alias_poi_id", "poi_alias", ["poi_id"])
    op.create_index("ix_poi_alias_normalized_alias", "poi_alias", ["normalized_alias"])

    op.create_table(
        "official_match_diagnostic",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "source_id",
            sa.String(length=128),
            sa.ForeignKey("source_registry.source_id"),
            nullable=False,
        ),
        sa.Column("region", sa.String(length=128), nullable=False),
        sa.Column("external_record_id", sa.String(length=255), nullable=True),
        sa.Column("external_name", sa.String(length=255), nullable=False),
        sa.Column(
            "matched_poi_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("poi.poi_id"),
            nullable=True,
        ),
        sa.Column("best_candidate_name", sa.String(length=255), nullable=True),
        sa.Column("best_similarity", sa.Float(), nullable=True),
        sa.Column("match_strategy", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_official_match_diagnostic_source_region",
        "official_match_diagnostic",
        ["source_id", "region"],
    )
    op.create_index(
        "ix_official_match_diagnostic_status",
        "official_match_diagnostic",
        ["status"],
    )
    op.create_index(
        "ix_official_match_diagnostic_matched_poi_id",
        "official_match_diagnostic",
        ["matched_poi_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_official_match_diagnostic_matched_poi_id",
        table_name="official_match_diagnostic",
    )
    op.drop_index("ix_official_match_diagnostic_status", table_name="official_match_diagnostic")
    op.drop_index(
        "ix_official_match_diagnostic_source_region",
        table_name="official_match_diagnostic",
    )
    op.drop_table("official_match_diagnostic")

    op.drop_index("ix_poi_alias_normalized_alias", table_name="poi_alias")
    op.drop_index("ix_poi_alias_poi_id", table_name="poi_alias")
    op.drop_table("poi_alias")
