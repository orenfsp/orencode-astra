from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application_models import Application, ApplicationStatus, Result, ResultStatus
from app.application_schemas import (
    ApplicationRead, AthleteBrief, CompetitionBrief, DecisionRequest, Eligibility, HistoryItem, JudgeScoreRead, ProtocolGroup,
    ProtocolRead, ProtocolRow, ResultRead, ResultsWrite, ResultWrite, TasksSummary,
)
from app.auth_models import AuthSession, User
from app.auth_routes import current_auth_session, is_active_admin, optional_auth_session, require_roles
from app.auth_security import utcnow
from app.coaching_models import CoachLink, LinkStatus
from app.database import get_session
from app.models import PROTOCOL_FORM_PRODUCT, AgeGroup, Competition, CompetitionStatus
from app.notifications import admin_ids, notify
from app.people import athlete_briefs, names
from app.profile_models import AthleteProfile, Profile
from app.protocol import PRODUCT_CRITERIA, Entry, competition_age, fitting_groups, judge_totals, normalize_mark, rank, solved_count
from app.qualification_models import JudgeAssignment
from app.schemas import AgeGroupRead


router = APIRouter(prefix="/api/v1", tags=["applications"])
admin_only = require_roles("federation_admin", csrf=True)


# ---------- helpers ----------

async def _competition(db: AsyncSession, competition_id: int) -> Competition:
    competition = await db.get(Competition, competition_id)
    if competition is None or competition.is_archived:
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    return competition


_athletes = athlete_briefs


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

async def coach_can_enter(db: AsyncSession, coach_id: int, athlete_id: int, discipline_id: int) -> bool:
    """Тренер подаёт заявки только за спортсменов с активной связью по дисциплине соревнования."""
    link = await db.scalar(select(CoachLink.id).where(
        CoachLink.coach_id == coach_id, CoachLink.athlete_id == athlete_id,
        CoachLink.discipline_id == discipline_id, CoachLink.status == LinkStatus.ACTIVE,
    ))
    return link is not None


async def _subject(db: AsyncSession, auth_session: AuthSession, competition: Competition, athlete_id: int | None) -> tuple[int | None, str | None]:
    """Resolve whose application this is for the active role; return (athlete_id, refusal)."""
    if auth_session.active_role == "athlete":
        return auth_session.user_id, None
    if auth_session.active_role == "coach":
        if athlete_id is None:
            return None, "Выберите спортсмена"
        if not await coach_can_enter(db, auth_session.user_id, athlete_id, competition.discipline_id):
            return None, f"Нет активной связи со спортсменом по дисциплине «{competition.discipline.name}»"
        return athlete_id, None
    return None, "Заявку подаёт спортсмен или его тренер"


@router.get("/competitions/{competition_id}/eligibility", response_model=Eligibility)
async def eligibility(
    competition_id: Annotated[int, Path(gt=0)],
    athlete_id: Annotated[int | None, Query(gt=0)] = None,
    auth_session: AuthSession = Depends(current_auth_session),
    db: AsyncSession = Depends(get_session),
) -> Eligibility:
    competition = await _competition(db, competition_id)
    subject, refusal = await _subject(db, auth_session, competition, athlete_id)
    if subject is None:
        return Eligibility(eligible=False, reasons=[refusal or ""], age=None, age_group=None, application_id=None, application_status=None)
    reasons, age, groups = await _check_eligibility(db, competition, subject)
    existing = await _existing(db, competition.id, subject)
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
    athlete_id: int | None = None


