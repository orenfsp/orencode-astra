"""Expand competition status storage length.

Revision ID: 20261027_04
Revises: 20261027_03
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261027_04"
down_revision: str | None = "20261027_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "competitions",
        "status",
        existing_type=sa.String(length=17),
        type_=sa.String(length=19),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE competitions SET status = 'upcoming' "
        "WHERE status = 'registration_closed'"
    )
    op.alter_column(
        "competitions",
        "status",
        existing_type=sa.String(length=19),
        type_=sa.String(length=17),
        existing_nullable=False,
    )
