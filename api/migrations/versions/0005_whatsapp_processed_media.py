"""whatsapp media handled before batching

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-09 00:00:00.000000+00:00
"""
from collections.abc import Sequence

from alembic import op

revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE whatsapp_messages SET status = 'processed' "
        "WHERE direction = 'inbound' AND type IN ('image', 'document') AND status = 'received'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE whatsapp_messages SET status = 'received' "
        "WHERE direction = 'inbound' AND status = 'processed'"
    )