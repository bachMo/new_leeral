"""prescription line extra fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07 00:00:00.000000+00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('prescription_lines', sa.Column('dci_read', sa.Text(), nullable=True))
    op.add_column('prescription_lines', sa.Column('dci_lexicon', sa.Text(), nullable=True))
    op.add_column('prescription_lines', sa.Column('form', sa.Text(), nullable=True))
    op.add_column('prescription_lines', sa.Column('instructions', sa.Text(), nullable=True))
    op.add_column('prescription_lines', sa.Column('raw_read', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('prescription_lines', 'raw_read')
    op.drop_column('prescription_lines', 'instructions')
    op.drop_column('prescription_lines', 'form')
    op.drop_column('prescription_lines', 'dci_lexicon')
    op.drop_column('prescription_lines', 'dci_read')
