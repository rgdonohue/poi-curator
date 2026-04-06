"""Activate rail as a query-available theme."""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "20260406_0007"
down_revision = "20260405_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            update theme_definition
            set is_query_active = true,
                updated_at = :updated_at
            where theme_slug = 'rail'
            """
        ).bindparams(updated_at=datetime.now(UTC))
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            update theme_definition
            set is_query_active = false,
                updated_at = :updated_at
            where theme_slug = 'rail'
            """
        ).bindparams(updated_at=datetime.now(UTC))
    )