@router.post("/competitions/{competition_id}/applications", response_model=ApplicationRead, status_code=201)
async def apply(
    competition_id: Annotated[int, Path(gt=0)],
    payload: ApplyRequest | None = None,
    _user: User = Depends(require_roles("athlete", "coach", csrf=True)),
    auth_session: AuthSession = Depends(current_auth_session),
    db: AsyncSession = Depends(get_session),
) -> ApplicationRead:
    competition = await _competition(db, competition_id)
    athlete_id, refusal = await _subject(db, auth_session, competition, payload.athlete_id if payload else None)
    if athlete_id is None:
        # Попытка тренера подать заявку за чужого спортсмена — это отказ в правах, а не ошибка ввода.
        no_link = auth_session.active_role == "coach" and payload is not None and payload.athlete_id is not None
        raise HTTPException(status_code=403 if no_link else 422, detail=refusal)
    reasons, _age, groups = await _check_eligibility(db, competition, athlete_id)
    if reasons:
        raise HTTPException(status_code=422, detail="; ".join(reasons))
    group = groups[0]
    if payload and payload.age_group_id is not None:
        group = next((item for item in groups if item.id == payload.age_group_id), None)
        if group is None:
            raise HTTPException(status_code=422, detail="Спортсмен не проходит в выбранную возрастную группу")

    application = await _existing(db, competition.id, athlete_id)
    if application is not None and application.status in {ApplicationStatus.PENDING, ApplicationStatus.APPROVED}:
        raise HTTPException(status_code=409, detail="Заявка на это соревнование уже подана")
    if application is None:
        application = Application(competition_id=competition.id, athlete_id=athlete_id)
        db.add(application)
    # Отозванную или отклонённую заявку можно подать повторно.
    application.age_group_id = group.id
    application.submitted_by_id = auth_session.user_id
    application.submitted_role = auth_session.active_role
    application.status = ApplicationStatus.PENDING
    application.moderator_comment = None
    application.created_at = utcnow()
    application.decided_at = None
    application.decided_by_id = None
    athletes = await _athletes(db, {athlete_id})
    link = f"/admin/competitions/{competition.id}"
    await notify(db, await admin_ids(db), "application_new", "Новая заявка на соревнование", f"{athletes[athlete_id].full_name} — «{competition.title}»", link)
    if auth_session.active_role == "coach":
        await notify(db, {athlete_id}, "application_by_coach", "Тренер подал за вас заявку", f"Соревнование «{competition.title}». Статус заявки — в кабинете.", f"/competitions/{competition.id}")
    await db.commit()
    await db.refresh(application, ["competition", "age_group", "result"])
    return _read(application, athletes)


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
    return await my_results_for(db, user.id)


