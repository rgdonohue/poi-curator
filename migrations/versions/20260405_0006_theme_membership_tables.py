"""Add theme definitions, memberships, evidence links, and editorial overrides."""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260405_0006"
down_revision = "20260404_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "theme_definition",
        sa.Column("theme_slug", sa.String(length=64), primary_key=True),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("region_scope", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_query_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "poi_theme_membership",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "poi_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("poi.poi_id"),
            nullable=False,
        ),
        sa.Column(
            "theme_slug",
            sa.String(length=64),
            sa.ForeignKey("theme_definition.theme_slug"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("assignment_basis", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rationale_summary", sa.Text(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("poi_id", "theme_slug", name="uq_poi_theme_membership_poi_theme"),
    )
    op.create_index("ix_poi_theme_membership_poi_id", "poi_theme_membership", ["poi_id"])
    op.create_index(
        "ix_poi_theme_membership_theme_slug",
        "poi_theme_membership",
        ["theme_slug"],
    )

    op.create_table(
        "poi_theme_membership_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "membership_id",
            sa.Integer(),
            sa.ForeignKey("poi_theme_membership.id"),
            nullable=False,
        ),
        sa.Column(
            "poi_evidence_id",
            sa.Integer(),
            sa.ForeignKey("poi_evidence.id"),
            nullable=False,
        ),
        sa.Column("contribution_type", sa.String(length=32), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "membership_id",
            "poi_evidence_id",
            name="uq_poi_theme_membership_evidence_membership_evidence",
        ),
    )
    op.create_index(
        "ix_poi_theme_membership_evidence_membership_id",
        "poi_theme_membership_evidence",
        ["membership_id"],
    )

    op.create_table(
        "poi_theme_editorial",
        sa.Column(
            "poi_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("poi.poi_id"),
            primary_key=True,
        ),
        sa.Column(
            "theme_slug",
            sa.String(length=64),
            sa.ForeignKey("theme_definition.theme_slug"),
            primary_key=True,
        ),
        sa.Column("editorial_decision", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    now = datetime.now(UTC)
    op.bulk_insert(
        sa.table(
            "theme_definition",
            sa.column("theme_slug", sa.String(length=64)),
            sa.column("label", sa.String(length=128)),
            sa.column("description", sa.Text()),
            sa.column("region_scope", sa.String(length=128)),
            sa.column("is_active", sa.Boolean()),
            sa.column("is_query_active", sa.Boolean()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "theme_slug": "water",
                "label": "Water",
                "description": (
                    "Places that reveal acequia infrastructure, canal traces, water corridors, "
                    "and the civic landscape shaped by water."
                ),
                "region_scope": "santa-fe",
                "is_active": True,
                "is_query_active": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "theme_slug": "rail",
                "label": "Rail",
                "description": (
                    "Places that reveal rail infrastructure, labor, circulation, and adaptive reuse."
                ),
                "region_scope": "santa-fe",
                "is_active": True,
                "is_query_active": False,
                "created_at": now,
                "updated_at": now,
            },
            {
                "theme_slug": "public_memory",
                "label": "Public Memory",
                "description": (
                    "Places where public commemoration, civic-historic framing, and staged memory "
                    "are legible in the landscape."
                ),
                "region_scope": "santa-fe",
                "is_active": True,
                "is_query_active": False,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("poi_theme_editorial")
    op.drop_index(
        "ix_poi_theme_membership_evidence_membership_id",
        table_name="poi_theme_membership_evidence",
    )
    op.drop_table("poi_theme_membership_evidence")
    op.drop_index("ix_poi_theme_membership_theme_slug", table_name="poi_theme_membership")
    op.drop_index("ix_poi_theme_membership_poi_id", table_name="poi_theme_membership")
    op.drop_table("poi_theme_membership")
    op.drop_table("theme_definition")
