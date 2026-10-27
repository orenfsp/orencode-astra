"""Reference dictionaries, full competition model, profiles and PD consent.

Revision ID: 20261027_05
Revises: 20261027_04
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261027_05"
down_revision: str | None = "20261027_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DISCIPLINES = [
    ("algorithmic", "Программирование алгоритмическое"),
    ("product", "Программирование продуктовое"),
    ("security", "Программирование систем информационной безопасности"),
    ("ai", "Программирование систем искусственного интеллекта"),
    ("robotics", "Программирование робототехники"),
    ("uav", "Программирование беспилотных авиационных систем"),
]
COMPETITION_TYPES = ["Чемпионат", "Первенство", "Кубок", "Всероссийские соревнования", "Официальные соревнования"]
AGE_GROUPS = [
    ("Мальчики, девочки (10–13 лет)", 10, 13),
    ("Юноши, девушки (14–17 лет)", 14, 17),
    ("Мужчины, женщины (16 лет и старше)", 16, None),
]
MUNICIPALITIES = [
    "г. Оренбург", "г. Орск", "г. Новотроицк", "г. Бузулук", "г. Бугуруслан", "г. Медногорск",
    "Гайский городской округ", "Сорочинский городской округ", "Кувандыкский городской округ",
    "Соль-Илецкий городской округ", "Ясненский городской округ", "Абдулинский городской округ",
    "Оренбургский район", "Бузулукский район", "Саракташский район", "Новосергиевский район",
]
JUDGE_POSITIONS = [
    "Главный судья", "Заместитель главного судьи", "Главный секретарь",
    "Заместитель главного секретаря", "Судья", "Технический специалист",
]

# Старые свободные названия дисциплин из первых миграций и демо-данных.
LEGACY_DISCIPLINES = {
    "Алгоритмическое программирование": "algorithmic",
    "Продуктовое программирование": "product",
    "Программирование систем искусственного интеллекта": "ai",
    "Программирование систем информационной безопасности": "security",
    "Программирование робототехники": "robotics",
    "Программирование беспилотных авиационных систем": "uav",
}


def upgrade() -> None:
    disciplines = op.create_table(
        "disciplines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=40), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    competition_types = op.create_table(
        "competition_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    age_groups = op.create_table(
        "age_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("min_age", sa.Integer(), nullable=False),
        sa.Column("max_age", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    municipalities = op.create_table(
        "municipalities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False, unique=True),
    )
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column(
            "org_type",
            sa.Enum("school", "university", "college", "sport_school", "club", "other", name="organization_type", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("municipality_id", sa.Integer(), sa.ForeignKey("municipalities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    judge_positions = op.create_table(
        "judge_positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False, unique=True),
    )

    op.bulk_insert(disciplines, [{"code": code, "name": name, "sort_order": index} for index, (code, name) in enumerate(DISCIPLINES)])
    op.bulk_insert(competition_types, [{"name": name, "is_active": True} for name in COMPETITION_TYPES])
    op.bulk_insert(age_groups, [{"name": name, "min_age": low, "max_age": high, "sort_order": index} for index, (name, low, high) in enumerate(AGE_GROUPS)])
    op.bulk_insert(municipalities, [{"name": name} for name in MUNICIPALITIES])
    op.bulk_insert(judge_positions, [{"name": name} for name in JUDGE_POSITIONS])

    # --- competitions: свободный текст -> справочники и перечисления ---
    op.add_column("competitions", sa.Column("discipline_id", sa.Integer(), nullable=True))
    op.add_column("competitions", sa.Column("competition_type_id", sa.Integer(), nullable=True))
    op.add_column(
        "competitions",
        sa.Column("level", sa.Enum("regional", "interregional", "all_russian", name="competition_level", native_enum=False, create_constraint=True), nullable=False, server_default="regional"),
    )
    op.add_column("competitions", sa.Column("end_date", sa.Date(), nullable=True))
    op.add_column(
        "competitions",
        sa.Column("format", sa.Enum("offline", "online", "mixed", name="competition_format", native_enum=False, create_constraint=True), nullable=False, server_default="offline"),
    )
    op.add_column(
        "competitions",
        sa.Column("calendar_plan", sa.Enum("none", "regional", "ekp", name="calendar_plan", native_enum=False, create_constraint=True), nullable=False, server_default="none"),
    )
    op.add_column("competitions", sa.Column("calendar_plan_number", sa.String(length=60), nullable=True))
    op.add_column("competitions", sa.Column("regulation_filename", sa.String(length=255), nullable=True))
    op.add_column("competitions", sa.Column("regulation_path", sa.String(length=255), nullable=True))

    for legacy_name, code in LEGACY_DISCIPLINES.items():
        op.execute(
            sa.text("UPDATE competitions SET discipline_id = (SELECT id FROM disciplines WHERE code = :code) WHERE discipline = :name")
            .bindparams(code=code, name=legacy_name)
        )
    op.execute("UPDATE competitions SET discipline_id = (SELECT id FROM disciplines WHERE code = 'algorithmic') WHERE discipline_id IS NULL")
    op.execute("UPDATE competitions SET competition_type_id = (SELECT id FROM competition_types WHERE name = 'Официальные соревнования')")
    op.execute("UPDATE competitions SET end_date = date")
    op.execute(
        "UPDATE competitions SET format = CASE event_format "
        "WHEN 'Онлайн' THEN 'online' WHEN 'Гибридный' THEN 'mixed' WHEN 'Смешанный' THEN 'mixed' ELSE 'offline' END"
    )

    op.alter_column("competitions", "discipline_id", nullable=False)
    op.alter_column("competitions", "competition_type_id", nullable=False)
    op.alter_column("competitions", "end_date", nullable=False)
    op.alter_column("competitions", "level", server_default=None)
    op.alter_column("competitions", "format", server_default=None)
    op.alter_column("competitions", "calendar_plan", server_default=None)
    op.create_foreign_key("fk_competitions_discipline_id", "competitions", "disciplines", ["discipline_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_competitions_competition_type_id", "competitions", "competition_types", ["competition_type_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_competitions_discipline_id", "competitions", ["discipline_id"])
    op.drop_column("competitions", "discipline")
    op.drop_column("competitions", "event_format")

    op.create_table(
        "competition_age_groups",
        sa.Column("competition_id", sa.Integer(), sa.ForeignKey("competitions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("age_group_id", sa.Integer(), sa.ForeignKey("age_groups.id", ondelete="RESTRICT"), primary_key=True),
    )
    op.execute(
        "INSERT INTO competition_age_groups (competition_id, age_group_id) "
        "SELECT competitions.id, age_groups.id FROM competitions CROSS JOIN age_groups"
    )

    # --- профили и согласие на обработку ПД ---
    op.add_column("users", sa.Column("pd_consent_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "profiles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("last_name", sa.String(length=120), nullable=False),
        sa.Column("first_name", sa.String(length=120), nullable=False),
        sa.Column("middle_name", sa.String(length=120), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", sa.Enum("male", "female", name="gender", native_enum=False, create_constraint=True), nullable=True),
        sa.Column("municipality_id", sa.Integer(), sa.ForeignKey("municipalities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "athlete_profiles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("start_year", sa.Integer(), nullable=True),
        sa.Column(
            "training_stage",
            sa.Enum("initial", "training", "improvement", "highest", name="training_stage", native_enum=False, create_constraint=True),
            nullable=True,
        ),
        sa.Column("guardian_name", sa.String(length=255), nullable=True),
        sa.Column("guardian_phone", sa.String(length=40), nullable=True),
        sa.Column("guardian_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rusada_completed_on", sa.Date(), nullable=True),
        sa.Column("rusada_certificate_url", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_athlete_profiles_organization_id", "athlete_profiles", ["organization_id"])
    op.create_table(
        "athlete_disciplines",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("athlete_profiles.user_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("discipline_id", sa.Integer(), sa.ForeignKey("disciplines.id", ondelete="RESTRICT"), primary_key=True),
    )
    op.create_table(
        "coach_profiles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_coach_profiles_organization_id", "coach_profiles", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_coach_profiles_organization_id", table_name="coach_profiles")
    op.drop_table("coach_profiles")
    op.drop_table("athlete_disciplines")
    op.drop_index("ix_athlete_profiles_organization_id", table_name="athlete_profiles")
    op.drop_table("athlete_profiles")
    op.drop_table("profiles")
    op.drop_column("users", "pd_consent_at")

    op.drop_table("competition_age_groups")
    op.add_column("competitions", sa.Column("discipline", sa.String(length=255), nullable=True))
    op.add_column("competitions", sa.Column("event_format", sa.String(length=120), nullable=True))
    op.execute("UPDATE competitions SET discipline = (SELECT name FROM disciplines WHERE disciplines.id = competitions.discipline_id)")
    op.execute("UPDATE competitions SET event_format = CASE format WHEN 'online' THEN 'Онлайн' WHEN 'mixed' THEN 'Гибридный' ELSE 'Очно' END")
    op.alter_column("competitions", "discipline", nullable=False)
    op.alter_column("competitions", "event_format", nullable=False)
    op.drop_index("ix_competitions_discipline_id", table_name="competitions")
    op.drop_constraint("fk_competitions_competition_type_id", "competitions", type_="foreignkey")
    op.drop_constraint("fk_competitions_discipline_id", "competitions", type_="foreignkey")
    for column in ("regulation_path", "regulation_filename", "calendar_plan_number", "calendar_plan", "format", "end_date", "level", "competition_type_id", "discipline_id"):
        op.drop_column("competitions", column)

    op.drop_table("judge_positions")
    op.drop_table("organizations")
    op.drop_table("municipalities")
    op.drop_table("age_groups")
    op.drop_table("competition_types")
    op.drop_table("disciplines")
