"""Справки об участии с проверкой подлинности и подтверждающие документы к показателям развития."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Certificate(Base):
    """Справка об участии в соревновании: номер для людей и случайный код для QR и страницы проверки."""

    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(40), unique=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    athlete_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IndicatorDocument(Base):
    """Файл, подтверждающий показатель развития вида спорта за год."""

    __tablename__ = "indicator_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator: Mapped[str] = mapped_column(String(40), index=True)
    year: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
