"""Expand competitions for detail and management flows.

Revision ID: 20261027_03
Revises: 20261027_02
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261027_03"
down_revision: str | None = "20261027_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "competitions",
        sa.Column("description", sa.Text(), nullable=False, server_default="Описание уточняется."),
    )
    op.add_column(
        "competitions",
        sa.Column("event_format", sa.String(length=120), nullable=False, server_default="Очно"),
    )
    op.add_column(
        "competitions",
        sa.Column("registration_start", sa.Date(), nullable=True),
    )
    op.add_column(
        "competitions",
        sa.Column("registration_end", sa.Date(), nullable=True),
    )
    op.add_column(
        "competitions",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.execute(
        """
        UPDATE competitions
        SET description = CASE id
                WHEN 1 THEN 'Региональный турнир для школьников и студентов с задачами по алгоритмам и структурам данных.'
                WHEN 2 THEN 'Командная разработка цифрового продукта по задаче от индустриального партнёра.'
                WHEN 3 THEN 'Соревнование по анализу данных и построению моделей машинного обучения.'
                ELSE description
            END,
            event_format = CASE id
                WHEN 2 THEN 'Гибридный'
                WHEN 3 THEN 'Онлайн'
                ELSE event_format
            END,
            registration_start = date - 30,
            registration_end = date - 5
        """
    )
    op.alter_column("competitions", "registration_start", nullable=False)
    op.alter_column("competitions", "registration_end", nullable=False)
    op.alter_column("competitions", "description", server_default=None)
    op.alter_column("competitions", "event_format", server_default=None)

    op.drop_constraint("competition_status", "competitions", type_="check")
    op.create_check_constraint(
        "competition_status",
        "competitions",
        "status IN ('draft', 'registration_open', 'registration_closed', 'upcoming', 'ongoing', 'completed')",
    )


def downgrade() -> None:
    op.execute("UPDATE competitions SET status = 'upcoming' WHERE status NOT IN ('registration_open', 'upcoming', 'completed')")
    op.drop_constraint("competition_status", "competitions", type_="check")
    op.create_check_constraint(
        "competition_status",
        "competitions",
        "status IN ('registration_open', 'upcoming', 'completed')",
    )
    op.drop_column("competitions", "is_archived")
    op.drop_column("competitions", "registration_end")
    op.drop_column("competitions", "registration_start")
    op.drop_column("competitions", "event_format")
    op.drop_column("competitions", "description")