async def my_results_for(db: AsyncSession, athlete_id: int) -> list[HistoryItem]:
    """История выступлений: только опубликованные протоколы."""
    rows = list(await db.scalars(
        select(Application)
        .join(Competition, Competition.id == Application.competition_id)
        .join(Result, Result.application_id == Application.id)
        .where(Application.athlete_id == athlete_id, Competition.protocol_published_at.is_not(None))
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
            application_id=application.id,
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
    verdict = "одобрена" if application.status == ApplicationStatus.APPROVED else f"отклонена: {payload.comment}"
    await notify(
        db, {application.athlete_id, application.submitted_by_id}, "application_decision", "Решение по заявке",
        f"Заявка на «{application.competition.title}» {verdict}", f"/competitions/{application.competition_id}",
    )
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
        places = rank([Entry(item.id, item.result.score, item.result.result_status, item.result.penalty_minutes) for item in items])
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
        details = _result_details(competition, item, application.athlete_id)
        if application.result is None:
            application.result = Result(result_status=item.result_status, updated_at=now, **details)
        else:
            application.result.result_status, application.result.updated_at = item.result_status, now
            for field, value in details.items():
                setattr(application.result, field, value)
    _rerank(list(approved.values()))
    await db.commit()
    return await _protocol(db, competition)


def _result_details(competition: Competition, item: ResultWrite, athlete_id: int) -> dict:
    """Баллы и подробности результата по форме протокола соревнования.

    Протокол по задачам: баллы — число решённых задач, при равенстве выше тот, у кого меньше время.
    Протокол продуктового программирования: баллы — среднее итогов судей по пяти критериям.
    Без подробностей принимаются просто баллы (например, при импорте итоговой таблицы).
    """
    details = {"score": item.score, "task_marks": None, "penalty_minutes": None, "judge_scores": None}
    if item.task_marks is not None:
        if competition.protocol_form == PROTOCOL_FORM_PRODUCT:
            raise HTTPException(status_code=422, detail="В продуктовом программировании результат — оценки судей, а не задачи")
        if not competition.task_count:
            raise HTTPException(status_code=422, detail="Укажите в карточке соревнования, сколько задач предложено к решению")
        if len(item.task_marks) != competition.task_count:
            raise HTTPException(status_code=422, detail=f"Нужны отметки по всем {competition.task_count} задачам")
        try:
            marks = [normalize_mark(mark) for mark in item.task_marks]
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from None
        details |= {"score": Decimal(solved_count(marks)), "task_marks": marks, "penalty_minutes": item.penalty_minutes or 0}
    elif item.judge_scores is not None:
        if competition.protocol_form != PROTOCOL_FORM_PRODUCT:
            raise HTTPException(status_code=422, detail="Оценки судей по критериям ведутся только в продуктовом программировании")
        stored = [{"judge": judge.judge.strip(), "scores": [str(score) for score in judge.scores]} for judge in item.judge_scores]
        details |= {"score": judge_totals(stored)[2], "judge_scores": stored}
    elif item.result_status == ResultStatus.OK and item.score is None:
        raise HTTPException(status_code=422, detail=f"Нет результата для заявки {item.application_id} (спортсмен #{athlete_id})")
    elif item.result_status == ResultStatus.OK:
        details["penalty_minutes"] = item.penalty_minutes
    return details


def _row(item: Application, athlete: AthleteBrief) -> ProtocolRow:
    result = item.result
    row = ProtocolRow(
        application_id=item.id,
        place=result.place if result else None,
        athlete=athlete,
        score=result.score if result else None,
        result_status=result.result_status if result else None,
        penalty_minutes=result.penalty_minutes if result else None,
    )
    if result is not None and result.task_marks is not None:
        row.task_marks, row.solved = list(result.task_marks), solved_count(result.task_marks)
    if result is not None and result.judge_scores:
        judges, overall, _total = judge_totals(result.judge_scores)
        row.judge_scores = [JudgeScoreRead(judge=name, scores=scores, total=total) for name, scores, total in judges]
        row.overall_scores = overall
    return row


async def _protocol(db: AsyncSession, competition: Competition) -> ProtocolRead:
    approved = await _approved(db, competition.id)
    athletes = await _athletes(db, {item.athlete_id for item in approved})
    groups = []
    for group in competition.age_groups:
        members = [item for item in approved if item.age_group_id == group.id]
        if not members:
            continue
        rows = [_row(item, athletes[item.athlete_id]) for item in members]
        # Сначала места по порядку, затем не явившиеся/дисквалифицированные, затем без результата.
        rows.sort(key=lambda row: (row.place is None, row.place or 0, row.result_status is None, row.athlete.full_name))
        groups.append(ProtocolGroup(age_group=AgeGroupRead.model_validate(group), rows=rows))

    product = competition.protocol_form == PROTOCOL_FORM_PRODUCT
    summary = None
    marked = [row for group in groups for row in group.rows if row.task_marks is not None]
    if not product and marked:
        summary = TasksSummary(
            offered=competition.task_count,
            solved_all=sum(1 for row in marked if competition.task_count and row.solved == competition.task_count),
            solved_none=sum(1 for row in marked if row.solved == 0),
        )
    panel = list(await db.scalars(select(JudgeAssignment).where(JudgeAssignment.competition_id == competition.id)))
    panel_names = await names(db, {item.judge_id for item in panel})
    by_position = {item.position.name: panel_names[item.judge_id] for item in panel}
    return ProtocolRead(
        competition=CompetitionBrief.model_validate(competition),
        location=competition.location,
        published_at=competition.protocol_published_at,
        is_complete=bool(approved) and all(item.result is not None for item in approved),
        form=competition.protocol_form,
        task_count=competition.task_count,
        criteria=PRODUCT_CRITERIA if product else [],
        tasks_summary=summary,
        chief_judge=by_position.get("Главный судья"),
        chief_secretary=by_position.get("Главный секретарь"),
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
    participants = {item.athlete_id for item in await _approved(db, competition.id)}
    await notify(
        db, participants, "protocol_published", "Опубликован протокол", f"Результаты соревнования «{competition.title}» доступны в истории выступлений.",
        f"/competitions/{competition.id}/protocol", dedupe_key=f"protocol:{competition.id}",
    )
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
