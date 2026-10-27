from collections import defaultdict
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application_models import Application, ApplicationStatus, Result, ResultStatus
from app.application_schemas import (
    ApplicationRead, AthleteBrief, CompetitionBrief, DecisionRequest, Eligibility, HistoryItem, ProtocolGroup,
    ProtocolRead, ProtocolRow, ResultRead, ResultsWrite,
)
from app.auth_models import AuthSession, User
from app.auth_routes import current_auth_session, is_active_admin, optional_auth_session, require_roles
from app.auth_security import utcnow
from app.database import get_session
from app.models import AgeGroup, Competition, CompetitionStatus
from app.profile_models import AthleteProfile, Profile
from app.protocol import Entry, competition_age, fitting_groups, rank
from app.schemas import AgeGroupRead


router = APIRouter(prefix="/api/v1", tags=["applications"])
admin_only = require_roles("federation_admin", csrf=True)


# ---------- helpers ----------

async def _competition(db: AsyncSession, competition_id: int) -> Competition:
    competition = await db.get(Competition, competition_id)
    if competition is None or competition.is_archived:
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    return competition


async def _athletes(db: AsyncSession, user_ids: set[int]) -> dict[int, AthleteBrief]:
    if not user_ids:
        return {}
    profiles = {item.user_id: item for item in await db.scalars(select(Profile).where(Profile.user_id.in_(user_ids)))}
    athletes = {item.user_id: item for item in await db.scalars(select(AthleteProfile).where(AthleteProfile.user_id.in_(user_ids)))}
    briefs = {}
    for user_id in user_ids:
        profile, athlete = profiles.get(user_id), athletes.get(user_id)
        name = " ".join(part for part in (profile.last_name, profile.first_name, profile.middle_name) if part) if profile else f"Спортсмен #{user_id}"
        briefs[user_id] = AthleteBrief(
            id=user_id,
            full_name=name,
            birth_date=profile.birth_date if profile else None,
            municipality=profile.municipality.name if profile and profile.municipality else None,
            organization=athlete.organization.name if athlete and athlete.organization else None,
        )
    return briefs


def _read(application: Application, athletes: dict[int, AthleteBrief]) -> ApplicationRead:
    return ApplicationRead(
        id=application.id,
        competition=CompetitionBrief.model_validate(application.competition),
        athlete=athletes[application.athlete_id],
        age_group=AgeGroupRead.model_validate(application.age_group),
        status=application.status,
        submitted_role=application.submitted_role,
        moderator_comment=application.moderator_comment,
        created_at=application.created_at,
        decided_at=application.decided_at,
        result=ResultRead.model_validate(application.result) if application.result else None,
    )


async def _check_eligibility(db: AsyncSession, competition: Competition, athlete_id: int, today: date | None = None) -> tuple[list[str], int | None, list[AgeGroup]]:
    """Return (reasons it is not allowed, competition age, fitting age groups)."""
    today = today or date.today()
    reasons: list[str] = []
    if competition.status != CompetitionStatus.REGISTRATION_OPEN:
        reasons.append("Приём заявок на это соревнование не открыт")
    elif not (competition.registration_start <= today <= competition.registration_end):
        reasons.append("Сейчас не период приёма заявок")

    profile = await db.get(Profile, athlete_id)
    athlete = await db.get(AthleteProfile, athlete_id)
    if athlete is None:
        reasons.append("Заполните раздел «Спортсмен» в профиле")
    elif competition.discipline_id not in {item.id for item in athlete.disciplines}:
        reasons.append(f"В профиле не указана дисциплина «{competition.discipline.name}»")

    age = None
    groups: list[AgeGroup] = []
    if profile is None or profile.birth_date is None:
        reasons.append("Укажите дату рождения в профиле")
    else:
        age = competition_age(profile.birth_date, competition.date)
        groups = fitting_groups(age, competition.age_groups)
        if not groups:
            names = ", ".join(group.name for group in competition.age_groups)
            reasons.append(f"Возраст в год соревнования — {age}; соревнование проводится для групп: {names}")
        if athlete is not None and age < 18 and athlete.guardian_consent_at is None:
            reasons.append("Нужно согласие законного представителя на обработку персональных данных")
    return reasons, age, groups


