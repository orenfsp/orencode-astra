"""Тренер и спортсмены: поиск в реестре, запрос на привязку, подтверждение, статусы и история."""

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application_models import Application
from app.application_schemas import ApplicationRead, AthleteBrief, HistoryItem
from app.applications import _read as read_application, my_results_for
from app.auth_models import User
from app.auth_routes import require_roles
from app.auth_security import utcnow
from app.coaching_models import CoachLink, CoachLinkEvent, LinkStatus
from app.database import get_session
from app.models import Discipline
from app.notifications import notify
from app.people import athlete_briefs, names
from app.profile_models import AthleteProfile, Profile, athlete_disciplines
from app.qualification_models import AthleteRank
from app.schemas import DisciplineRead


router = APIRouter(prefix="/api/v1", tags=["coaching"])
coach_role = require_roles("coach")
coach_write = require_roles("coach", csrf=True)
athlete_role = require_roles("athlete")
athlete_write = require_roles("athlete", csrf=True)

OPEN_STATUSES = {LinkStatus.PENDING, LinkStatus.ACTIVE, LinkStatus.SUSPENDED}


class SearchResult(AthleteBrief):
    disciplines: list[DisciplineRead]


class LinkEventRead(BaseModel):
    status: LinkStatus
    changed_by: str | None
    note: str | None
    created_at: datetime


class LinkRead(BaseModel):
    id: int
    coach_id: int
    coach_name: str
    athlete: AthleteBrief
    discipline: DisciplineRead
    status: LinkStatus
    created_at: datetime
    updated_at: datetime
    history: list[LinkEventRead]


class LinkCreate(BaseModel):
    athlete_id: int = Field(gt=0)
    discipline_id: int = Field(gt=0)


class LinkResponse(BaseModel):
    accept: bool


class LinkStatusChange(BaseModel):
    status: Literal["active", "suspended", "ended"]
    note: str | None = Field(default=None, max_length=500)


class RankInfo(BaseModel):
    rank: str
    assigned_on: date
    expires_on: date
    order_ref: str


class CoachAthleteSummary(BaseModel):
    athlete: AthleteBrief
    disciplines: list[DisciplineRead]
    rank: RankInfo | None
    results: list[HistoryItem]


def _event(link: CoachLink, status: LinkStatus, user_id: int, note: str | None = None) -> None:
    now = utcnow()
    link.status, link.updated_at = status, now
    link.events.append(CoachLinkEvent(status=status, changed_by_id=user_id, note=note, created_at=now))


async def _read_links(db: AsyncSession, links: list[CoachLink]) -> list[LinkRead]:
    people = await names(db, {link.coach_id for link in links} | {event.changed_by_id for link in links for event in link.events if event.changed_by_id})
    athletes = await athlete_briefs(db, {link.athlete_id for link in links})
    return [
        LinkRead(
            id=link.id, coach_id=link.coach_id, coach_name=people[link.coach_id], athlete=athletes[link.athlete_id],
            discipline=DisciplineRead.model_validate(link.discipline), status=link.status, created_at=link.created_at, updated_at=link.updated_at,
            history=[LinkEventRead(status=event.status, changed_by=people.get(event.changed_by_id) if event.changed_by_id else None, note=event.note, created_at=event.created_at) for event in link.events],
        )
        for link in links
    ]


async def current_rank(db: AsyncSession, athlete_id: int) -> AthleteRank | None:
    """Последний присвоенный разряд, даже если срок истёк (истечение показывается отдельно)."""
    return await db.scalar(select(AthleteRank).where(AthleteRank.athlete_id == athlete_id).order_by(AthleteRank.assigned_on.desc(), AthleteRank.id.desc()).limit(1))


async def has_active_coach(db: AsyncSession, athlete_id: int) -> bool:
    return await db.scalar(select(func.count()).select_from(CoachLink).where(CoachLink.athlete_id == athlete_id, CoachLink.status == LinkStatus.ACTIVE)) > 0


async def active_athlete_ids(db: AsyncSession, coach_id: int) -> set[int]:
    return set(await db.scalars(select(CoachLink.athlete_id).where(CoachLink.coach_id == coach_id, CoachLink.status == LinkStatus.ACTIVE)))


# ---------- тренер ----------

