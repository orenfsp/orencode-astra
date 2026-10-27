"""Контроль сроков: что видит каждая роль, дашборд федерации и фоновые напоминания."""

import asyncio
import logging
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application_models import Application, ApplicationStatus
from app.auth_models import AuthSession, Role, User, user_roles
from app.auth_routes import current_auth_session, require_roles
from app.coaching import active_athlete_ids
from app.coaching_models import CoachLink, LinkStatus
from app.database import get_session
from app.models import Competition, CompetitionStatus, Organization
from app.notifications import admin_ids, notify, send_pending_emails
from app.people import names
from app.profile_models import AthleteProfile, athlete_disciplines
from app.qualification_models import (
    AthleteRank, JudgeCategoryRequest, JudgeProfile, RankRequest, RequestStatus,
)
from app.qualifications import CATEGORY_LABELS, EXPIRY_WARNING_DAYS, RANK_LABELS, _latest_ranks


log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["deadlines"])
REGISTRATION_WINDOW_DAYS = 30
REMINDER_DAYS = 30


class Deadline(BaseModel):
    kind: str
    title: str
    date: date
    days_left: int
    severity: Literal["info", "warning", "danger"]
    link: str | None = None


def _deadline(kind: str, title: str, when: date, today: date, link: str | None = None, warn_days: int = 7) -> Deadline:
    days = (when - today).days
    severity = "danger" if days < 0 else "warning" if days <= warn_days else "info"
    return Deadline(kind=kind, title=title, date=when, days_left=days, severity=severity, link=link)


def governor_deadline(today: date) -> date:
    """Ходатайства на премии Губернатора — до 1 февраля."""
    this_year = date(today.year, 2, 1)
    return this_year if today <= this_year else date(today.year + 1, 2, 1)


async def _open_registrations(db: AsyncSession, today: date, discipline_ids: set[int] | None = None) -> list[Competition]:
    statement = select(Competition).where(
        Competition.status == CompetitionStatus.REGISTRATION_OPEN, Competition.is_archived.is_(False),
        Competition.registration_end >= today, Competition.registration_end <= today + timedelta(days=REGISTRATION_WINDOW_DAYS),
    ).order_by(Competition.registration_end)
    if discipline_ids is not None:
        statement = statement.where(Competition.discipline_id.in_(discipline_ids or {0}))
    return list(await db.scalars(statement))


async def deadlines_for(db: AsyncSession, user_id: int, role: str, today: date | None = None) -> list[Deadline]:
    today = today or date.today()
    items: list[Deadline] = []
    if role == "athlete":
        athlete = await db.get(AthleteProfile, user_id)
        disciplines = {item.id for item in athlete.disciplines} if athlete else set()
        for competition in await _open_registrations(db, today, disciplines):
            items.append(_deadline("registration", f"Приём заявок: {competition.title}", competition.registration_end, today, f"/competitions/{competition.id}"))
        rank = (await _latest_ranks(db, {user_id})).get(user_id)
        if rank:
            items.append(_deadline("rank_expiry", f"Срок действия: {RANK_LABELS[rank.rank]}", rank.expires_on, today, "/cabinet", EXPIRY_WARNING_DAYS))
    elif role == "coach":
        athletes = await active_athlete_ids(db, user_id)
        disciplines = set(await db.scalars(select(CoachLink.discipline_id).where(CoachLink.coach_id == user_id, CoachLink.status == LinkStatus.ACTIVE)))
        for competition in await _open_registrations(db, today, disciplines):
            items.append(_deadline("registration", f"Приём заявок: {competition.title}", competition.registration_end, today, f"/competitions/{competition.id}"))
        people = await names(db, athletes)
        for athlete_id, rank in (await _latest_ranks(db, athletes)).items():
            items.append(_deadline("rank_expiry", f"{people[athlete_id]}: {RANK_LABELS[rank.rank]}", rank.expires_on, today, "/cabinet", EXPIRY_WARNING_DAYS))
    elif role == "judge":
        profile = await db.get(JudgeProfile, user_id)
        if profile and profile.category_expires_on:
            items.append(_deadline("category_expiry", f"Срок действия: {CATEGORY_LABELS[profile.category]}", profile.category_expires_on, today, "/cabinet", EXPIRY_WARNING_DAYS))
    elif role == "federation_admin":
        for competition in await _open_registrations(db, today):
            items.append(_deadline("registration", f"Окончание приёма заявок: {competition.title}", competition.registration_end, today, f"/admin/competitions/{competition.id}"))
        latest = await _latest_ranks(db, set(await db.scalars(select(AthleteRank.athlete_id))))
        people = await names(db, set(latest))
        for athlete_id, rank in latest.items():
            if (rank.expires_on - today).days <= EXPIRY_WARNING_DAYS:
                items.append(_deadline("rank_expiry", f"Разряд истекает: {people[athlete_id]}, {RANK_LABELS[rank.rank]}", rank.expires_on, today, "/admin/ranks", EXPIRY_WARNING_DAYS))
        judges = list(await db.scalars(select(JudgeProfile).where(JudgeProfile.category_expires_on.is_not(None))))
        judge_names = await names(db, {item.user_id for item in judges})
        for profile in judges:
            if (profile.category_expires_on - today).days <= EXPIRY_WARNING_DAYS:
                items.append(_deadline("category_expiry", f"Категория истекает: {judge_names[profile.user_id]}", profile.category_expires_on, today, "/admin/judges", EXPIRY_WARNING_DAYS))
        items.append(_deadline("governor", "Ходатайства на премии Губернатора", governor_deadline(today), today, None, 30))
    return sorted(items, key=lambda item: item.date)


