"""Судейские категории и коллегии, спортивные разряды и ориентиры ЕВСК."""

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application_models import Application, ApplicationStatus, Result, ResultStatus
from app.application_schemas import AthleteBrief, CompetitionBrief
from app.auth_models import AuthSession, Role, User, user_roles
from app.auth_routes import current_auth_session, require_roles
from app.auth_security import utcnow
from app.coaching import active_athlete_ids, has_active_coach
from app.database import get_session
from app.models import Competition, CompetitionLevel, JudgePosition
from app.notifications import admin_ids, notify
from app.people import athlete_briefs, names
from app.qualification_models import (
    RANK_ORDER, AthleteRank, JudgeAssignment, JudgeCategory, JudgeCategoryRequest, JudgeProfile, RankNorm, RankRequest,
    RequestKind, RequestStatus, SportRank,
)
from app.schemas import RefItem


router = APIRouter(prefix="/api/v1", tags=["qualifications"])
admin_read = require_roles("federation_admin")
admin_write = require_roles("federation_admin", csrf=True)
EXPIRY_WARNING_DAYS = 60

RANK_LABELS = {
    SportRank.YOUTH_3: "3 юношеский разряд", SportRank.YOUTH_2: "2 юношеский разряд", SportRank.YOUTH_1: "1 юношеский разряд",
    SportRank.THIRD: "3 спортивный разряд", SportRank.SECOND: "2 спортивный разряд", SportRank.FIRST: "1 спортивный разряд",
    SportRank.KMS: "КМС",
}
CATEGORY_LABELS = {
    JudgeCategory.YOUNG: "Юный спортивный судья", JudgeCategory.THIRD: "Спортивный судья 3 категории",
    JudgeCategory.SECOND: "Спортивный судья 2 категории", JudgeCategory.FIRST: "Спортивный судья 1 категории",
    JudgeCategory.ALL_RUSSIAN: "Спортивный судья всероссийской категории",
}


def validity(expires_on: date | None, today: date | None = None) -> Literal["none", "valid", "expiring", "expired"]:
    if expires_on is None:
        return "none"
    days = (expires_on - (today or date.today())).days
    return "expired" if days < 0 else "expiring" if days <= EXPIRY_WARNING_DAYS else "valid"


class Decision(BaseModel):
    """Решение федерации; при одобрении фиксируются дата, приказ и срок действия."""

    status: Literal["approved", "rejected"]
    comment: str | None = Field(default=None, max_length=1000)
    assigned_on: date | None = None
    expires_on: date | None = None
    order_ref: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def complete(self) -> "Decision":
        self.comment = (self.comment or "").strip() or None
        self.order_ref = (self.order_ref or "").strip() or None
        if self.status == "rejected" and not self.comment:
            raise ValueError("Укажите причину отказа")
        if self.status == "approved":
            if not (self.assigned_on and self.expires_on and self.order_ref):
                raise ValueError("Укажите дату присвоения, срок действия и реквизиты приказа")
            if self.expires_on <= self.assigned_on:
                raise ValueError("Срок действия должен быть позже даты присвоения")
        return self


# =============================== судьи ===============================

class JudgeCategoryInfo(BaseModel):
    category: JudgeCategory | None
    category_assigned_on: date | None
    category_expires_on: date | None
    order_ref: str | None
    validity: str


class AssignmentRead(BaseModel):
    id: int
    competition: CompetitionBrief
    judge_id: int
    judge_name: str
    position: RefItem


class JudgeRequestRead(BaseModel):
    id: int
    judge_id: int
    judge_name: str
    category: JudgeCategory
    kind: RequestKind
    justification: str
    status: RequestStatus
    moderator_comment: str | None
    created_at: datetime
    current: JudgeCategoryInfo


class MyJudge(BaseModel):
    info: JudgeCategoryInfo
    assignments: list[AssignmentRead]
    requests: list[JudgeRequestRead]


class JudgeRow(BaseModel):
    judge_id: int
    name: str
    info: JudgeCategoryInfo
    assignments: int


class JudgeRequestCreate(BaseModel):
    category: JudgeCategory
    kind: RequestKind
    justification: str = Field(min_length=10, max_length=4000)


class AssignmentCreate(BaseModel):
    judge_id: int = Field(gt=0)
    position_id: int = Field(gt=0)


