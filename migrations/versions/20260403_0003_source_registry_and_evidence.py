"""Add source registry, POI evidence, and corroboration signal fields."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260403_0003"
down_revision = "20260401_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "poi_signals",
        sa.Column("official_corroboration_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "poi_signals",
        sa.Column("district_membership_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "poi_signals",
        sa.Column("institutional_identity_score", sa.Float(), nullable=False, server_default="0"),
    )

    op.create_table(
        "source_registry",
        sa.Column("source_id", sa.String(length=128), primary_key=True),
        sa.Column("organization_name", sa.String(length=255), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("trust_class", sa.String(length=64), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("license_notes", sa.Text(), nullable=True),
        sa.Column("crawl_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ingest_method", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "poi_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("evidence_key", sa.String(length=255), nullable=False),
        sa.Column(
            "poi_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("poi.poi_id"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.String(length=128),
            sa.ForeignKey("source_registry.source_id"),
            nullable=False,
        ),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_label", sa.String(length=255), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("evidence_url", sa.Text(), nullable=True),
        sa.Column("external_record_id", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("raw_evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("evidence_key", name="uq_poi_evidence_key"),
    )
    op.create_index("ix_poi_evidence_poi_id", "poi_evidence", ["poi_id"])
    op.create_index("ix_poi_evidence_source_id", "poi_evidence", ["source_id"])
    op.create_index(
        "ix_poi_evidence_poi_source_type",
        "poi_evidence",
        ["poi_id", "source_id", "evidence_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_poi_evidence_poi_source_type", table_name="poi_evidence")
    op.drop_index("ix_poi_evidence_source_id", table_name="poi_evidence")
    op.drop_index("ix_poi_evidence_poi_id", table_name="poi_evidence")
    op.drop_table("poi_evidence")
    op.drop_table("source_registry")

    op.drop_column("poi_signals", "institutional_identity_score")
    op.drop_column("poi_signals", "district_membership_score")
    op.drop_column("poi_signals", "official_corroboration_score")
