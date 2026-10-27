from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base, Discipline, _enum


class LinkStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ENDED = "ended"
    DECLINED = "declined"


class CoachLink(Base):
    """Связь тренер — спортсмен по дисциплине. Спортсмен подтверждает запрос тренера."""

    __tablename__ = "coach_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    discipline_id: Mapped[int] = mapped_column(ForeignKey("disciplines.id", ondelete="RESTRICT"))
    status: Mapped[LinkStatus] = mapped_column(_enum(LinkStatus, "link_status"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    discipline: Mapped[Discipline] = relationship(lazy="selectin")
    events: Mapped[list[CoachLinkEvent]] = relationship(lazy="selectin", order_by="CoachLinkEvent.id", cascade="all, delete-orphan")


class CoachLinkEvent(Base):
    """История изменений связи: кто и когда перевёл её в какой статус."""

    __tablename__ = "coach_link_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("coach_links.id", ondelete="CASCADE"), index=True)
    status: Mapped[LinkStatus] = mapped_column(_enum(LinkStatus, "link_status"))
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
