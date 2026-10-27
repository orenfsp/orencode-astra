from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import CompetitionStatus


class CompetitionFields(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    discipline: str = Field(min_length=1, max_length=255)
    date: Date
    location: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=5000)
    event_format: str = Field(min_length=1, max_length=120)
    registration_start: Date
    registration_end: Date
    status: CompetitionStatus = CompetitionStatus.DRAFT

    @model_validator(mode="after")
    def validate_dates(self) -> "CompetitionFields":
        if self.registration_start > self.registration_end:
            raise ValueError("registration_start must not be after registration_end")
        if self.registration_end > self.date:
            raise ValueError("registration_end must not be after competition date")
        return self


class CompetitionCreate(CompetitionFields):
    pass


class CompetitionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    discipline: str | None = Field(default=None, min_length=1, max_length=255)
    date: Date | None = None
    location: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    event_format: str | None = Field(default=None, min_length=1, max_length=120)
    registration_start: Date | None = None
    registration_end: Date | None = None


class CompetitionStatusUpdate(BaseModel):
    status: CompetitionStatus


class CompetitionRead(CompetitionFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_archived: bool