async def _existing(db: AsyncSession, competition_id: int, athlete_id: int) -> Application | None:
    return await db.scalar(select(Application).where(Application.competition_id == competition_id, Application.athlete_id == athlete_id))


# ---------- athlete ----------

@router.get("/competitions/{competition_id}/eligibility", response_model=Eligibility)
async def eligibility(
    competition_id: Annotated[int, Path(gt=0)],
    auth_session: AuthSession = Depends(current_auth_session),
    db: AsyncSession = Depends(get_session),
) -> Eligibility:
    competition = await _competition(db, competition_id)
    if auth_session.active_role != "athlete":
        return Eligibility(eligible=False, reasons=["Заявку подают из кабинета спортсмена"], age=None, age_group=None, application_id=None, application_status=None)
    reasons, age, groups = await _check_eligibility(db, competition, auth_session.user_id)
    existing = await _existing(db, competition.id, auth_session.user_id)
    if existing is not None and existing.status in {ApplicationStatus.PENDING, ApplicationStatus.APPROVED}:
        reasons.insert(0, "Заявка уже подана")
    return Eligibility(
        eligible=not reasons,
        reasons=reasons,
        age=age,
        age_group=AgeGroupRead.model_validate(groups[0]) if groups else None,
        application_id=existing.id if existing else None,
        application_status=existing.status if existing else None,
    )


class ApplyRequest(BaseModel):
    age_group_id: int | None = None


@router.post("/competitions/{competition_id}/applications", response_model=ApplicationRead, status_code=201)
async def apply(
    competition_id: Annotated[int, Path(gt=0)],
    payload: ApplyRequest | None = None,
    user: User = Depends(require_roles("athlete", csrf=True)),
    db: AsyncSession = Depends(get_session),
) -> ApplicationRead:
    competition = await _competition(db, competition_id)
    reasons, _age, groups = await _check_eligibility(db, competition, user.id)
    if reasons:
        raise HTTPException(status_code=422, detail="; ".join(reasons))
    group = groups[0]
    if payload and payload.age_group_id is not None:
        group = next((item for item in groups if item.id == payload.age_group_id), None)
        if group is None:
            raise HTTPException(status_code=422, detail="Спортсмен не проходит в выбранную возрастную группу")

    application = await _existing(db, competition.id, user.id)
    if application is not None and application.status in {ApplicationStatus.PENDING, ApplicationStatus.APPROVED}:
        raise HTTPException(status_code=409, detail="Заявка на это соревнование уже подана")
    if application is None:
        application = Application(competition_id=competition.id, athlete_id=user.id)
        db.add(application)
    # Отозванную или отклонённую заявку можно подать повторно.
    application.age_group_id = group.id
    application.submitted_by_id = user.id
    application.submitted_role = "athlete"
    application.status = ApplicationStatus.PENDING
    application.moderator_comment = None
    application.created_at = utcnow()
    application.decided_at = None
    application.decided_by_id = None
    await db.commit()
    await db.refresh(application, ["competition", "age_group", "result"])
    return _read(application, await _athletes(db, {user.id}))


@router.get("/me/applications", response_model=list[ApplicationRead])
async def my_applications(user: User = Depends(require_roles("athlete")), db: AsyncSession = Depends(get_session)) -> list[ApplicationRead]:
    items = list(await db.scalars(select(Application).where(Application.athlete_id == user.id).order_by(Application.created_at.desc())))
    athletes = await _athletes(db, {user.id})
    return [_read(item, athletes) for item in items]