def _info(profile: JudgeProfile | None) -> JudgeCategoryInfo:
    return JudgeCategoryInfo(
        category=profile.category if profile else None,
        category_assigned_on=profile.category_assigned_on if profile else None,
        category_expires_on=profile.category_expires_on if profile else None,
        order_ref=profile.order_ref if profile else None,
        validity=validity(profile.category_expires_on if profile else None),
    )


async def _judge_requests(db: AsyncSession, items: list[JudgeCategoryRequest]) -> list[JudgeRequestRead]:
    people = await names(db, {item.judge_id for item in items})
    profiles = {item.user_id: item for item in await db.scalars(select(JudgeProfile).where(JudgeProfile.user_id.in_({item.judge_id for item in items})))} if items else {}
    return [
        JudgeRequestRead(
            id=item.id, judge_id=item.judge_id, judge_name=people[item.judge_id], category=item.category, kind=item.kind,
            justification=item.justification, status=item.status, moderator_comment=item.moderator_comment, created_at=item.created_at,
            current=_info(profiles.get(item.judge_id)),
        )
        for item in items
    ]


async def _assignments(db: AsyncSession, items: list[JudgeAssignment]) -> list[AssignmentRead]:
    people = await names(db, {item.judge_id for item in items})
    return [
        AssignmentRead(id=item.id, competition=CompetitionBrief.model_validate(item.competition), judge_id=item.judge_id,
                       judge_name=people[item.judge_id], position=RefItem.model_validate(item.position))
        for item in items
    ]


async def judge_ids(db: AsyncSession) -> set[int]:
    return set(await db.scalars(select(user_roles.c.user_id).join(Role, Role.id == user_roles.c.role_id).where(Role.name == "judge")))


@router.get("/me/judge", response_model=MyJudge)
async def my_judge(judge: User = Depends(require_roles("judge")), db: AsyncSession = Depends(get_session)) -> MyJudge:
    assignments = list(await db.scalars(
        select(JudgeAssignment).join(Competition, Competition.id == JudgeAssignment.competition_id)
        .where(JudgeAssignment.judge_id == judge.id).order_by(Competition.date.desc())
    ))
    requests = list(await db.scalars(select(JudgeCategoryRequest).where(JudgeCategoryRequest.judge_id == judge.id).order_by(JudgeCategoryRequest.id.desc())))
    return MyJudge(info=_info(await db.get(JudgeProfile, judge.id)), assignments=await _assignments(db, assignments), requests=await _judge_requests(db, requests))


@router.post("/me/judge/requests", response_model=JudgeRequestRead, status_code=201)
async def create_judge_request(payload: JudgeRequestCreate, judge: User = Depends(require_roles("judge", csrf=True)), db: AsyncSession = Depends(get_session)) -> JudgeRequestRead:
    pending = await db.scalar(select(JudgeCategoryRequest.id).where(JudgeCategoryRequest.judge_id == judge.id, JudgeCategoryRequest.status == RequestStatus.PENDING))
    if pending is not None:
        raise HTTPException(status_code=409, detail="Предыдущая заявка ещё на рассмотрении")
    profile = await db.get(JudgeProfile, judge.id)
    if payload.kind == RequestKind.CONFIRM and (profile is None or profile.category != payload.category):
        raise HTTPException(status_code=422, detail="Подтвердить можно только текущую категорию")
    item = JudgeCategoryRequest(judge_id=judge.id, category=payload.category, kind=payload.kind, justification=payload.justification.strip(), status=RequestStatus.PENDING, created_at=utcnow())
    db.add(item)
    name = (await names(db, {judge.id}))[judge.id]
    await notify(db, await admin_ids(db), "judge_request", "Заявка на судейскую категорию", f"{name}: {CATEGORY_LABELS[payload.category]}", "/admin/judges")
    await db.commit()
    return (await _judge_requests(db, [item]))[0]


