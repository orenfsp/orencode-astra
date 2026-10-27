"""Create competitions table.

Revision ID: 20261027_01
Revises:
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261027_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "competitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("discipline", sa.String(length=255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "registration_open",
                "upcoming",
                "completed",
                name="competition_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("competitions")
