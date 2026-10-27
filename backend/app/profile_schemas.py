from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.profile_models import Gender, TrainingStage
from app.schemas import DisciplineRead, OrganizationRead, RefItem


def _clean(value: str | None) -> str | None:
    return (value or "").strip() or None


class ProfileWrite(BaseModel):
    last_name: str = Field(min_length=1, max_length=120)
    first_name: str = Field(min_length=1, max_length=120)
    middle_name: str | None = Field(default=None, max_length=120)
    birth_date: date | None = None
    gender: Gender | None = None
    municipality_id: int | None = Field(default=None, gt=0)
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("last_name", "first_name")
    @classmethod
    def required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Поле не может быть пустым")
        return value

    @field_validator("middle_name", "phone")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _clean(value)

    @field_validator("birth_date")
    @classmethod
    def plausible_birth_date(cls, value: date | None) -> date | None:
        if value is not None and not (date(1920, 1, 1) <= value <= date.today()):
            raise ValueError("Некорректная дата рождения")
        return value


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    last_name: str
    first_name: str
    middle_name: str | None
    birth_date: date | None
    gender: Gender | None
    municipality: RefItem | None
    phone: str | None


class AthleteWrite(BaseModel):
    organization_id: int | None = Field(default=None, gt=0)
    discipline_ids: list[int] = Field(min_length=1, max_length=6)
    start_year: int | None = Field(default=None, ge=1990)
    end_year: int | None = Field(default=None, ge=1990)
    training_stage: TrainingStage | None = None
    guardian_name: str | None = Field(default=None, max_length=255)
    guardian_phone: str | None = Field(default=None, max_length=40)
    guardian_consent: bool = False
    rusada_completed_on: date | None = None
    rusada_certificate_url: HttpUrl | None = None

    @field_validator("guardian_name", "guardian_phone")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        return _clean(value)

    @field_validator("start_year", "end_year")
    @classmethod
    def not_future_year(cls, value: int | None) -> int | None:
        if value is not None and value > date.today().year:
            raise ValueError("Год не может быть в будущем")
        return value

    @model_validator(mode="after")
    def end_after_start(self) -> "AthleteWrite":
        if self.end_year is not None and self.start_year is not None and self.end_year < self.start_year:
            raise ValueError("Год окончания занятий раньше года начала")
        return self


class AthleteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization: OrganizationRead | None
    disciplines: list[DisciplineRead]
    start_year: int | None
    end_year: int | None
    training_stage: TrainingStage | None
    guardian_name: str | None
    guardian_phone: str | None
    guardian_consent_at: datetime | None
    rusada_completed_on: date | None
    rusada_certificate_url: str | None


class CoachWrite(BaseModel):
    organization_id: int | None = Field(default=None, gt=0)


class CoachRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    organization: OrganizationRead | None


class MyProfileRead(BaseModel):
    profile: ProfileRead | None
    athlete: AthleteRead | None
    coach: CoachRead | None
    age: int | None
    is_minor: bool
    pd_consent_at: datetime | None
