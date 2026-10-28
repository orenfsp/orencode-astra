from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

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
    penalty_minutes: int | None = None


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


CriterionScore = Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]


class JudgeScoreWrite(BaseModel):
    """Оценки одного судьи по пяти критериям протокола продуктового программирования."""

    judge: str = Field(min_length=1, max_length=255)
    scores: list[CriterionScore] = Field(min_length=5, max_length=5)


class ResultWrite(BaseModel):
    application_id: int = Field(gt=0)
    score: Decimal | None = Field(default=None, ge=0, le=Decimal("99999999.99"), decimal_places=2)
    result_status: ResultStatus = ResultStatus.OK
    # Протокол по задачам: отметка по каждой задаче и время выполнения задач (мин); баллы = число решённых задач.
    task_marks: list[str] | None = Field(default=None, max_length=30)
    penalty_minutes: int | None = Field(default=None, ge=0, le=100000)
    # Протокол продуктового программирования: оценки судей; баллы = среднее судейских итогов.
    judge_scores: list[JudgeScoreWrite] | None = Field(default=None, min_length=1, max_length=5)

    @model_validator(mode="after")
    def ok_needs_score(self) -> "ResultWrite":
        if self.result_status == ResultStatus.OK and self.score is None and self.task_marks is None and self.judge_scores is None:
            raise ValueError("Для участника с результатом нужны баллы")
        if self.result_status != ResultStatus.OK:
            self.score, self.task_marks, self.penalty_minutes, self.judge_scores = None, None, None, None
        return self


class ResultsWrite(BaseModel):
    results: list[ResultWrite] = Field(min_length=1, max_length=2000)


class JudgeScoreRead(BaseModel):
    judge: str
    scores: list[Decimal]
    total: Decimal


class ProtocolRow(BaseModel):
    application_id: int
    place: int | None
    athlete: AthleteBrief
    score: Decimal | None
    result_status: ResultStatus | None
    task_marks: list[str] | None = None
    solved: int | None = None
    penalty_minutes: int | None = None
    judge_scores: list[JudgeScoreRead] | None = None
    # Строка «ОБЩЕЕ»: среднее судей по каждому критерию.
    overall_scores: list[Decimal] | None = None


class ProtocolGroup(BaseModel):
    age_group: AgeGroupRead
    rows: list[ProtocolRow]


class TasksSummary(BaseModel):
    """Итоговая строка образца: сколько задач предложено, сколько участников решили все задачи и ни одной."""

    offered: int | None
    solved_all: int
    solved_none: int


class ProtocolRead(BaseModel):
    competition: CompetitionBrief
    location: str
    published_at: datetime | None
    is_complete: bool
    form: Literal["tasks", "product"]
    task_count: int | None
    criteria: list[str]
    tasks_summary: TasksSummary | None
    chief_judge: str | None
    chief_secretary: str | None
    groups: list[ProtocolGroup]


class HistoryItem(BaseModel):
    application_id: int
    competition: CompetitionBrief
    age_group: AgeGroupRead
    place: int | None
    score: Decimal | None
    result_status: ResultStatus
    participants: int
