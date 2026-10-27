from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, Discipline, Municipality, Organization, _enum


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"


class TrainingStage(str, Enum):
    """Этапы спортивной подготовки по ФССП."""

    INITIAL = "initial"
    TRAINING = "training"
    IMPROVEMENT = "improvement"
    HIGHEST = "highest"


class Profile(Base):
    """Общие персональные данные аккаунта, используются всеми ролями."""

    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    last_name: Mapped[str] = mapped_column(String(120))
    first_name: Mapped[str] = mapped_column(String(120))
    middle_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(_enum(Gender, "gender"), nullable=True)
    municipality_id: Mapped[int | None] = mapped_column(ForeignKey("municipalities.id", ondelete="SET NULL"), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    municipality: Mapped[Municipality | None] = relationship(lazy="selectin")


athlete_disciplines = Table(
    "athlete_disciplines",
    Base.metadata,
    Column("user_id", ForeignKey("athlete_profiles.user_id", ondelete="CASCADE"), primary_key=True),
    Column("discipline_id", ForeignKey("disciplines.id", ondelete="RESTRICT"), primary_key=True),
)


class AthleteProfile(Base):
    __tablename__ = "athlete_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # NULL означает «без организации».
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Год, после которого спортсмен прекратил занятия; нужен для динамики численности.
    end_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    training_stage: Mapped[TrainingStage | None] = mapped_column(_enum(TrainingStage, "training_stage"), nullable=True)
    guardian_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    guardian_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    guardian_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rusada_completed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    rusada_certificate_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    organization: Mapped[Organization | None] = relationship(lazy="selectin")
    disciplines: Mapped[list[Discipline]] = relationship(secondary=athlete_disciplines, lazy="selectin", order_by=Discipline.sort_order)


class CoachProfile(Base):
    __tablename__ = "coach_profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    organization: Mapped[Organization | None] = relationship(lazy="selectin")
