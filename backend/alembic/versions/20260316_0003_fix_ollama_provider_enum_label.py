"""fix ollama provider enum label casing

Revision ID: 20260316_0003
Revises: 20260316_0002
Create Date: 2026-03-16 14:58:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260316_0003"
down_revision: str | None = "20260316_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'provider_name' AND e.enumlabel = 'ollama'
            ) THEN
                ALTER TYPE provider_name RENAME VALUE 'ollama' TO 'OLLAMA';
            ELSIF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'provider_name' AND e.enumlabel = 'OLLAMA'
            ) THEN
                ALTER TYPE provider_name ADD VALUE 'OLLAMA';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON e.enumtypid = t.oid
                WHERE t.typname = 'provider_name' AND e.enumlabel = 'OLLAMA'
            ) THEN
                ALTER TYPE provider_name RENAME VALUE 'OLLAMA' TO 'ollama';
            END IF;
        END $$;
        """
    )
