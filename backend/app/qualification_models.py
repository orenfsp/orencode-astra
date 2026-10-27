"""Судейские категории, судейские коллегии и спортивные разряды."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, Competition, CompetitionLevel, JudgePosition, _enum


class RequestKind(str, Enum):
    ASSIGN = "assign"
    CONFIRM = "confirm"


class RequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class JudgeCategory(str, Enum):
    YOUNG = "young"
    THIRD = "third"
    SECOND = "second"
    FIRST = "first"
    ALL_RUSSIAN = "all_russian"


class SportRank(str, Enum):
    """Разряды по ЕВСК от младшего к старшему (звание МС присваивает Минспорт России)."""

    YOUTH_3 = "youth_3"
    YOUTH_2 = "youth_2"
    YOUTH_1 = "youth_1"
    THIRD = "third"
    SECOND = "second"
    FIRST = "first"
    KMS = "kms"


RANK_ORDER = list(SportRank)


class JudgeProfile(Base):
    __tablename__ = "judge_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    category: Mapped[JudgeCategory | None] = mapped_column(_enum(JudgeCategory, "judge_category"), nullable=True)
    category_assigned_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    category_expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    order_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JudgeCategoryRequest(Base):
    __tablename__ = "judge_category_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    judge_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[JudgeCategory] = mapped_column(_enum(JudgeCategory, "judge_category"))
    kind: Mapped[RequestKind] = mapped_column(_enum(RequestKind, "request_kind"))
    justification: Mapped[str] = mapped_column(Text)
    status: Mapped[RequestStatus] = mapped_column(_enum(RequestStatus, "request_status"), index=True)
    moderator_comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class JudgeAssignment(Base):
    """Назначение судьи в судейскую коллегию соревнования с должностью."""

    __tablename__ = "judge_assignments"
    __table_args__ = (UniqueConstraint("competition_id", "judge_id", name="uq_judge_assignments_competition_judge"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id", ondelete="CASCADE"), index=True)
    judge_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    position_id: Mapped[int] = mapped_column(ForeignKey("judge_positions.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    competition: Mapped[Competition] = relationship(lazy="selectin")
    position: Mapped[JudgePosition] = relationship(lazy="selectin")


class AthleteRank(Base):
    """Присвоенный разряд: дата, приказ, срок действия и основание (заявка)."""

    __tablename__ = "athlete_ranks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rank: Mapped[SportRank] = mapped_column(_enum(SportRank, "sport_rank"))
    assigned_on: Mapped[date] = mapped_column(Date)
    expires_on: Mapped[date] = mapped_column(Date, index=True)
    order_ref: Mapped[str] = mapped_column(String(120))
    request_id: Mapped[int | None] = mapped_column(ForeignKey("rank_requests.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RankRequest(Base):
    """Заявка на присвоение или подтверждение разряда с указанием результата-основания."""

    __tablename__ = "rank_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rank: Mapped[SportRank] = mapped_column(_enum(SportRank, "sport_rank"))
    kind: Mapped[RequestKind] = mapped_column(_enum(RequestKind, "request_kind"))
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="RESTRICT"))
    submitted_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    submitted_role: Mapped[str] = mapped_column(String(40))
    status: Mapped[RequestStatus] = mapped_column(_enum(RequestStatus, "request_status"), index=True)
    moderator_comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class RankNorm(Base):
    """Ориентир ЕВСК: какое место на соревновании какого статуса даёт право на разряд.

    Значения заполняются федерацией по действующим нормам ЕВСК; используются, чтобы подсветить кандидатов.
    """

    __tablename__ = "rank_norms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[CompetitionLevel] = mapped_column(_enum(CompetitionLevel, "competition_level"))
    max_place: Mapped[int] = mapped_column(Integer)
    rank: Mapped[SportRank] = mapped_column(_enum(SportRank, "sport_rank"))
