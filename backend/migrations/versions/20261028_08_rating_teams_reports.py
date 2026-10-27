"""Rating points and settings, sanctions, regional teams, athlete end year.

Revision ID: 20261028_08
Revises: 20261028_07
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261028_08"
down_revision: str | None = "20261028_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEVEL = ("regional", "interregional", "all_russian")
# Базовые значения из кейса; федерация меняет их в настройках рейтинга.
RATING_POINTS = [
    ("Чемпионат России", "all_russian", "Чемпионат", 100, 80, 60),
    ("Первенство России", "all_russian", "Первенство", 80, 60, 40),
    ("Межрегиональные (в т. ч. окружные)", "interregional", None, 60, 45, 30),
    ("Региональные (чемпионат, первенство области)", "regional", None, 40, 30, 20),
]


def upgrade() -> None:
    op.add_column("athlete_profiles", sa.Column("end_year", sa.Integer(), nullable=True))

    op.create_table(
        "rating_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stability_coefficient", sa.Numeric(4, 2), nullable=False),
        sa.Column("stability_min_podiums", sa.Integer(), nullable=False),
    )
    op.execute("INSERT INTO rating_settings (stability_coefficient, stability_min_podiums) VALUES (1.2, 2)")
    op.create_table(
        "rating_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("level", sa.Enum(*LEVEL, name="competition_level", native_enum=False, create_constraint=True), nullable=False),
        sa.Column("competition_type_id", sa.Integer(), sa.ForeignKey("competition_types.id", ondelete="CASCADE"), nullable=True),
        sa.Column("first", sa.Integer(), nullable=False),
        sa.Column("second", sa.Integer(), nullable=False),
        sa.Column("third", sa.Integer(), nullable=False),
        sa.UniqueConstraint("level", "competition_type_id", name="uq_rating_points_level_type"),
    )
    for title, level, type_name, first, second, third in RATING_POINTS:
        type_id = "(SELECT id FROM competition_types WHERE name = :type_name)" if type_name else "NULL"
        op.execute(
            sa.text(f"INSERT INTO rating_points (title, level, competition_type_id, first, second, third) VALUES (:title, :level, {type_id}, :first, :second, :third)")
            .bindparams(**{"title": title, "level": level, "first": first, "second": second, "third": third, **({"type_name": type_name} if type_name else {})})
        )

    op.create_table(
        "sanctions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.Enum("disqualification", "suspension", name="sanction_kind", native_enum=False, create_constraint=True), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sanctions_athlete_id", "sanctions", ["athlete_id"])

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("season", sa.Integer(), nullable=False),
        sa.Column("age_group_id", sa.Integer(), sa.ForeignKey("age_groups.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "team_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("is_reserve", sa.Boolean(), nullable=False),
        sa.Column("rating_place", sa.Integer(), nullable=True),
        sa.Column("rating_points", sa.Numeric(8, 2), nullable=True),
        sa.UniqueConstraint("team_id", "athlete_id", name="uq_team_members_team_athlete"),
    )
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_team_members_team_id", table_name="team_members")
    op.drop_table("team_members")
    op.drop_table("teams")
    op.drop_index("ix_sanctions_athlete_id", table_name="sanctions")
    op.drop_table("sanctions")
    op.drop_table("rating_points")
    op.drop_table("rating_settings")
    op.drop_column("athlete_profiles", "end_year")