@router.get("/coach/athletes/search", response_model=list[SearchResult])
async def search_athletes(
    q: Annotated[str, Query(min_length=2, max_length=120)],
    discipline_id: Annotated[int | None, Query(gt=0)] = None,
    _coach: User = Depends(coach_role),
    db: AsyncSession = Depends(get_session),
) -> list[SearchResult]:
    """Поиск спортсменов в реестре по ФИО — минимум данных, достаточный для выбора."""
    pattern = f"%{q.strip().replace('%', '').replace('_', '')}%"
    statement = (
        select(AthleteProfile.user_id)
        .join(Profile, Profile.user_id == AthleteProfile.user_id)
        .where(or_(Profile.last_name.ilike(pattern), Profile.first_name.ilike(pattern), (Profile.last_name + " " + Profile.first_name).ilike(pattern)))
        .order_by(Profile.last_name, Profile.first_name)
        .limit(20)
    )
    if discipline_id is not None:
        statement = statement.where(AthleteProfile.user_id.in_(select(athlete_disciplines.c.user_id).where(athlete_disciplines.c.discipline_id == discipline_id)))
    ids = list(await db.scalars(statement))
    briefs = await athlete_briefs(db, set(ids))
    profiles = {item.user_id: item for item in await db.scalars(select(AthleteProfile).where(AthleteProfile.user_id.in_(ids)))}
    return [SearchResult(**briefs[user_id].model_dump(), disciplines=[DisciplineRead.model_validate(item) for item in profiles[user_id].disciplines]) for user_id in ids]


@router.get("/coach/links", response_model=list[LinkRead])
async def coach_links(coach: User = Depends(coach_role), db: AsyncSession = Depends(get_session)) -> list[LinkRead]:
    links = list(await db.scalars(select(CoachLink).where(CoachLink.coach_id == coach.id).order_by(CoachLink.updated_at.desc())))
    return await _read_links(db, links)


@router.post("/coach/links", response_model=LinkRead, status_code=201)
async def request_link(payload: LinkCreate, coach: User = Depends(coach_write), db: AsyncSession = Depends(get_session)) -> LinkRead:
    if payload.athlete_id == coach.id:
        raise HTTPException(status_code=422, detail="Нельзя привязать самого себя")
    athlete = await db.get(AthleteProfile, payload.athlete_id)
    if athlete is None:
        raise HTTPException(status_code=404, detail="Спортсмен не найден в реестре")
    discipline = await db.get(Discipline, payload.discipline_id)
    if discipline is None or discipline.id not in {item.id for item in athlete.disciplines}:
        raise HTTPException(status_code=422, detail="Спортсмен не занимается этой дисциплиной")
    duplicate = await db.scalar(select(CoachLink.id).where(
        CoachLink.coach_id == coach.id, CoachLink.athlete_id == payload.athlete_id,
        CoachLink.discipline_id == payload.discipline_id, CoachLink.status.in_(OPEN_STATUSES),
    ))
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Связь по этой дисциплине уже есть или ожидает подтверждения")
    now = utcnow()
    link = CoachLink(coach_id=coach.id, athlete_id=payload.athlete_id, discipline_id=discipline.id, created_at=now, updated_at=now, events=[])
    _event(link, LinkStatus.PENDING, coach.id, "Запрос тренера")
    db.add(link)
    coach_name = (await names(db, {coach.id}))[coach.id]
    await notify(db, {payload.athlete_id}, "link_request", "Запрос на привязку от тренера", f"{coach_name} просит подтвердить, что тренирует вас по дисциплине «{discipline.name}».", "/cabinet")
    await db.commit()
    await db.refresh(link, ["discipline", "events"])
    return (await _read_links(db, [link]))[0]


@router.post("/coach/links/{link_id}/status", response_model=LinkRead)
async def change_link_status(
    link_id: Annotated[int, Path(gt=0)],
    payload: LinkStatusChange,
    coach: User = Depends(coach_write),
    db: AsyncSession = Depends(get_session),
) -> LinkRead:
    link = await db.get(CoachLink, link_id)
    if link is None or link.coach_id != coach.id:
        raise HTTPException(status_code=404, detail="Связь не найдена")
    allowed = {
        LinkStatus.ACTIVE: {LinkStatus.SUSPENDED, LinkStatus.ENDED},
        LinkStatus.SUSPENDED: {LinkStatus.ACTIVE, LinkStatus.ENDED},
        LinkStatus.PENDING: {LinkStatus.ENDED},
    }
    target = LinkStatus(payload.status)
    if target not in allowed.get(link.status, set()):
        raise HTTPException(status_code=409, detail="Такой переход статуса невозможен")
    _event(link, target, coach.id, payload.note)
    await notify(db, {link.athlete_id}, "link_status", "Изменился статус связи с тренером", f"Дисциплина «{link.discipline.name}»: {target.value}.", "/cabinet")
    await db.commit()
    return (await _read_links(db, [link]))[0]


