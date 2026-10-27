from __future__ import annotations

from datetime import date
from enum import Enum

from sqlalchemy import Boolean, Column, Date, Enum as SqlEnum, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _enum(enum_class: type[Enum], name: str) -> SqlEnum:
    return SqlEnum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda enum: [item.value for item in enum],
    )


class CompetitionStatus(str, Enum):
    DRAFT = "draft"
    REGISTRATION_OPEN = "registration_open"
    REGISTRATION_CLOSED = "registration_closed"
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    COMPLETED = "completed"


class CompetitionLevel(str, Enum):
    """Статус соревнования по правилам вида спорта."""

    REGIONAL = "regional"
    INTERREGIONAL = "interregional"
    ALL_RUSSIAN = "all_russian"


class CompetitionFormat(str, Enum):
    OFFLINE = "offline"
    ONLINE = "online"
    MIXED = "mixed"


class CalendarPlan(str, Enum):
    """В какой календарный план включено соревнование."""

    NONE = "none"
    REGIONAL = "regional"
    EKP = "ekp"


class OrganizationType(str, Enum):
    SCHOOL = "school"
    UNIVERSITY = "university"
    COLLEGE = "college"
    SPORT_SCHOOL = "sport_school"
    CLUB = "club"
    OTHER = "other"


class Discipline(Base):
    __tablename__ = "disciplines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class CompetitionType(Base):
    """Справочник типов соревнований (чемпионат, первенство, кубок…), пополняется федерацией."""

    __tablename__ = "competition_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AgeGroup(Base):
    __tablename__ = "age_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    min_age: Mapped[int] = mapped_column(Integer)
    max_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Municipality(Base):
    __tablename__ = "municipalities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    org_type: Mapped[OrganizationType] = mapped_column(_enum(OrganizationType, "organization_type"))
    municipality_id: Mapped[int | None] = mapped_column(ForeignKey("municipalities.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    municipality: Mapped[Municipality | None] = relationship(lazy="selectin")


class JudgePosition(Base):
    __tablename__ = "judge_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)


competition_age_groups = Table(
    "competition_age_groups",
    Base.metadata,
    Column("competition_id", ForeignKey("competitions.id", ondelete="CASCADE"), primary_key=True),
    Column("age_group_id", ForeignKey("age_groups.id", ondelete="RESTRICT"), primary_key=True),
)


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id", ondelete="RESTRICT"), index=True)
    competition_type_id: Mapped[int] = mapped_column(ForeignKey("competition_types.id", ondelete="RESTRICT"))
    level: Mapped[CompetitionLevel] = mapped_column(_enum(CompetitionLevel, "competition_level"))
    date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[CompetitionFormat] = mapped_column(_enum(CompetitionFormat, "competition_format"))
    registration_start: Mapped[date] = mapped_column(Date, nullable=False)
    registration_end: Mapped[date] = mapped_column(Date, nullable=False)
    calendar_plan: Mapped[CalendarPlan] = mapped_column(_enum(CalendarPlan, "calendar_plan"), default=CalendarPlan.NONE)
    calendar_plan_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    regulation_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    regulation_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[CompetitionStatus] = mapped_column(_enum(CompetitionStatus, "competition_status"), nullable=False)

    discipline: Mapped[Discipline] = relationship(lazy="selectin")
    competition_type: Mapped[CompetitionType] = relationship(lazy="selectin")
    age_groups: Mapped[list[AgeGroup]] = relationship(secondary=competition_age_groups, lazy="selectin", order_by=AgeGroup.sort_order)