@router.get("/judges", response_model=list[JudgeRow])
async def judges_registry(_admin: User = Depends(admin_read), db: AsyncSession = Depends(get_session)) -> list[JudgeRow]:
    ids = await judge_ids(db)
    people = await names(db, ids)
    profiles = {item.user_id: item for item in await db.scalars(select(JudgeProfile).where(JudgeProfile.user_id.in_(ids)))} if ids else {}
    counts: dict[int, int] = {}
    for judge_id in await db.scalars(select(JudgeAssignment.judge_id)):
        counts[judge_id] = counts.get(judge_id, 0) + 1
    rows = [JudgeRow(judge_id=item, name=people[item], info=_info(profiles.get(item)), assignments=counts.get(item, 0)) for item in ids]
    return sorted(rows, key=lambda row: row.name)


@router.get("/judge-requests", response_model=list[JudgeRequestRead])
async def judge_requests(status: RequestStatus | None = None, _admin: User = Depends(admin_read), db: AsyncSession = Depends(get_session)) -> list[JudgeRequestRead]:
    statement = select(JudgeCategoryRequest).order_by(JudgeCategoryRequest.id.desc())
    if status is not None:
        statement = statement.where(JudgeCategoryRequest.status == status)
    return await _judge_requests(db, list(await db.scalars(statement)))


