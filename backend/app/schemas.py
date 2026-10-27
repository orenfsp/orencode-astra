from datetime import date as Date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import CalendarPlan, CompetitionFormat, CompetitionLevel, CompetitionStatus, OrganizationType


class RefItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class DisciplineRead(RefItem):
    code: str


class AgeGroupRead(RefItem):
    min_age: int
    max_age: int | None


class CompetitionTypeRead(RefItem):
    is_active: bool


class OrganizationRead(RefItem):
    org_type: OrganizationType
    municipality: RefItem | None
    is_active: bool


class ReferenceBundle(BaseModel):
    disciplines: list[DisciplineRead]
    competition_types: list[CompetitionTypeRead]
    age_groups: list[AgeGroupRead]
    municipalities: list[RefItem]
    organizations: list[OrganizationRead]
    judge_positions: list[RefItem]


class CompetitionTypeWrite(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    is_active: bool = True


class AgeGroupWrite(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    min_age: int = Field(ge=5, le=100)
    max_age: int | None = Field(default=None, ge=5, le=100)

    @model_validator(mode="after")
    def validate_range(self) -> "AgeGroupWrite":
        if self.max_age is not None and self.max_age < self.min_age:
            raise ValueError("max_age must not be less than min_age")
        return self


class OrganizationWrite(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    org_type: OrganizationType
    municipality_id: int | None = None
    is_active: bool = True


class CompetitionFields(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    discipline_id: int = Field(gt=0)
    competition_type_id: int = Field(gt=0)
    level: CompetitionLevel
    age_group_ids: list[int] = Field(min_length=1, max_length=10)
    date: Date
    end_date: Date
    location: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=5000)
    format: CompetitionFormat
    registration_start: Date
    registration_end: Date
    calendar_plan: CalendarPlan = CalendarPlan.NONE
    calendar_plan_number: str | None = Field(default=None, max_length=60)
    status: CompetitionStatus = CompetitionStatus.DRAFT

    @model_validator(mode="after")
    def validate_rules(self) -> "CompetitionFields":
        if self.registration_start > self.registration_end:
            raise ValueError("registration_start must not be after registration_end")
        if self.registration_end > self.date:
            raise ValueError("registration_end must not be after competition date")
        if self.end_date < self.date:
            raise ValueError("end_date must not be before date")
        # Всероссийские и межрегиональные — в ЕКП Минспорта, региональные — в календарный план области.
        if self.calendar_plan == CalendarPlan.EKP and self.level == CompetitionLevel.REGIONAL:
            raise ValueError("Региональное соревнование включается в календарный план области, а не в ЕКП")
        if self.calendar_plan == CalendarPlan.REGIONAL and self.level != CompetitionLevel.REGIONAL:
            raise ValueError("Межрегиональные и всероссийские соревнования включаются в ЕКП")
        if self.calendar_plan == CalendarPlan.NONE:
            self.calendar_plan_number = None
        self.age_group_ids = sorted(set(self.age_group_ids))
        return self


class CompetitionCreate(CompetitionFields):
    pass


class CompetitionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    discipline_id: int | None = Field(default=None, gt=0)
    competition_type_id: int | None = Field(default=None, gt=0)
    level: CompetitionLevel | None = None
    age_group_ids: list[int] | None = Field(default=None, min_length=1, max_length=10)
    date: Date | None = None
    end_date: Date | None = None
    location: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    format: CompetitionFormat | None = None
    registration_start: Date | None = None
    registration_end: Date | None = None
    calendar_plan: CalendarPlan | None = None
    calendar_plan_number: str | None = Field(default=None, max_length=60)


class CompetitionStatusUpdate(BaseModel):
    status: CompetitionStatus


class CompetitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    discipline: DisciplineRead
    competition_type: RefItem
    level: CompetitionLevel
    age_groups: list[AgeGroupRead]
    date: Date
    end_date: Date
    location: str
    description: str
    format: CompetitionFormat
    registration_start: Date
    registration_end: Date
    calendar_plan: CalendarPlan
    calendar_plan_number: str | None
    regulation_filename: str | None
    protocol_published_at: datetime | None
    status: CompetitionStatus
    is_archived: bool
