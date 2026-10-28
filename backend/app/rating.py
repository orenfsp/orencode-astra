"""Рейтинг спортсменов за сезон по дисциплине, дисквалификации и формирование сборной."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application_models import Application, ApplicationStatus, Result, ResultStatus
from app.application_schemas import AthleteBrief
from app.auth_models import User
from app.auth_routes import require_roles
from app.auth_security import utcnow
from app.database import get_session
from app.models import AgeGroup, Competition, CompetitionLevel, CompetitionType, Discipline
from app.people import athlete_briefs
from app.profile_models import AthleteProfile
from app.protocol import fitting_groups
from app.qualification_models import RANK_ORDER, SportRank
from app.qualifications import _latest_ranks
from app.rating_models import RatingPoints, RatingSettings, Sanction, SanctionKind, Team, TeamMember
from app.schemas import AgeGroupRead, DisciplineRead, RefItem


router = APIRouter(prefix="/api/v1", tags=["rating"])
admin_read = require_roles("federation_admin")
admin_write = require_roles("federation_admin", csrf=True)
teams_read = require_roles("federation_admin", "ministry")
TWO_PLACES = Decimal("0.01")


# =============================== расчёт ===============================

@dataclass
class Entry:
    athlete_id: int
    competition_id: int
    title: str
    date: date
    level: CompetitionLevel
    type_id: int
    type_name: str
    place: int


@dataclass
class Rule:
    title: str
    level: CompetitionLevel
    type_id: int | None
    first: int
    second: int
    third: int

    def points(self, place: int) -> int:
        return {1: self.first, 2: self.second, 3: self.third}.get(place, 0)


@dataclass
class Scored:
    entry: Entry
    points: int
    rule: str | None


@dataclass
class AthleteScore:
    athlete_id: int
    items: list[Scored] = field(default_factory=list)
    base: int = 0
    podiums: int = 0
    coefficient: Decimal = Decimal("1")
    total: Decimal = Decimal("0")
    place: int = 0


def match_rule(entry: Entry, rules: list[Rule]) -> Rule | None:
    """Правило для конкретного типа соревнования точнее правила «любой тип» того же уровня."""
    exact = next((rule for rule in rules if rule.level == entry.level and rule.type_id == entry.type_id), None)
    return exact or next((rule for rule in rules if rule.level == entry.level and rule.type_id is None), None)


def compute_rating(entries: list[Entry], rules: list[Rule], coefficient: Decimal, min_podiums: int) -> list[AthleteScore]:
    """Сумма баллов за все соревнования сезона; ×коэффициент стабильности при призовых местах на min_podiums соревнованиях."""
    scores: dict[int, AthleteScore] = {}
    for entry in sorted(entries, key=lambda item: (item.date, item.competition_id)):
        score = scores.setdefault(entry.athlete_id, AthleteScore(entry.athlete_id))
        rule = match_rule(entry, rules)
        points = rule.points(entry.place) if rule else 0
        score.items.append(Scored(entry, points, rule.title if rule else None))
        score.base += points
        score.podiums += entry.place <= 3
    ranked = list(scores.values())
    for score in ranked:
        score.coefficient = (coefficient if score.podiums >= min_podiums else Decimal("1")).quantize(TWO_PLACES)
        score.total = (Decimal(score.base) * score.coefficient).quantize(TWO_PLACES, ROUND_HALF_UP)
    ranked.sort(key=lambda item: (-item.total, -item.podiums, item.athlete_id))
    previous: Decimal | None = None
    for index, score in enumerate(ranked, start=1):
        score.place = ranked[index - 2].place if previous == score.total else index
        previous = score.total
    return ranked


def active_sanction(sanctions: list[Sanction], today: date) -> Sanction | None:
    return next((item for item in sanctions if item.starts_on <= today and (item.ends_on is None or item.ends_on >= today)), None)


# =============================== API ===============================

class ScoredRead(BaseModel):
    competition_id: int
    title: str
    date: date
    level: CompetitionLevel
    competition_type: str
    place: int
    points: int
    rule: str | None


class RatingRow(BaseModel):
    place: int
    athlete: AthleteBrief
    rank: SportRank | None
    base_points: int
    podiums: int
    coefficient: Decimal
    total: Decimal
    items: list[ScoredRead]


class Excluded(BaseModel):
    athlete: AthleteBrief
    reason: str


class RuleRead(BaseModel):
    title: str
    level: CompetitionLevel
    competition_type_id: int | None
    first: int = Field(ge=0, le=1000)
    second: int = Field(ge=0, le=1000)
    third: int = Field(ge=0, le=1000)


class RatingSettingsRead(BaseModel):
    stability_coefficient: Decimal = Field(ge=1, le=3)
    stability_min_podiums: int = Field(ge=1, le=20)
    points: list[RuleRead] = Field(max_length=50)

    @model_validator(mode="after")
    def unique_rules(self) -> "RatingSettingsRead":
        keys = [(rule.level, rule.competition_type_id) for rule in self.points]
        if len(keys) != len(set(keys)):
            raise ValueError("Для одного уровня и типа соревнования может быть только одно правило")
        return self


class RatingRead(BaseModel):
    season: int
    discipline: DisciplineRead
    age_group: AgeGroupRead | None
    min_rank: SportRank | None
    settings: RatingSettingsRead
    rows: list[RatingRow]
    excluded: list[Excluded]


async def load_settings(db: AsyncSession) -> RatingSettingsRead:
    settings = await db.scalar(select(RatingSettings).limit(1))
    rules = list(await db.scalars(select(RatingPoints).order_by(RatingPoints.level, RatingPoints.id)))
    return RatingSettingsRead(
        stability_coefficient=settings.stability_coefficient if settings else Decimal("1.2"),
        stability_min_podiums=settings.stability_min_podiums if settings else 2,
        points=[RuleRead(title=rule.title, level=rule.level, competition_type_id=rule.competition_type_id, first=rule.first, second=rule.second, third=rule.third) for rule in rules],
    )


async def build_rating(db: AsyncSession, discipline_id: int, season: int, age_group_id: int | None = None, min_rank: SportRank | None = None, today: date | None = None) -> RatingRead:
    today = today or date.today()
    discipline = await db.get(Discipline, discipline_id)
    if discipline is None:
        raise HTTPException(status_code=422, detail="Неизвестная дисциплина")
    age_group = await db.get(AgeGroup, age_group_id) if age_group_id else None
    if age_group_id and age_group is None:
        raise HTTPException(status_code=422, detail="Неизвестная возрастная группа")
    settings = await load_settings(db)

    applications = list(await db.scalars(
        select(Application)
        .join(Competition, Competition.id == Application.competition_id)
        .join(Result, Result.application_id == Application.id)
        .where(
            Competition.discipline_id == discipline_id, Competition.protocol_published_at.is_not(None), Competition.is_archived.is_(False),
            Competition.date.between(date(season, 1, 1), date(season, 12, 31)),
            Application.status == ApplicationStatus.APPROVED, Result.result_status == ResultStatus.OK, Result.place.is_not(None),
        )
    ))
    entries = [
        Entry(item.athlete_id, item.competition_id, item.competition.title, item.competition.date, item.competition.level,
              item.competition.competition_type_id, item.competition.competition_type.name, item.result.place)
        for item in applications
    ]
    athlete_ids = {entry.athlete_id for entry in entries}
    briefs = await athlete_briefs(db, athlete_ids)
    ranks = await _latest_ranks(db, athlete_ids)
    sanctions: dict[int, list[Sanction]] = defaultdict(list)
    if athlete_ids:
        for item in await db.scalars(select(Sanction).where(Sanction.athlete_id.in_(athlete_ids))):
            sanctions[item.athlete_id].append(item)

    excluded: list[Excluded] = []
    allowed: set[int] = set()
    for athlete_id in athlete_ids:
        sanction = active_sanction(sanctions[athlete_id], today)
        if sanction is not None:
            label = "Дисквалификация" if sanction.kind == SanctionKind.DISQUALIFICATION else "Отстранение"
            until = f" до {sanction.ends_on:%d.%m.%Y}" if sanction.ends_on else ""
            excluded.append(Excluded(athlete=briefs[athlete_id], reason=f"{label}{until}: {sanction.reason}"))
            continue
        birth = briefs[athlete_id].birth_date
        if age_group is not None and (birth is None or not fitting_groups(season - birth.year, [age_group])):
            continue
        rank = ranks.get(athlete_id)
        valid_rank = rank.rank if rank and rank.expires_on >= today else None
        if min_rank is not None and (valid_rank is None or RANK_ORDER.index(valid_rank) < RANK_ORDER.index(min_rank)):
            continue
        allowed.add(athlete_id)

    rules = [Rule(rule.title, rule.level, rule.competition_type_id, rule.first, rule.second, rule.third) for rule in settings.points]
    scores = compute_rating([entry for entry in entries if entry.athlete_id in allowed], rules, settings.stability_coefficient, settings.stability_min_podiums)
    rows = [
        RatingRow(
            place=score.place, athlete=briefs[score.athlete_id],
            rank=ranks[score.athlete_id].rank if score.athlete_id in ranks and ranks[score.athlete_id].expires_on >= today else None,
            base_points=score.base, podiums=score.podiums, coefficient=score.coefficient, total=score.total,
            items=[ScoredRead(competition_id=item.entry.competition_id, title=item.entry.title, date=item.entry.date, level=item.entry.level,
                              competition_type=item.entry.type_name, place=item.entry.place, points=item.points, rule=item.rule) for item in score.items],
        )
        for score in scores
    ]
    return RatingRead(
        season=season, discipline=DisciplineRead.model_validate(discipline), age_group=AgeGroupRead.model_validate(age_group) if age_group else None,
        min_rank=min_rank, settings=settings, rows=rows, excluded=sorted(excluded, key=lambda item: item.athlete.full_name),
    )


@router.get("/rating", response_model=RatingRead)
async def rating(
    discipline_id: Annotated[int, Query(gt=0)],
    season: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    age_group_id: Annotated[int | None, Query(gt=0)] = None,
    min_rank: SportRank | None = None,
    _admin: User = Depends(admin_read),
    db: AsyncSession = Depends(get_session),
) -> RatingRead:
    return await build_rating(db, discipline_id, season or date.today().year, age_group_id, min_rank)


@router.get("/rating/settings", response_model=RatingSettingsRead)
async def get_rating_settings(_admin: User = Depends(admin_read), db: AsyncSession = Depends(get_session)) -> RatingSettingsRead:
    return await load_settings(db)


@router.put("/rating/settings", response_model=RatingSettingsRead)
async def update_rating_settings(payload: RatingSettingsRead, _admin: User = Depends(admin_write), db: AsyncSession = Depends(get_session)) -> RatingSettingsRead:
    type_ids = {rule.competition_type_id for rule in payload.points if rule.competition_type_id is not None}
    if type_ids and len(list(await db.scalars(select(CompetitionType.id).where(CompetitionType.id.in_(type_ids))))) != len(type_ids):
        raise HTTPException(status_code=422, detail="Неизвестный тип соревнования")
    settings = await db.scalar(select(RatingSettings).limit(1))
    if settings is None:
        settings = RatingSettings()
        db.add(settings)
    settings.stability_coefficient, settings.stability_min_podiums = payload.stability_coefficient, payload.stability_min_podiums
    for rule in await db.scalars(select(RatingPoints)):
        await db.delete(rule)
    await db.flush()
    db.add_all(RatingPoints(**rule.model_dump()) for rule in payload.points)
    await db.commit()
    return await load_settings(db)


# ---------- дисквалификации и отстранения ----------

class SanctionWrite(BaseModel):
    athlete_id: int = Field(gt=0)
    kind: SanctionKind
    starts_on: date
    ends_on: date | None = None
    reason: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def dates(self) -> "SanctionWrite":
        if self.ends_on is not None and self.ends_on < self.starts_on:
            raise ValueError("Окончание раньше начала")
        return self


class SanctionRead(BaseModel):
    id: int
    athlete: AthleteBrief
    kind: SanctionKind
    starts_on: date
    ends_on: date | None
    reason: str
    active: bool


async def _sanctions(db: AsyncSession, items: list[Sanction]) -> list[SanctionRead]:
    briefs = await athlete_briefs(db, {item.athlete_id for item in items})
    today = date.today()
    return [
        SanctionRead(id=item.id, athlete=briefs[item.athlete_id], kind=item.kind, starts_on=item.starts_on, ends_on=item.ends_on,
                     reason=item.reason, active=active_sanction([item], today) is not None)
        for item in items
    ]


@router.get("/sanctions", response_model=list[SanctionRead])
async def list_sanctions(_admin: User = Depends(admin_read), db: AsyncSession = Depends(get_session)) -> list[SanctionRead]:
    return await _sanctions(db, list(await db.scalars(select(Sanction).order_by(Sanction.starts_on.desc()))))


@router.post("/sanctions", response_model=SanctionRead, status_code=201)
async def create_sanction(payload: SanctionWrite, _admin: User = Depends(admin_write), db: AsyncSession = Depends(get_session)) -> SanctionRead:
    if await db.get(AthleteProfile, payload.athlete_id) is None:
        raise HTTPException(status_code=404, detail="Спортсмен не найден в реестре")
    item = Sanction(**payload.model_dump() | {"reason": payload.reason.strip()}, created_at=utcnow())
    db.add(item)
    await db.commit()
    return (await _sanctions(db, [item]))[0]


@router.delete("/sanctions/{sanction_id}", status_code=204)
async def delete_sanction(sanction_id: Annotated[int, Path(gt=0)], _admin: User = Depends(admin_write), db: AsyncSession = Depends(get_session)) -> None:
    item = await db.get(Sanction, sanction_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    await db.delete(item)
    await db.commit()


# ---------- сборная ----------

class MemberWrite(BaseModel):
    athlete_id: int = Field(gt=0)
    is_reserve: bool = False


class TeamWrite(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    discipline_id: int = Field(gt=0)
    season: int = Field(ge=2000, le=2100)
    age_group_id: int | None = Field(default=None, gt=0)
    members: list[MemberWrite] = Field(min_length=1, max_length=200)


class MemberRead(BaseModel):
    athlete: AthleteBrief
    position: int
    is_reserve: bool
    rating_place: int | None
    rating_points: Decimal | None
    rank: SportRank | None


class TeamRead(BaseModel):
    id: int
    title: str
    discipline: DisciplineRead
    season: int
    age_group: RefItem | None
    created_at: datetime
    members: list[MemberRead]


async def read_team(db: AsyncSession, team: Team) -> TeamRead:
    ids = {member.athlete_id for member in team.members}
    briefs = await athlete_briefs(db, ids)
    ranks = await _latest_ranks(db, ids)
    return TeamRead(
        id=team.id, title=team.title, discipline=DisciplineRead.model_validate(team.discipline), season=team.season,
        age_group=RefItem.model_validate(team.age_group) if team.age_group else None, created_at=team.created_at,
        members=[
            MemberRead(athlete=briefs[member.athlete_id], position=member.position, is_reserve=member.is_reserve, rating_place=member.rating_place,
                       rating_points=member.rating_points, rank=ranks[member.athlete_id].rank if member.athlete_id in ranks else None)
            for member in team.members
        ],
    )


async def get_team(db: AsyncSession, team_id: int) -> Team:
    team = await db.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Состав сборной не найден")
    return team


@router.get("/teams", response_model=list[TeamRead])
async def list_teams(_reader: User = Depends(teams_read), db: AsyncSession = Depends(get_session)) -> list[TeamRead]:
    return [await read_team(db, team) for team in await db.scalars(select(Team).order_by(Team.created_at.desc()))]


@router.post("/teams", response_model=TeamRead, status_code=201)
async def create_team(payload: TeamWrite, _admin: User = Depends(admin_write), db: AsyncSession = Depends(get_session)) -> TeamRead:
    """Федерация вручную выбирает спортсменов; места и баллы рейтинга сохраняются снимком."""
    ids = [member.athlete_id for member in payload.members]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="Спортсмен указан дважды")
    current = await build_rating(db, payload.discipline_id, payload.season, payload.age_group_id)
    by_athlete = {row.athlete.id: row for row in current.rows}
    excluded = {item.athlete.id for item in current.excluded}
    if excluded & set(ids):
        raise HTTPException(status_code=422, detail="В составе есть дисквалифицированный или отстранённый спортсмен")
    missing = set(ids) - by_athlete.keys()
    if missing:
        raise HTTPException(status_code=422, detail="В сборную включаются спортсмены из рейтинга этой дисциплины и сезона")
    team = Team(title=payload.title.strip(), discipline_id=payload.discipline_id, season=payload.season, age_group_id=payload.age_group_id, created_at=utcnow())
    team.members = [
        TeamMember(athlete_id=member.athlete_id, position=index, is_reserve=member.is_reserve,
                   rating_place=by_athlete[member.athlete_id].place, rating_points=by_athlete[member.athlete_id].total)
        for index, member in enumerate(sorted(payload.members, key=lambda item: (item.is_reserve, by_athlete[item.athlete_id].place)), start=1)
    ]
    db.add(team)
    await db.commit()
    await db.refresh(team, ["discipline", "age_group", "members"])
    return await read_team(db, team)


@router.get("/teams/{team_id}", response_model=TeamRead)
async def team_detail(team_id: Annotated[int, Path(gt=0)], _reader: User = Depends(teams_read), db: AsyncSession = Depends(get_session)) -> TeamRead:
    return await read_team(db, await get_team(db, team_id))


@router.delete("/teams/{team_id}", status_code=204)
async def delete_team(team_id: Annotated[int, Path(gt=0)], _admin: User = Depends(admin_write), db: AsyncSession = Depends(get_session)) -> None:
    await db.delete(await get_team(db, team_id))
    await db.commit()
