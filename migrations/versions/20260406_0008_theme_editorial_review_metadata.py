"""Add theme editorial review metadata and allow reviewed-without-override rows."""

from alembic import op
import sqlalchemy as sa

revision = "20260406_0008"
down_revision = "20260406_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "poi_theme_editorial",
        "editorial_decision",
        existing_type=sa.String(length=32),
        nullable=True,
    )
    op.add_column(
        "poi_theme_editorial",
        sa.Column("reviewed_membership_computed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("poi_theme_editorial", "reviewed_membership_computed_at")
    op.alter_column(
        "poi_theme_editorial",
        "editorial_decision",
        existing_type=sa.String(length=32),
        nullable=False,
    )
