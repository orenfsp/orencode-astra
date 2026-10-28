from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import AgeGroup, Base, Competition, _enum


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ResultStatus(str, Enum):
    """Итог участника в протоколе: ранжирован, не явился, дисквалифицирован."""

    OK = "ok"
    DNS = "dns"
    DSQ = "dsq"


class Application(Base):
    """Заявка спортсмена на соревнование; один спортсмен — одна заявка на соревнование."""

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("competition_id", "athlete_id", name="uq_applications_competition_athlete"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competition_id: Mapped[int] = mapped_column(ForeignKey("competitions.id", ondelete="CASCADE"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    age_group_id: Mapped[int] = mapped_column(ForeignKey("age_groups.id", ondelete="RESTRICT"))
    submitted_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    submitted_role: Mapped[str] = mapped_column(String(40))
    status: Mapped[ApplicationStatus] = mapped_column(_enum(ApplicationStatus, "application_status"), index=True)
    moderator_comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    competition: Mapped[Competition] = relationship(lazy="selectin")
    age_group: Mapped[AgeGroup] = relationship(lazy="selectin")
    result: Mapped[Result | None] = relationship(back_populates="application", lazy="selectin", uselist=False)


class Result(Base):
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), unique=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    result_status: Mapped[ResultStatus] = mapped_column(_enum(ResultStatus, "result_status"))
    # Место рассчитывается автоматически внутри возрастной группы при сохранении результатов.
    place: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Протокол по задачам: отметки по каждой задаче («+», «+2», «-1», пусто) и время выполнения задач в минутах.
    task_marks: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    penalty_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Протокол продуктового программирования: [{"judge": ФИО, "scores": [пять критериев]}].
    judge_scores: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    application: Mapped[Application] = relationship(back_populates="result")