@router.get("/me/deadlines", response_model=list[Deadline])
async def my_deadlines(auth_session: AuthSession = Depends(current_auth_session), db: AsyncSession = Depends(get_session)) -> list[Deadline]:
    return await deadlines_for(db, auth_session.user_id, auth_session.active_role)


# ---------- дашборд федерации ----------

class Attention(BaseModel):
    title: str
    count: int
    link: str


class UpcomingCompetition(BaseModel):
    id: int
    title: str
    date: date
    discipline: str
    status: CompetitionStatus
    approved: int
    pending: int


class Dashboard(BaseModel):
    athletes: int
    coaches: int
    judges: int
    organizations: int
    competitions_this_year: int
    participants_this_year: int
    ranks_this_year: int
    attention: list[Attention]
    upcoming: list[UpcomingCompetition]
    deadlines: list[Deadline]


async def _role_count(db: AsyncSession, role: str) -> int:
    return await db.scalar(select(func.count()).select_from(user_roles).join(Role, Role.id == user_roles.c.role_id).where(Role.name == role)) or 0


@router.get("/admin/dashboard", response_model=Dashboard)
async def dashboard(admin: User = Depends(require_roles("federation_admin")), db: AsyncSession = Depends(get_session)) -> Dashboard:
    today = date.today()
    year_start, year_end = date(today.year, 1, 1), date(today.year, 12, 31)
    count = lambda statement: db.scalar(statement)  # noqa: E731 - короткая запись для набора счётчиков
    pending_applications = await count(select(func.count()).select_from(Application).where(Application.status == ApplicationStatus.PENDING)) or 0
    pending_ranks = await count(select(func.count()).select_from(RankRequest).where(RankRequest.status == RequestStatus.PENDING)) or 0
    pending_judges = await count(select(func.count()).select_from(JudgeCategoryRequest).where(JudgeCategoryRequest.status == RequestStatus.PENDING)) or 0
    deadlines = await deadlines_for(db, admin.id, "federation_admin", today)
    expiring = sum(1 for item in deadlines if item.kind in {"rank_expiry", "category_expiry"})
    unpublished = await count(select(func.count()).select_from(Competition).where(
        Competition.date < today, Competition.protocol_published_at.is_(None), Competition.is_archived.is_(False), Competition.status != CompetitionStatus.DRAFT,
    )) or 0
    attention = [item for item in (
        Attention(title="Заявки на соревнования на модерации", count=pending_applications, link="/admin/competitions"),
        Attention(title="Заявки на разряд", count=pending_ranks, link="/admin/ranks"),
        Attention(title="Заявки на судейскую категорию", count=pending_judges, link="/admin/judges"),
        Attention(title="Истекающие разряды и категории", count=expiring, link="/admin/ranks"),
        Attention(title="Прошедшие соревнования без опубликованного протокола", count=unpublished, link="/admin/competitions"),
    ) if item.count]

    upcoming = []
    for competition in await db.scalars(select(Competition).where(Competition.date >= today, Competition.is_archived.is_(False)).order_by(Competition.date).limit(5)):
        stats = dict((status, total) for status, total in await db.execute(
            select(Application.status, func.count()).where(Application.competition_id == competition.id).group_by(Application.status)
        ))
        upcoming.append(UpcomingCompetition(
            id=competition.id, title=competition.title, date=competition.date, discipline=competition.discipline.name, status=competition.status,
            approved=stats.get(ApplicationStatus.APPROVED, 0), pending=stats.get(ApplicationStatus.PENDING, 0),
        ))

    return Dashboard(
        athletes=await count(select(func.count()).select_from(AthleteProfile)) or 0,
        coaches=await _role_count(db, "coach"),
        judges=await _role_count(db, "judge"),
        organizations=await count(select(func.count()).select_from(Organization).where(Organization.is_active.is_(True))) or 0,
        competitions_this_year=await count(select(func.count()).select_from(Competition).where(Competition.date.between(year_start, year_end), Competition.is_archived.is_(False), Competition.status != CompetitionStatus.DRAFT)) or 0,
        participants_this_year=await count(
            select(func.count(func.distinct(Application.athlete_id))).join(Competition, Competition.id == Application.competition_id)
            .where(Application.status == ApplicationStatus.APPROVED, Competition.date.between(year_start, year_end))
        ) or 0,
        ranks_this_year=await count(select(func.count()).select_from(AthleteRank).where(AthleteRank.assigned_on.between(year_start, year_end))) or 0,
        attention=attention,
        upcoming=upcoming,
        deadlines=deadlines,
    )