@router.post("/applications/{application_id}/withdraw", response_model=ApplicationRead)
async def withdraw(
    application_id: Annotated[int, Path(gt=0)],
    user: User = Depends(require_roles("athlete", csrf=True)),
    db: AsyncSession = Depends(get_session),
) -> ApplicationRead:
    application = await db.get(Application, application_id)
    if application is None or application.athlete_id != user.id:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if application.status not in {ApplicationStatus.PENDING, ApplicationStatus.APPROVED} or application.result is not None:
        raise HTTPException(status_code=409, detail="Эту заявку уже нельзя отозвать")
    application.status = ApplicationStatus.WITHDRAWN
    await db.commit()
    return _read(application, await _athletes(db, {user.id}))


@router.get("/me/results", response_model=list[HistoryItem])
async def my_results(user: User = Depends(require_roles("athlete")), db: AsyncSession = Depends(get_session)) -> list[HistoryItem]:
    """История выступлений: только опубликованные протоколы."""
    rows = list(await db.scalars(
        select(Application)
        .join(Competition, Competition.id == Application.competition_id)
        .join(Result, Result.application_id == Application.id)
        .where(Application.athlete_id == user.id, Competition.protocol_published_at.is_not(None))
        .order_by(Competition.date.desc())
    ))
    history = []
    for application in rows:
        participants = len(list(await db.scalars(
            select(Application.id).where(
                Application.competition_id == application.competition_id,
                Application.age_group_id == application.age_group_id,
                Application.status == ApplicationStatus.APPROVED,
            )
        )))
        history.append(HistoryItem(
            competition=CompetitionBrief.model_validate(application.competition),
            age_group=AgeGroupRead.model_validate(application.age_group),
            place=application.result.place,
            score=application.result.score,
            result_status=application.result.result_status,
            participants=participants,
        ))
    return history


# ---------- federation ----------

@router.get("/competitions/{competition_id}/applications", response_model=list[ApplicationRead])
async def competition_applications(
    competition_id: Annotated[int, Path(gt=0)],
    status: ApplicationStatus | None = Query(default=None),
    _admin: User = Depends(require_roles("federation_admin")),
    db: AsyncSession = Depends(get_session),
) -> list[ApplicationRead]:
    await _competition(db, competition_id)
    statement = select(Application).where(Application.competition_id == competition_id)
    if status is not None:
        statement = statement.where(Application.status == status)
    items = list(await db.scalars(statement.order_by(Application.created_at)))
    athletes = await _athletes(db, {item.athlete_id for item in items})
    return sorted((_read(item, athletes) for item in items), key=lambda item: (item.age_group.min_age, item.athlete.full_name))


@router.post("/applications/{application_id}/decision", response_model=ApplicationRead)
async def decide(
    application_id: Annotated[int, Path(gt=0)],
    payload: DecisionRequest,
    admin: User = Depends(admin_only),
    db: AsyncSession = Depends(get_session),
) -> ApplicationRead:
    application = await db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if application.status != ApplicationStatus.PENDING:
        raise HTTPException(status_code=409, detail="Решение по заявке уже принято")
    application.status = ApplicationStatus(payload.status)
    application.moderator_comment = payload.comment
    application.decided_at = utcnow()
    application.decided_by_id = admin.id
    await db.commit()
    return _read(application, await _athletes(db, {application.athlete_id}))


async def _approved(db: AsyncSession, competition_id: int) -> list[Application]:
    return list(await db.scalars(select(Application).where(Application.competition_id == competition_id, Application.status == ApplicationStatus.APPROVED)))


def _rerank(applications: list[Application]) -> None:
    """Пересчитать места внутри каждой возрастной группы."""
    by_group: dict[int, list[Application]] = defaultdict(list)
    for application in applications:
        if application.result is not None:
            by_group[application.age_group_id].append(application)
    for items in by_group.values():
        places = rank([Entry(item.id, item.result.score, item.result.result_status) for item in items])
        for item in items:
            item.result.place = places[item.id]


