"""initial schema

Revision ID: 20260313_0001
Revises:
Create Date: 2026-03-13 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

from app.db.base import Base

# revision identifiers, used by Alembic.
revision: str = "20260313_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
