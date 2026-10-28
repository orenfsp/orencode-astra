"""Protocol forms from appendix 5 of the sport rules: task marks, time and judges' scores.

Revision ID: 20261028_11
Revises: 20261028_10
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261028_11"
down_revision: str | None = "20261028_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("competitions", sa.Column("task_count", sa.Integer(), nullable=True))
    op.add_column("results", sa.Column("task_marks", sa.JSON(), nullable=True))
    op.add_column("results", sa.Column("penalty_minutes", sa.Integer(), nullable=True))
    op.add_column("results", sa.Column("judge_scores", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("results", "judge_scores")
    op.drop_column("results", "penalty_minutes")
    op.drop_column("results", "task_marks")
    op.drop_column("competitions", "task_count")
