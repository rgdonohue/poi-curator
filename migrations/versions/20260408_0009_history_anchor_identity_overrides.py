"""Narrow history anchor identity overrides for Santa Fe validation."""

import sqlalchemy as sa
from alembic import op

revision = "20260408_0009"
down_revision = "20260406_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE poi
        SET display_categories = CASE
                WHEN NOT ('history' = ANY(display_categories))
                THEN array_append(display_categories, 'history')
                ELSE display_categories
            END,
            historical_flag = TRUE,
            updated_at = NOW()
        WHERE canonical_name = 'The Santa Fe Plaza'
        """
    )

    bind = op.get_bind()
    poi_id = bind.execute(
        sa.text("SELECT poi_id FROM poi WHERE canonical_name = 'San Miguel'")
    ).scalar_one_or_none()
    if poi_id is None:
        return

    updated = bind.execute(
        sa.text(
            """
            UPDATE poi_editorial
            SET editorial_title_override = 'San Miguel Chapel'
            WHERE poi_id = :poi_id
            """
        ),
        {"poi_id": poi_id},
    )
    if updated.rowcount:
        return

    bind.execute(
        sa.text(
            """
            INSERT INTO poi_editorial (
                poi_id,
                editorial_status,
                editorial_title_override,
                editorial_description_override,
                editorial_category_override,
                editorial_boost,
                editorial_notes,
                city_pack,
                last_reviewed_at,
                reviewed_by
            )
            VALUES (
                :poi_id,
                'needs_review',
                'San Miguel Chapel',
                NULL,
                NULL,
                0,
                'Narrow PM-directed title alignment for history-anchor evaluation.',
                NULL,
                NULL,
                'migration:20260408_0009'
            )
            """
        ),
        {"poi_id": poi_id},
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE poi
        SET display_categories = array_remove(display_categories, 'history'),
            historical_flag = FALSE,
            updated_at = NOW()
        WHERE canonical_name = 'The Santa Fe Plaza'
          AND normalized_category = 'civic'
        """
    )
    op.execute(
        """
        DELETE FROM poi_editorial
        WHERE poi_id IN (
            SELECT poi_id
            FROM poi
            WHERE canonical_name = 'San Miguel'
        )
          AND editorial_title_override = 'San Miguel Chapel'
          AND reviewed_by = 'migration:20260408_0009'
        """
    )