# ---------- напоминания ----------

async def generate_reminders(db: AsyncSession, today: date | None = None) -> int:
    """Создать напоминания о сроках. Повторный запуск безопасен: каждое напоминание уходит один раз."""
    today = today or date.today()
    created = 0
    soon = today + timedelta(days=REMINDER_DAYS)
    latest = await _latest_ranks(db, set(await db.scalars(select(AthleteRank.athlete_id))))
    for athlete_id, rank in latest.items():
        if rank.expires_on > soon:
            continue
        stage = "expired" if rank.expires_on < today else "soon"
        coaches = set(await db.scalars(select(CoachLink.coach_id).where(CoachLink.athlete_id == athlete_id, CoachLink.status == LinkStatus.ACTIVE)))
        title = "Срок разряда истёк" if stage == "expired" else "Скоро истекает срок разряда"
        body = f"{RANK_LABELS[rank.rank]} действует до {rank.expires_on:%d.%m.%Y}. Подайте заявку на подтверждение."
        created += await notify(db, {athlete_id} | coaches, "rank_expiry", title, body, "/cabinet", dedupe_key=f"rank:{rank.id}:{stage}")
        created += await notify(db, await admin_ids(db), "rank_expiry", title, f"{(await names(db, {athlete_id}))[athlete_id]}: {body}", "/admin/ranks", dedupe_key=f"rank:{rank.id}:{stage}")
    for profile in await db.scalars(select(JudgeProfile).where(JudgeProfile.category_expires_on.is_not(None), JudgeProfile.category_expires_on <= soon)):
        stage = "expired" if profile.category_expires_on < today else "soon"
        body = f"{CATEGORY_LABELS[profile.category]} действует до {profile.category_expires_on:%d.%m.%Y}."
        created += await notify(db, {profile.user_id}, "category_expiry", "Срок судейской категории", body, "/cabinet", dedupe_key=f"category:{profile.user_id}:{profile.category_expires_on}:{stage}")
    for competition in await _open_registrations(db, today):
        if (competition.registration_end - today).days > 3:
            continue
        applied = set(await db.scalars(select(Application.athlete_id).where(Application.competition_id == competition.id)))
        athletes = set(await db.scalars(select(athlete_disciplines.c.user_id).where(athlete_disciplines.c.discipline_id == competition.discipline_id))) - applied
        created += await notify(db, athletes, "registration_closing", "Заканчивается приём заявок",
                                f"«{competition.title}»: заявки до {competition.registration_end:%d.%m.%Y}.", f"/competitions/{competition.id}",
                                dedupe_key=f"closing:{competition.id}")
    governor = governor_deadline(today)
    if (governor - today).days <= 30:
        created += await notify(db, await admin_ids(db), "governor", "Ходатайства на премии Губернатора",
                                f"Срок подачи — до {governor:%d.%m.%Y}.", None, dedupe_key=f"governor:{governor.year}")
    await db.commit()
    return created


class ReminderRun(BaseModel):
    created: int


@router.post("/admin/reminders/run", response_model=ReminderRun)
async def run_reminders(_admin: User = Depends(require_roles("federation_admin", csrf=True)), db: AsyncSession = Depends(get_session)) -> ReminderRun:
    return ReminderRun(created=await generate_reminders(db))


async def background_worker(session_factory, stop: asyncio.Event) -> None:
    """Раз в минуту отправляет email, раз в 6 часов создаёт напоминания о сроках."""
    ticks = 0
    while not stop.is_set():
        try:
            if ticks % 360 == 0:
                async with session_factory() as db:
                    await generate_reminders(db)
            await send_pending_emails(session_factory)
        except Exception:  # noqa: BLE001 - фоновая задача не должна падать
            log.exception("Background worker iteration failed")
        ticks += 1
        try:
            await asyncio.wait_for(stop.wait(), timeout=60)
        except TimeoutError:
            pass