@router.post("/judge-requests/{request_id}/decision", response_model=JudgeRequestRead)
async def decide_judge_request(request_id: Annotated[int, Path(gt=0)], payload: Decision, admin: User = Depends(admin_write), db: AsyncSession = Depends(get_session)) -> JudgeRequestRead:
    item = await db.get(JudgeCategoryRequest, request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if item.status != RequestStatus.PENDING:
        raise HTTPException(status_code=409, detail="Решение уже принято")
    item.status, item.moderator_comment, item.decided_at, item.decided_by_id = RequestStatus(payload.status), payload.comment, utcnow(), admin.id
    if item.status == RequestStatus.APPROVED:
        profile = await db.get(JudgeProfile, item.judge_id)
        if profile is None:
            profile = JudgeProfile(user_id=item.judge_id)
            db.add(profile)
        profile.category, profile.category_assigned_on, profile.category_expires_on = item.category, payload.assigned_on, payload.expires_on
        profile.order_ref, profile.updated_at = payload.order_ref, utcnow()
        body = f"{CATEGORY_LABELS[item.category]} до {payload.expires_on:%d.%m.%Y}, приказ {payload.order_ref}."
    else:
        body = f"Отказ: {payload.comment}"
    await notify(db, {item.judge_id}, "judge_decision", "Решение по судейской категории", body, "/cabinet")
    await db.commit()
    return (await _judge_requests(db, [item]))[0]


@router.get("/competitions/{competition_id}/judges", response_model=list[AssignmentRead])
async def competition_judges(competition_id: Annotated[int, Path(gt=0)], _admin: User = Depends(admin_read), db: AsyncSession = Depends(get_session)) -> list[AssignmentRead]:
    items = list(await db.scalars(select(JudgeAssignment).where(JudgeAssignment.competition_id == competition_id).order_by(JudgeAssignment.position_id, JudgeAssignment.id)))
    return await _assignments(db, items)


@router.post("/competitions/{competition_id}/judges", response_model=AssignmentRead, status_code=201)
async def assign_judge(competition_id: Annotated[int, Path(gt=0)], payload: AssignmentCreate, _admin: User = Depends(admin_write), db: AsyncSession = Depends(get_session)) -> AssignmentRead:
    competition = await db.get(Competition, competition_id)
    if competition is None or competition.is_archived:
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    if payload.judge_id not in await judge_ids(db):
        raise HTTPException(status_code=422, detail="Пользователь не зарегистрирован как судья")
    position = await db.get(JudgePosition, payload.position_id)
    if position is None:
        raise HTTPException(status_code=422, detail="Неизвестная судейская должность")
    item = JudgeAssignment(competition_id=competition.id, judge_id=payload.judge_id, position_id=position.id, created_at=utcnow())
    db.add(item)
    await notify(db, {payload.judge_id}, "judge_assigned", "Назначение в судейскую коллегию", f"«{competition.title}», {competition.date:%d.%m.%Y}: {position.name}.", "/cabinet")
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Судья уже назначен на это соревнование") from None
    await db.refresh(item, ["competition", "position"])
    return (await _assignments(db, [item]))[0]


@router.delete("/competitions/{competition_id}/judges/{assignment_id}", status_code=204)
async def remove_judge(competition_id: Annotated[int, Path(gt=0)], assignment_id: Annotated[int, Path(gt=0)], _admin: User = Depends(admin_write), db: AsyncSession = Depends(get_session)) -> None:
    item = await db.get(JudgeAssignment, assignment_id)
    if item is None or item.competition_id != competition_id:
        raise HTTPException(status_code=404, detail="Назначение не найдено")
    await db.delete(item)
    await db.commit()


# =============================== разряды ===============================

class RankRead(BaseModel):
    id: int
    rank: SportRank
    assigned_on: date
    expires_on: date
    order_ref: str
    validity: str


class Basis(BaseModel):
    application_id: int
    competition: CompetitionBrief
    place: int | None
    score: str | None
    result_status: ResultStatus


class RankRequestRead(BaseModel):
    id: int
    athlete: AthleteBrief
    rank: SportRank
    kind: RequestKind
    basis: Basis
    submitted_by: str
    submitted_role: str
    status: RequestStatus
    moderator_comment: str | None
    created_at: datetime
    current: RankRead | None


class MyRank(BaseModel):
    current: RankRead | None
    history: list[RankRead]
    has_coach: bool
    requests: list[RankRequestRead]


class RankRequestCreate(BaseModel):
    athlete_id: int | None = Field(default=None, gt=0)
    rank: SportRank
    kind: RequestKind
    application_id: int = Field(gt=0)


class Candidate(BaseModel):
    athlete: AthleteBrief
    suggested_rank: SportRank
    current: RankRead | None
    basis: Basis
    pending_request: bool


class ExpiringRank(BaseModel):
    athlete: AthleteBrief
    rank: RankRead


class RankNormRow(BaseModel):
    level: CompetitionLevel
    max_place: int = Field(ge=1, le=100)
    rank: SportRank


def _rank_read(item: AthleteRank | None) -> RankRead | None:
    if item is None:
        return None
    return RankRead(id=item.id, rank=item.rank, assigned_on=item.assigned_on, expires_on=item.expires_on, order_ref=item.order_ref, validity=validity(item.expires_on))


async def _latest_ranks(db: AsyncSession, athlete_ids: set[int]) -> dict[int, AthleteRank]:
    latest: dict[int, AthleteRank] = {}
    if athlete_ids:
        for item in await db.scalars(select(AthleteRank).where(AthleteRank.athlete_id.in_(athlete_ids)).order_by(AthleteRank.assigned_on, AthleteRank.id)):
            latest[item.athlete_id] = item
    return latest


def _basis(application: Application) -> Basis:
    result = application.result
    return Basis(
        application_id=application.id, competition=CompetitionBrief.model_validate(application.competition),
        place=result.place if result else None, score=str(result.score) if result and result.score is not None else None,
        result_status=result.result_status if result else ResultStatus.DNS,
    )


async def _rank_requests(db: AsyncSession, items: list[RankRequest]) -> list[RankRequestRead]:
    athletes = await athlete_briefs(db, {item.athlete_id for item in items})
    people = await names(db, {item.submitted_by_id for item in items})
    latest = await _latest_ranks(db, {item.athlete_id for item in items})
    applications = {item.id: item for item in await db.scalars(select(Application).where(Application.id.in_({item.application_id for item in items})))} if items else {}
    return [
        RankRequestRead(
            id=item.id, athlete=athletes[item.athlete_id], rank=item.rank, kind=item.kind, basis=_basis(applications[item.application_id]),
            submitted_by=people[item.submitted_by_id], submitted_role=item.submitted_role, status=item.status,
            moderator_comment=item.moderator_comment, created_at=item.created_at, current=_rank_read(latest.get(item.athlete_id)),
        )
        for item in items
    ]


@router.get("/me/rank", response_model=MyRank)
async def my_rank(athlete: User = Depends(require_roles("athlete")), db: AsyncSession = Depends(get_session)) -> MyRank:
    history = list(await db.scalars(select(AthleteRank).where(AthleteRank.athlete_id == athlete.id).order_by(AthleteRank.assigned_on.desc(), AthleteRank.id.desc())))
    requests = list(await db.scalars(select(RankRequest).where(RankRequest.athlete_id == athlete.id).order_by(RankRequest.id.desc())))
    return MyRank(
        current=_rank_read(history[0] if history else None),
        history=[_rank_read(item) for item in history],
        has_coach=await has_active_coach(db, athlete.id),
        requests=await _rank_requests(db, requests),
    )


@router.post("/rank-requests", response_model=RankRequestRead, status_code=201)
async def create_rank_request(
    payload: RankRequestCreate,
    _user: User = Depends(require_roles("athlete", "coach", csrf=True)),
    auth_session: AuthSession = Depends(current_auth_session),
    db: AsyncSession = Depends(get_session),
) -> RankRequestRead:
    if auth_session.active_role == "athlete":
        athlete_id = auth_session.user_id
        if await has_active_coach(db, athlete_id):
            raise HTTPException(status_code=409, detail="У вас есть тренер — заявку на разряд подаёт он")
    else:
        if payload.athlete_id is None:
            raise HTTPException(status_code=422, detail="Выберите спортсмена")
        athlete_id = payload.athlete_id
        if athlete_id not in await active_athlete_ids(db, auth_session.user_id):
            raise HTTPException(status_code=403, detail="Нет активной связи с этим спортсменом")

    application = await db.get(Application, payload.application_id)
    if (
        application is None or application.athlete_id != athlete_id or application.status != ApplicationStatus.APPROVED
        or application.result is None or application.competition.protocol_published_at is None
    ):
        raise HTTPException(status_code=422, detail="Основанием может быть только результат спортсмена в опубликованном протоколе")
    if await db.scalar(select(RankRequest.id).where(RankRequest.athlete_id == athlete_id, RankRequest.status == RequestStatus.PENDING)) is not None:
        raise HTTPException(status_code=409, detail="Заявка на разряд уже на рассмотрении")
    current = (await _latest_ranks(db, {athlete_id})).get(athlete_id)
    if payload.kind == RequestKind.CONFIRM and (current is None or current.rank != payload.rank):
        raise HTTPException(status_code=422, detail="Подтвердить можно только текущий разряд")

    item = RankRequest(
        athlete_id=athlete_id, rank=payload.rank, kind=payload.kind, application_id=application.id, submitted_by_id=auth_session.user_id,
        submitted_role=auth_session.active_role, status=RequestStatus.PENDING, created_at=utcnow(),
    )
    db.add(item)
    athlete_name = (await names(db, {athlete_id}))[athlete_id]
    await notify(db, await admin_ids(db), "rank_request", "Заявка на разряд", f"{athlete_name}: {RANK_LABELS[payload.rank]} — «{application.competition.title}»", "/admin/ranks")
    await db.commit()
    return (await _rank_requests(db, [item]))[0]


@router.get("/coach/rank-requests", response_model=list[RankRequestRead])
async def coach_rank_requests(coach: User = Depends(require_roles("coach")), db: AsyncSession = Depends(get_session)) -> list[RankRequestRead]:
    ids = await active_athlete_ids(db, coach.id)
    items = list(await db.scalars(select(RankRequest).where(RankRequest.athlete_id.in_(ids)).order_by(RankRequest.id.desc()))) if ids else []
    return await _rank_requests(db, items)


@router.get("/rank-requests", response_model=list[RankRequestRead])
async def rank_requests(status: RequestStatus | None = None, _admin: User = Depends(admin_read), db: AsyncSession = Depends(get_session)) -> list[RankRequestRead]:
    statement = select(RankRequest).order_by(RankRequest.id.desc())
    if status is not None:
        statement = statement.where(RankRequest.status == status)
    return await _rank_requests(db, list(await db.scalars(statement)))


@router.post("/rank-requests/{request_id}/decision", response_model=RankRequestRead)
async def decide_rank_request(request_id: Annotated[int, Path(gt=0)], payload: Decision, admin: User = Depends(admin_write), db: AsyncSession = Depends(get_session)) -> RankRequestRead:
    item = await db.get(RankRequest, request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if item.status != RequestStatus.PENDING:
        raise HTTPException(status_code=409, detail="Решение уже принято")
    item.status, item.moderator_comment, item.decided_at, item.decided_by_id = RequestStatus(payload.status), payload.comment, utcnow(), admin.id
    if item.status == RequestStatus.APPROVED:
        db.add(AthleteRank(
            athlete_id=item.athlete_id, rank=item.rank, assigned_on=payload.assigned_on, expires_on=payload.expires_on,
            order_ref=payload.order_ref, request_id=item.id, created_at=utcnow(),
        ))
        body = f"{RANK_LABELS[item.rank]} присвоен, приказ {payload.order_ref}, действует до {payload.expires_on:%d.%m.%Y}."
    else:
        body = f"{RANK_LABELS[item.rank]}: отказ. {payload.comment}"
    await notify(db, {item.athlete_id, item.submitted_by_id}, "rank_decision", "Решение по заявке на разряд", body, "/cabinet")
    await db.commit()
    return (await _rank_requests(db, [item]))[0]


def suggested_rank(level: CompetitionLevel, place: int | None, norms: list[RankNorm]) -> SportRank | None:
    """Старший разряд, на который даёт право место на соревновании этого статуса."""
    if place is None:
        return None
    fitting = [norm.rank for norm in norms if norm.level == level and place <= norm.max_place]
    return max(fitting, key=RANK_ORDER.index) if fitting else None


@router.get("/rank-candidates", response_model=list[Candidate])
async def rank_candidates(_admin: User = Depends(admin_read), db: AsyncSession = Depends(get_session)) -> list[Candidate]:
    """Спортсмены, чей результат в опубликованном протоколе может соответствовать требованиям ЕВСК выше текущего разряда."""
    norms = list(await db.scalars(select(RankNorm)))
    rows = list(await db.scalars(
        select(Application).join(Result, Result.application_id == Application.id).join(Competition, Competition.id == Application.competition_id)
        .where(Competition.protocol_published_at.is_not(None), Result.place.is_not(None)).order_by(Competition.date.desc())
    ))
    best: dict[int, tuple[SportRank, Application]] = {}
    for application in rows:
        rank = suggested_rank(application.competition.level, application.result.place, norms)
        if rank is None:
            continue
        previous = best.get(application.athlete_id)
        if previous is None or RANK_ORDER.index(rank) > RANK_ORDER.index(previous[0]):
            best[application.athlete_id] = (rank, application)
    latest = await _latest_ranks(db, set(best))
    pending = set(await db.scalars(select(RankRequest.athlete_id).where(RankRequest.status == RequestStatus.PENDING)))
    athletes = await athlete_briefs(db, set(best))
    today = date.today()
    candidates = []
    for athlete_id, (rank, application) in best.items():
        current = latest.get(athlete_id)
        if current is not None and current.expires_on >= today and RANK_ORDER.index(current.rank) >= RANK_ORDER.index(rank):
            continue
        candidates.append(Candidate(athlete=athletes[athlete_id], suggested_rank=rank, current=_rank_read(current), basis=_basis(application), pending_request=athlete_id in pending))
    return sorted(candidates, key=lambda item: (-RANK_ORDER.index(item.suggested_rank), item.athlete.full_name))


@router.get("/ranks/expiring", response_model=list[ExpiringRank])
async def expiring_ranks(days: Annotated[int, Query(ge=1, le=365)] = EXPIRY_WARNING_DAYS, _admin: User = Depends(admin_read), db: AsyncSession = Depends(get_session)) -> list[ExpiringRank]:
    latest = await _latest_ranks(db, set(await db.scalars(select(AthleteRank.athlete_id))))
    today = date.today()
    items = [item for item in latest.values() if (item.expires_on - today).days <= days]
    athletes = await athlete_briefs(db, {item.athlete_id for item in items})
    return [ExpiringRank(athlete=athletes[item.athlete_id], rank=_rank_read(item)) for item in sorted(items, key=lambda item: item.expires_on)]


@router.get("/rank-norms", response_model=list[RankNormRow])
async def get_rank_norms(_admin: User = Depends(admin_read), db: AsyncSession = Depends(get_session)) -> list[RankNorm]:
    return list(await db.scalars(select(RankNorm).order_by(RankNorm.level, RankNorm.max_place)))


@router.put("/rank-norms", response_model=list[RankNormRow])
async def replace_rank_norms(payload: list[RankNormRow], _admin: User = Depends(admin_write), db: AsyncSession = Depends(get_session)) -> list[RankNorm]:
    for item in await db.scalars(select(RankNorm)):
        await db.delete(item)
    db.add_all(RankNorm(**row.model_dump()) for row in payload)
    await db.commit()
    return await get_rank_norms(_admin, db)