@router.get("/coach/applications", response_model=list[ApplicationRead])
async def coach_applications(coach: User = Depends(coach_role), db: AsyncSession = Depends(get_session)) -> list[ApplicationRead]:
    """Заявки привязанных спортсменов (в том числе поданные ими самими)."""
    athlete_ids = set(await db.scalars(select(CoachLink.athlete_id).where(CoachLink.coach_id == coach.id, CoachLink.status.in_({LinkStatus.ACTIVE, LinkStatus.SUSPENDED}))))
    items = list(await db.scalars(select(Application).where(Application.athlete_id.in_(athlete_ids)).order_by(Application.created_at.desc()))) if athlete_ids else []
    athletes = await athlete_briefs(db, {item.athlete_id for item in items})
    return [read_application(item, athletes) for item in items]


@router.get("/coach/athletes", response_model=list[CoachAthleteSummary])
async def coach_athletes(coach: User = Depends(coach_role), db: AsyncSession = Depends(get_session)) -> list[CoachAthleteSummary]:
    """Сводка по подопечным: дисциплины связи, разряд и выступления."""
    links = list(await db.scalars(select(CoachLink).where(CoachLink.coach_id == coach.id, CoachLink.status == LinkStatus.ACTIVE)))
    by_athlete: dict[int, list[Discipline]] = {}
    for link in links:
        by_athlete.setdefault(link.athlete_id, []).append(link.discipline)
    briefs = await athlete_briefs(db, set(by_athlete))
    summary = []
    for athlete_id, disciplines in by_athlete.items():
        rank = await current_rank(db, athlete_id)
        summary.append(CoachAthleteSummary(
            athlete=briefs[athlete_id],
            disciplines=[DisciplineRead.model_validate(item) for item in disciplines],
            rank=RankInfo(rank=rank.rank.value, assigned_on=rank.assigned_on, expires_on=rank.expires_on, order_ref=rank.order_ref) if rank else None,
            results=await my_results_for(db, athlete_id),
        ))
    return sorted(summary, key=lambda item: item.athlete.full_name)


# ---------- спортсмен ----------

@router.get("/me/coach-links", response_model=list[LinkRead])
async def my_coach_links(athlete: User = Depends(athlete_role), db: AsyncSession = Depends(get_session)) -> list[LinkRead]:
    links = list(await db.scalars(select(CoachLink).where(CoachLink.athlete_id == athlete.id).order_by(CoachLink.updated_at.desc())))
    return await _read_links(db, links)


@router.post("/me/coach-links/{link_id}/respond", response_model=LinkRead)
async def respond_link(
    link_id: Annotated[int, Path(gt=0)],
    payload: LinkResponse,
    athlete: User = Depends(athlete_write),
    db: AsyncSession = Depends(get_session),
) -> LinkRead:
    link = await db.get(CoachLink, link_id)
    if link is None or link.athlete_id != athlete.id:
        raise HTTPException(status_code=404, detail="Запрос не найден")
    if link.status != LinkStatus.PENDING:
        raise HTTPException(status_code=409, detail="Запрос уже рассмотрен")
    target = LinkStatus.ACTIVE if payload.accept else LinkStatus.DECLINED
    _event(link, target, athlete.id, "Подтверждено спортсменом" if payload.accept else "Отклонено спортсменом")
    athlete_name = (await names(db, {athlete.id}))[athlete.id]
    verdict = "подтвердил(а) привязку" if payload.accept else "отклонил(а) запрос"
    await notify(db, {link.coach_id}, "link_response", "Ответ спортсмена", f"{athlete_name} {verdict} по дисциплине «{link.discipline.name}».", "/cabinet")
    await db.commit()
    return (await _read_links(db, [link]))[0]
