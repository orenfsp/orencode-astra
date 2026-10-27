"""Applications, results and protocol publication.

Revision ID: 20261028_06
Revises: 20261027_05
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261028_06"
down_revision: str | None = "20261027_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("competitions", sa.Column("protocol_published_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("competition_id", sa.Integer(), sa.ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("age_group_id", sa.Integer(), sa.ForeignKey("age_groups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_role", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", "withdrawn", name="application_status", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("moderator_comment", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("competition_id", "athlete_id", name="uq_applications_competition_athlete"),
    )
    op.create_index("ix_applications_competition_id", "applications", ["competition_id"])
    op.create_index("ix_applications_athlete_id", "applications", ["athlete_id"])
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_table(
        "results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("score", sa.Numeric(10, 2), nullable=True),
        sa.Column("result_status", sa.Enum("ok", "dns", "dsq", name="result_status", native_enum=False, create_constraint=True), nullable=False),
        sa.Column("place", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("results")
    op.drop_index("ix_applications_status", table_name="applications")
    op.drop_index("ix_applications_athlete_id", table_name="applications")
    op.drop_index("ix_applications_competition_id", table_name="applications")
    op.drop_table("applications")
    op.drop_column("competitions", "protocol_published_at")
