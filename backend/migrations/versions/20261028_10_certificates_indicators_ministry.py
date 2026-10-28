"""Participation certificates, indicator documents and the ministry role.

Revision ID: 20261028_10
Revises: 20261028_09
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261028_10"
down_revision: str | None = "20261028_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("INSERT INTO roles (name) SELECT 'ministry' WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = 'ministry')")
    op.create_table(
        "certificates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.String(length=40), nullable=False, unique=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(length=255), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_certificates_code", "certificates", ["code"], unique=True)
    op.create_index("ix_certificates_athlete_id", "certificates", ["athlete_id"])
    op.create_table(
        "indicator_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("indicator", sa.String(length=40), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_indicator_documents_indicator", "indicator_documents", ["indicator"])


def downgrade() -> None:
    op.drop_index("ix_indicator_documents_indicator", table_name="indicator_documents")
    op.drop_table("indicator_documents")
    op.drop_index("ix_certificates_athlete_id", table_name="certificates")
    op.drop_index("ix_certificates_code", table_name="certificates")
    op.drop_table("certificates")
    op.execute("DELETE FROM roles WHERE name = 'ministry'")
