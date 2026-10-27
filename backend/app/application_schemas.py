from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.application_models import ApplicationStatus, ResultStatus
from app.models import CompetitionLevel
from app.schemas import AgeGroupRead, DisciplineRead, RefItem


class Eligibility(BaseModel):
    """Может ли текущий спортсмен подать заявку и в какую возрастную группу он попадает."""

    eligible: bool
    reasons: list[str]
    age: int | None
    age_group: AgeGroupRead | None
    application_id: int | None
    application_status: ApplicationStatus | None


class CompetitionBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    date: date
    end_date: date
    level: CompetitionLevel
    discipline: DisciplineRead
    competition_type: RefItem


class AthleteBrief(BaseModel):
    id: int
    full_name: str
    birth_date: date | None
    municipality: str | None
    organization: str | None


class ResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: Decimal | None
    result_status: ResultStatus
    place: int | None


class ApplicationRead(BaseModel):
    id: int
    competition: CompetitionBrief
    athlete: AthleteBrief
    age_group: AgeGroupRead
    status: ApplicationStatus
    submitted_role: str
    moderator_comment: str | None
    created_at: datetime
    decided_at: datetime | None
    result: ResultRead | None


class DecisionRequest(BaseModel):
    status: Literal["approved", "rejected"]
    comment: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def rejection_needs_reason(self) -> "DecisionRequest":
        self.comment = (self.comment or "").strip() or None
        if self.status == "rejected" and not self.comment:
            raise ValueError("Укажите причину отклонения заявки")
        return self


class ResultWrite(BaseModel):
    application_id: int = Field(gt=0)
    score: Decimal | None = Field(default=None, ge=0, le=Decimal("99999999.99"), decimal_places=2)
    result_status: ResultStatus = ResultStatus.OK

    @model_validator(mode="after")
    def ok_needs_score(self) -> "ResultWrite":
        if self.result_status == ResultStatus.OK and self.score is None:
            raise ValueError("Для участника с результатом нужны баллы")
        if self.result_status != ResultStatus.OK:
            self.score = None
        return self


class ResultsWrite(BaseModel):
    results: list[ResultWrite] = Field(min_length=1, max_length=2000)


class ProtocolRow(BaseModel):
    application_id: int
    place: int | None
    athlete: AthleteBrief
    score: Decimal | None
    result_status: ResultStatus | None


class ProtocolGroup(BaseModel):
    age_group: AgeGroupRead
    rows: list[ProtocolRow]


class ProtocolRead(BaseModel):
    competition: CompetitionBrief
    location: str
    published_at: datetime | None
    is_complete: bool
    groups: list[ProtocolGroup]


class HistoryItem(BaseModel):
    competition: CompetitionBrief
    age_group: AgeGroupRead
    place: int | None
    score: Decimal | None
    result_status: ResultStatus
    participants: int
