"""declarative_findings

Revision ID: e8312ab56401
Revises: d7119ba3049c
Create Date: 2026-10-27 23:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8312ab56401'
down_revision: Union[str, Sequence[str], None] = 'd7119ba3049c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add clause_ref, severity, and signal_type to findings."""
    op.add_column('findings', sa.Column('clause_ref', sa.JSON(), nullable=True))
    op.add_column('findings', sa.Column('severity', sa.String(length=20), server_default='medium', nullable=True))
    op.add_column('findings', sa.Column('signal_type', sa.String(length=20), server_default='rule', nullable=True))


def downgrade() -> None:
    """Drop clause_ref, severity, and signal_type from findings."""
    op.drop_column('findings', 'signal_type')
    op.drop_column('findings', 'severity')
    op.drop_column('findings', 'clause_ref')
