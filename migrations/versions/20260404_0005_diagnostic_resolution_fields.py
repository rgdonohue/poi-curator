"""Add editorial resolution fields for official match diagnostics."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260404_0005"
down_revision = "20260404_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "official_match_diagnostic",
        sa.Column(
            "resolved_poi_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey("poi.poi_id"),
            nullable=True,
        ),
    )
    op.add_column(
        "official_match_diagnostic",
        sa.Column("resolution_method", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "official_match_diagnostic",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "official_match_diagnostic",
        sa.Column("reviewed_by", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_official_match_diagnostic_resolved_poi_id",
        "official_match_diagnostic",
        ["resolved_poi_id"],
    )
    op.execute(
        "UPDATE official_match_diagnostic SET status = 'unreviewed' WHERE status = 'unmatched'"
    )


def downgrade() -> None:
    op.drop_index(
        "ix_official_match_diagnostic_resolved_poi_id",
        table_name="official_match_diagnostic",
    )
    op.drop_column("official_match_diagnostic", "reviewed_by")
    op.drop_column("official_match_diagnostic", "reviewed_at")
    op.drop_column("official_match_diagnostic", "resolution_method")
    op.drop_column("official_match_diagnostic", "resolved_poi_id")
