"""add ollama provider enum value

Revision ID: 20260316_0002
Revises: 20260313_0001
Create Date: 2026-03-16 14:45:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260316_0002"
down_revision: str | None = "20260313_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE provider_name ADD VALUE IF NOT EXISTS 'OLLAMA'")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM instructors WHERE api_provider::text = 'ollama')
                OR EXISTS (SELECT 1 FROM ai_provider_configs WHERE provider_name::text = 'ollama')
                OR EXISTS (SELECT 1 FROM provider_usage_logs WHERE provider_name::text = 'ollama')
                OR EXISTS (SELECT 1 FROM evaluation_results WHERE provider_name::text = 'ollama')
            THEN
                RAISE EXCEPTION 'Cannot downgrade while ollama provider rows still exist';
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TYPE provider_name RENAME TO provider_name_old")
    op.execute("CREATE TYPE provider_name AS ENUM ('OPENAI', 'GEMINI', 'DEEPSEEK')")
    op.execute(
        """
        ALTER TABLE instructors
        ALTER COLUMN api_provider TYPE provider_name
        USING (
            CASE
                WHEN api_provider IS NULL THEN NULL
                ELSE api_provider::text::provider_name
            END
        )
        """
    )
    op.execute(
        """
        ALTER TABLE ai_provider_configs
        ALTER COLUMN provider_name TYPE provider_name
        USING provider_name::text::provider_name
        """
    )
    op.execute(
        """
        ALTER TABLE provider_usage_logs
        ALTER COLUMN provider_name TYPE provider_name
        USING provider_name::text::provider_name
        """
    )
    op.execute(
        """
        ALTER TABLE evaluation_results
        ALTER COLUMN provider_name TYPE provider_name
        USING (
            CASE
                WHEN provider_name IS NULL THEN NULL
                ELSE provider_name::text::provider_name
            END
        )
        """
    )
    op.execute("DROP TYPE provider_name_old")