@router.put("/competitions/{competition_id}/results", response_model=ProtocolRead)
async def save_results(
    competition_id: Annotated[int, Path(gt=0)],
    payload: ResultsWrite,
    _admin: User = Depends(admin_only),
    db: AsyncSession = Depends(get_session),
) -> ProtocolRead:
    competition = await _competition(db, competition_id)
    if competition.protocol_published_at is not None:
        raise HTTPException(status_code=409, detail="Протокол опубликован. Снимите публикацию, чтобы внести изменения")
    approved = {item.id: item for item in await _approved(db, competition.id)}
    ids = [item.application_id for item in payload.results]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="Участник указан дважды")
    unknown = set(ids) - approved.keys()
    if unknown:
        raise HTTPException(status_code=422, detail="Результаты можно вносить только участникам с одобренной заявкой")
    now = utcnow()
    for item in payload.results:
        application = approved[item.application_id]
        if application.result is None:
            application.result = Result(result_status=item.result_status, score=item.score, updated_at=now)
        else:
            application.result.result_status, application.result.score, application.result.updated_at = item.result_status, item.score, now
    _rerank(list(approved.values()))
    await db.commit()
    return await _protocol(db, competition)


async def _protocol(db: AsyncSession, competition: Competition) -> ProtocolRead:
    approved = await _approved(db, competition.id)
    athletes = await _athletes(db, {item.athlete_id for item in approved})
    groups = []
    for group in competition.age_groups:
        members = [item for item in approved if item.age_group_id == group.id]
        if not members:
            continue
        rows = [
            ProtocolRow(
                application_id=item.id,
                place=item.result.place if item.result else None,
                athlete=athletes[item.athlete_id],
                score=item.result.score if item.result else None,
                result_status=item.result.result_status if item.result else None,
            )
            for item in members
        ]
        # Сначала места по порядку, затем не явившиеся/дисквалифицированные, затем без результата.
        rows.sort(key=lambda row: (row.place is None, row.place or 0, row.result_status is None, row.athlete.full_name))
        groups.append(ProtocolGroup(age_group=AgeGroupRead.model_validate(group), rows=rows))
    return ProtocolRead(
        competition=CompetitionBrief.model_validate(competition),
        location=competition.location,
        published_at=competition.protocol_published_at,
        is_complete=bool(approved) and all(item.result is not None for item in approved),
        groups=groups,
    )


@router.get("/competitions/{competition_id}/protocol", response_model=ProtocolRead)
async def get_protocol(
    competition_id: Annotated[int, Path(gt=0)],
    viewer: AuthSession | None = Depends(optional_auth_session),
    db: AsyncSession = Depends(get_session),
) -> ProtocolRead:
    competition = await _competition(db, competition_id)
    if competition.protocol_published_at is None and not is_active_admin(viewer):
        raise HTTPException(status_code=404, detail="Протокол ещё не опубликован")
    return await _protocol(db, competition)


@router.post("/competitions/{competition_id}/protocol/publish", response_model=ProtocolRead)
async def publish_protocol(
    competition_id: Annotated[int, Path(gt=0)],
    _admin: User = Depends(admin_only),
    db: AsyncSession = Depends(get_session),
) -> ProtocolRead:
    competition = await _competition(db, competition_id)
    protocol = await _protocol(db, competition)
    if not protocol.is_complete:
        raise HTTPException(status_code=409, detail="Внесите результаты всем допущенным участникам")
    competition.protocol_published_at = utcnow()
    competition.status = CompetitionStatus.COMPLETED
    await db.commit()
    return await _protocol(db, competition)


@router.post("/competitions/{competition_id}/protocol/unpublish", response_model=ProtocolRead)
async def unpublish_protocol(
    competition_id: Annotated[int, Path(gt=0)],
    _admin: User = Depends(admin_only),
    db: AsyncSession = Depends(get_session),
) -> ProtocolRead:
    competition = await _competition(db, competition_id)
    competition.protocol_published_at = None
    await db.commit()
    return await _protocol(db, competition)
