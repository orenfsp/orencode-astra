"""Coach links, judge categories and panels, sport ranks, rank norms, notifications.

Revision ID: 20261028_07
Revises: 20261028_06
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261028_07"
down_revision: str | None = "20261028_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


LINK_STATUS = ("pending", "active", "suspended", "ended", "declined")
JUDGE_CATEGORY = ("young", "third", "second", "first", "all_russian")
SPORT_RANK = ("youth_3", "youth_2", "youth_1", "third", "second", "first", "kms")
REQUEST_KIND = ("assign", "confirm")
REQUEST_STATUS = ("pending", "approved", "rejected")

# Ориентиры ЕВСК по умолчанию — федерация правит их через API.
RANK_NORMS = [
    ("all_russian", 3, "kms"), ("all_russian", 8, "first"), ("all_russian", 16, "second"),
    ("interregional", 3, "first"), ("interregional", 6, "second"), ("interregional", 10, "third"),
    ("regional", 3, "second"), ("regional", 6, "third"), ("regional", 10, "youth_1"),
]


def upgrade() -> None:
    op.add_column("users", sa.Column("email_notifications", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column("users", "email_notifications", server_default=None)

    op.create_table(
        "coach_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", _enum("link_status", *LINK_STATUS), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_coach_links_coach_id", "coach_links", ["coach_id"])
    op.create_index("ix_coach_links_athlete_id", "coach_links", ["athlete_id"])
    op.create_table(
        "coach_link_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("link_id", sa.Integer(), sa.ForeignKey("coach_links.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", _enum("link_status", *LINK_STATUS), nullable=False),
        sa.Column("changed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_coach_link_events_link_id", "coach_link_events", ["link_id"])

    op.create_table(
        "judge_profiles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("category", _enum("judge_category", *JUDGE_CATEGORY), nullable=True),
        sa.Column("category_assigned_on", sa.Date(), nullable=True),
        sa.Column("category_expires_on", sa.Date(), nullable=True),
        sa.Column("order_ref", sa.String(length=120), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "judge_category_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("judge_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", _enum("judge_category", *JUDGE_CATEGORY), nullable=False),
        sa.Column("kind", _enum("request_kind", *REQUEST_KIND), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("status", _enum("request_status", *REQUEST_STATUS), nullable=False),
        sa.Column("moderator_comment", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_judge_category_requests_judge_id", "judge_category_requests", ["judge_id"])
    op.create_index("ix_judge_category_requests_status", "judge_category_requests", ["status"])
    op.create_table(
        "judge_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("competition_id", sa.Integer(), sa.ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("judge_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position_id", sa.Integer(), sa.ForeignKey("judge_positions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("competition_id", "judge_id", name="uq_judge_assignments_competition_judge"),
    )
    op.create_index("ix_judge_assignments_competition_id", "judge_assignments", ["competition_id"])
    op.create_index("ix_judge_assignments_judge_id", "judge_assignments", ["judge_id"])

    op.create_table(
        "rank_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", _enum("sport_rank", *SPORT_RANK), nullable=False),
        sa.Column("kind", _enum("request_kind", *REQUEST_KIND), nullable=False),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_role", sa.String(length=40), nullable=False),
        sa.Column("status", _enum("request_status", *REQUEST_STATUS), nullable=False),
        sa.Column("moderator_comment", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_rank_requests_athlete_id", "rank_requests", ["athlete_id"])
    op.create_index("ix_rank_requests_status", "rank_requests", ["status"])
    op.create_table(
        "athlete_ranks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", _enum("sport_rank", *SPORT_RANK), nullable=False),
        sa.Column("assigned_on", sa.Date(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=False),
        sa.Column("order_ref", sa.String(length=120), nullable=False),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("rank_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_athlete_ranks_athlete_id", "athlete_ranks", ["athlete_id"])
    op.create_index("ix_athlete_ranks_expires_on", "athlete_ranks", ["expires_on"])
    rank_norms = op.create_table(
        "rank_norms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("level", _enum("competition_level", "regional", "interregional", "all_russian"), nullable=False),
        sa.Column("max_place", sa.Integer(), nullable=False),
        sa.Column("rank", _enum("sport_rank", *SPORT_RANK), nullable=False),
    )
    op.bulk_insert(rank_norms, [{"level": level, "max_place": place, "rank": rank} for level, place, rank in RANK_NORMS])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.String(length=1000), nullable=False),
        sa.Column("link", sa.String(length=255), nullable=True),
        sa.Column("dedupe_key", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("emailed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("rank_norms")
    op.drop_table("athlete_ranks")
    op.drop_table("rank_requests")
    op.drop_table("judge_assignments")
    op.drop_table("judge_category_requests")
    op.drop_table("judge_profiles")
    op.drop_table("coach_link_events")
    op.drop_table("coach_links")
    op.drop_column("users", "email_notifications")
