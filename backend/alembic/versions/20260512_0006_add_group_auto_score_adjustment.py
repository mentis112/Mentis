"""add group auto score adjustment flag

Revision ID: 20260512_0006
Revises: 20260417_0005
Create Date: 2026-05-12 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260512_0006"
down_revision: str | None = "20260417_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assignment_groups",
        sa.Column(
            "enable_auto_score_adjustment",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.alter_column("assignment_groups", "enable_auto_score_adjustment", server_default=None)


def downgrade() -> None:
    op.drop_column("assignment_groups", "enable_auto_score_adjustment")
