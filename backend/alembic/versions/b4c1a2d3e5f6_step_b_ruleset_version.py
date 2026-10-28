"""step_b_ruleset_version

Revision ID: b4c1a2d3e5f6
Revises: e8312ab56401
Create Date: 2026-10-28 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4c1a2d3e5f6"
down_revision: Union[str, Sequence[str], None] = "e8312ab56401"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add advisory, ruleset_version, and rule_engine_mode columns using batch alter for dialect neutrality."""
    with op.batch_alter_table("findings") as batch_op:
        batch_op.add_column(sa.Column("advisory", sa.Boolean(), nullable=True, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("ruleset_version", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("rule_engine_mode", sa.String(length=32), nullable=True))

    with op.batch_alter_table("applications") as batch_op:
        batch_op.add_column(sa.Column("ruleset_version", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("rule_engine_mode", sa.String(length=32), nullable=True))


def downgrade() -> None:
    """Drop ruleset_version, rule_engine_mode, and advisory columns using batch alter."""
    with op.batch_alter_table("applications") as batch_op:
        batch_op.drop_column("rule_engine_mode")
        batch_op.drop_column("ruleset_version")

    with op.batch_alter_table("findings") as batch_op:
        batch_op.drop_column("rule_engine_mode")
        batch_op.drop_column("ruleset_version")
        batch_op.drop_column("advisory")
