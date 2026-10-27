from datetime import date
from enum import Enum

from sqlalchemy import Date, Enum as SqlEnum, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CompetitionStatus(str, Enum):
    REGISTRATION_OPEN = "registration_open"
    UPCOMING = "upcoming"
    COMPLETED = "completed"


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    discipline: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CompetitionStatus] = mapped_column(
        SqlEnum(
            CompetitionStatus,
            name="competition_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
