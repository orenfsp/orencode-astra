"""Audit log of changes made through the platform.

Revision ID: 20261028_09
Revises: 20261028_08
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261028_09"
down_revision: str | None = "20261028_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("role", sa.String(length=40), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("entity_id", sa.String(length=60), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=True),
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_entity_type", "audit_log", ["entity_type"])


def downgrade() -> None:
    for name in ("ix_audit_log_entity_type", "ix_audit_log_action", "ix_audit_log_user_id", "ix_audit_log_created_at"):
        op.drop_index(name, table_name="audit_log")
    op.drop_table("audit_log")
