"""add evaluation depth to provider configs

Revision ID: 20260414_0004
Revises: 20260316_0003
Create Date: 2026-04-14 18:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260414_0004"
down_revision: str | None = "20260316_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    evaluation_depth = sa.Enum(
        "academic_professional",
        "academic_applied",
        "academic_standard",
        "general_research",
        name="evaluation_depth",
    )
    evaluation_depth.create(bind, checkfirst=True)
    existing_columns = {column["name"] for column in inspect(bind).get_columns("ai_provider_configs")}
    if "evaluation_depth" in existing_columns:
        return
    op.add_column(
        "ai_provider_configs",
        sa.Column(
            "evaluation_depth",
            evaluation_depth,
            nullable=False,
            server_default="academic_standard",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    existing_columns = {column["name"] for column in inspect(bind).get_columns("ai_provider_configs")}
    if "evaluation_depth" in existing_columns:
        op.drop_column("ai_provider_configs", "evaluation_depth")
    evaluation_depth = sa.Enum(
        "academic_professional",
        "academic_applied",
        "academic_standard",
        "general_research",
        name="evaluation_depth",
    )
    evaluation_depth.drop(bind, checkfirst=True)
