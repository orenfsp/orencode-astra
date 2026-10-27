"""Рейтинг спортсменов, дисквалификации и сборная региона."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import AgeGroup, Base, CompetitionLevel, CompetitionType, Discipline, _enum


class RatingPoints(Base):
    """Баллы рейтинга за 1–3 место в зависимости от уровня (и, при необходимости, типа) соревнования.

    Строка с competition_type_id = NULL действует для любого типа этого уровня; строка с типом точнее.
    """

    __tablename__ = "rating_points"
    __table_args__ = (UniqueConstraint("level", "competition_type_id", name="uq_rating_points_level_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    level: Mapped[CompetitionLevel] = mapped_column(_enum(CompetitionLevel, "competition_level"))
    competition_type_id: Mapped[int | None] = mapped_column(ForeignKey("competition_types.id", ondelete="CASCADE"), nullable=True)
    first: Mapped[int] = mapped_column(Integer)
    second: Mapped[int] = mapped_column(Integer)
    third: Mapped[int] = mapped_column(Integer)

    competition_type: Mapped[CompetitionType | None] = relationship(lazy="selectin")


class RatingSettings(Base):
    """Единственная строка с общими параметрами рейтинга."""

    __tablename__ = "rating_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stability_coefficient: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    stability_min_podiums: Mapped[int] = mapped_column(Integer)


class SanctionKind(str, Enum):
    DISQUALIFICATION = "disqualification"
    SUSPENSION = "suspension"


class Sanction(Base):
    """Дисквалификация или отстранение: пока действует, спортсмен не попадает в рейтинг."""

    __tablename__ = "sanctions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[SanctionKind] = mapped_column(_enum(SanctionKind, "sanction_kind"))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Team(Base):
    """Состав сборной региона, сформированный федерацией из рейтинга."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id", ondelete="RESTRICT"))
    season: Mapped[int] = mapped_column(Integer)
    age_group_id: Mapped[int | None] = mapped_column(ForeignKey("age_groups.id", ondelete="RESTRICT"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    discipline: Mapped[Discipline] = relationship(lazy="selectin")
    age_group: Mapped[AgeGroup | None] = relationship(lazy="selectin")
    members: Mapped[list[TeamMember]] = relationship(lazy="selectin", cascade="all, delete-orphan", order_by="TeamMember.position")


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "athlete_id", name="uq_team_members_team_athlete"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    is_reserve: Mapped[bool] = mapped_column(Boolean, default=False)
    # Снимок рейтинга на момент формирования, чтобы приказ не менялся задним числом.
    rating_place: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_points: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
