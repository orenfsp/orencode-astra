"""Реестр занимающихся и отчёт о численности с динамикой по годам (JSON и .xlsx)."""

from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application_schemas import AthleteBrief
from app.auth_models import User
from app.auth_routes import require_roles
from app.coaching_models import CoachLink, LinkStatus
from app.database import get_session
from app.models import AgeGroup
from app.people import athlete_briefs, names
from app.profile_models import AthleteProfile, Profile, TrainingStage
from app.protocol import fitting_groups
from app.qualification_models import RANK_ORDER, SportRank
from app.qualifications import _latest_ranks, validity
from app.schemas import DisciplineRead


router = APIRouter(prefix="/api/v1", tags=["reports"])
admin_read = require_roles("federation_admin")

STAGE_LABELS = {
    TrainingStage.INITIAL: "Начальная подготовка", TrainingStage.TRAINING: "Учебно-тренировочный этап",
    TrainingStage.IMPROVEMENT: "Совершенствование спортивного мастерства", TrainingStage.HIGHEST: "Высшее спортивное мастерство",
}
OUTSIDE_GROUPS = "Вне возрастных групп"
NO_VALUE = "Не указано"


# =============================== реестр ===============================

class RegistryRow(AthleteBrief):
    disciplines: list[DisciplineRead]
    start_year: int | None
    end_year: int | None
    training_stage: TrainingStage | None
    rank: SportRank | None
    rank_validity: str
    coaches: list[str]
    age: int | None


@router.get("/registry/athletes", response_model=list[RegistryRow])
async def registry_athletes(
    q: Annotated[str | None, Query(max_length=120)] = None,
    discipline_id: Annotated[int | None, Query(gt=0)] = None,
    organization_id: Annotated[int | None, Query(ge=0)] = None,
    municipality_id: Annotated[int | None, Query(gt=0)] = None,
    age_group_id: Annotated[int | None, Query(gt=0)] = None,
    min_rank: SportRank | None = None,
    _admin: User = Depends(admin_read),
    db: AsyncSession = Depends(get_session),
) -> list[RegistryRow]:
    """Реестр спортсменов с фильтрами; organization_id=0 — «без организации»."""
    today = date.today()
    athletes = list(await db.scalars(select(AthleteProfile)))
    profiles = {item.user_id: item for item in await db.scalars(select(Profile).where(Profile.user_id.in_({item.user_id for item in athletes})))} if athletes else {}
    briefs = await athlete_briefs(db, {item.user_id for item in athletes})
    ranks = await _latest_ranks(db, {item.user_id for item in athletes})
    age_group = await db.get(AgeGroup, age_group_id) if age_group_id else None
    links = list(await db.scalars(select(CoachLink).where(CoachLink.status == LinkStatus.ACTIVE)))
    coach_names = await names(db, {link.coach_id for link in links})
    coaches: dict[int, list[str]] = {}
    for link in links:
        coaches.setdefault(link.athlete_id, []).append(f"{coach_names[link.coach_id]} ({link.discipline.name.replace('Программирование ', '')})")

    needle = (q or "").strip().casefold()
    rows = []
    for athlete in athletes:
        brief, profile = briefs[athlete.user_id], profiles.get(athlete.user_id)
        age = today.year - profile.birth_date.year if profile and profile.birth_date else None
        rank = ranks.get(athlete.user_id)
        if needle and needle not in brief.full_name.casefold():
            continue
        if discipline_id and discipline_id not in {item.id for item in athlete.disciplines}:
            continue
        if organization_id is not None and (athlete.organization_id or 0) != organization_id:
            continue
        if municipality_id and (profile is None or profile.municipality_id != municipality_id):
            continue
        if age_group is not None and (age is None or not fitting_groups(age, [age_group])):
            continue
        if min_rank is not None and (rank is None or rank.expires_on < today or RANK_ORDER.index(rank.rank) < RANK_ORDER.index(min_rank)):
            continue
        rows.append(RegistryRow(
            **brief.model_dump(), disciplines=[DisciplineRead.model_validate(item) for item in athlete.disciplines],
            start_year=athlete.start_year, end_year=athlete.end_year, training_stage=athlete.training_stage,
            rank=rank.rank if rank else None, rank_validity=validity(rank.expires_on if rank else None, today),
            coaches=coaches.get(athlete.user_id, []), age=age,
        ))
    return sorted(rows, key=lambda row: row.full_name)


# =============================== численность ===============================

@dataclass
class Person:
    birth_year: int | None
    start_year: int
    end_year: int | None
    organization: str
    municipality: str
    disciplines: list[str]
    stage: str


def active_in(person: Person, year: int) -> bool:
    return person.start_year <= year and (person.end_year is None or person.end_year >= year)


class Line(BaseModel):
    name: str
    counts: list[int]


class Section(BaseModel):
    key: str
    title: str
    rows: list[Line]


class Headcount(BaseModel):
    years: list[int]
    total: list[int]
    sections: list[Section]
    note: str


def build_headcount(people: list[Person], years: list[int], groups: list[AgeGroup]) -> Headcount:
    """Человек считается занимающимся в году, если начал не позже и не прекратил занятия раньше этого года.

    В разрезе дисциплин человек учитывается в каждой своей дисциплине, в разрезе возрастных групп —
    в каждой группе, куда проходит по возрасту; поэтому суммы разрезов могут превышать итог.
    """
    def section(key: str, title: str, keys_of) -> Section:
        counts: dict[str, list[int]] = {}
        for person in people:
            for index, year in enumerate(years):
                if not active_in(person, year):
                    continue
                for name in keys_of(person, year):
                    counts.setdefault(name, [0] * len(years))[index] += 1
        rows = [Line(name=name, counts=values) for name, values in counts.items()]
        rows.sort(key=lambda line: (line.name in {NO_VALUE, OUTSIDE_GROUPS}, -line.counts[-1], line.name))
        return Section(key=key, title=title, rows=rows)

    def age_keys(person: Person, year: int) -> list[str]:
        if person.birth_year is None:
            return [NO_VALUE]
        fitting = fitting_groups(year - person.birth_year, groups)
        return [group.name for group in fitting] or [OUTSIDE_GROUPS]

    return Headcount(
        years=years,
        total=[sum(active_in(person, year) for person in people) for year in years],
        sections=[
            section("organizations", "Организации", lambda person, _year: [person.organization]),
            section("disciplines", "Дисциплины", lambda person, _year: person.disciplines or [NO_VALUE]),
            section("age_groups", "Возрастные группы", age_keys),
            section("municipalities", "Муниципалитеты", lambda person, _year: [person.municipality]),
            section("stages", "Этапы спортивной подготовки", lambda person, _year: [person.stage]),
        ],
        note="Занимающийся учитывается в году, если начал занятия не позже этого года и не прекратил их раньше. "
             "Спортсмен с несколькими дисциплинами или подходящий в несколько возрастных групп учитывается в каждой, "
             "поэтому сумма по разрезу может быть больше итога.",
    )


async def load_people(db: AsyncSession) -> list[Person]:
    athletes = list(await db.scalars(select(AthleteProfile)))
    profiles = {item.user_id: item for item in await db.scalars(select(Profile).where(Profile.user_id.in_({item.user_id for item in athletes})))} if athletes else {}
    users = {item.id: item for item in await db.scalars(select(User).where(User.id.in_({item.user_id for item in athletes})))} if athletes else {}
    people = []
    for athlete in athletes:
        profile = profiles.get(athlete.user_id)
        # Без года начала занятий берём год регистрации на платформе.
        start = athlete.start_year or users[athlete.user_id].created_at.year
        people.append(Person(
            birth_year=profile.birth_date.year if profile and profile.birth_date else None,
            start_year=start, end_year=athlete.end_year,
            organization=athlete.organization.name if athlete.organization else "Без организации",
            municipality=profile.municipality.name if profile and profile.municipality else NO_VALUE,
            disciplines=[item.name for item in athlete.disciplines],
            stage=STAGE_LABELS.get(athlete.training_stage, NO_VALUE) if athlete.training_stage else NO_VALUE,
        ))
    return people


def _years(from_year: int | None, to_year: int | None) -> list[int]:
    to_year = to_year or date.today().year
    from_year = from_year or to_year - 2
    if to_year - from_year < 1:
        raise HTTPException(status_code=422, detail="Динамика строится минимум за 2 года")
    if to_year - from_year > 15:
        raise HTTPException(status_code=422, detail="Период не больше 15 лет")
    return list(range(from_year, to_year + 1))


@router.get("/reports/headcount", response_model=Headcount)
async def headcount(
    from_year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    to_year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    _admin: User = Depends(admin_read),
    db: AsyncSession = Depends(get_session),
) -> Headcount:
    groups = list(await db.scalars(select(AgeGroup).order_by(AgeGroup.sort_order, AgeGroup.id)))
    return build_headcount(await load_people(db), _years(from_year, to_year), groups)


# ---------- .xlsx ----------

HEADER_FILL = PatternFill("solid", fgColor="402FFF")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14)


def _dynamics(counts: list[int]) -> tuple[int, str]:
    previous, last = counts[-2], counts[-1]
    change = last - previous
    percent = f"{change / previous:+.0%}" if previous else ("—" if last == 0 else "новое")
    return change, percent


def _table(sheet, start_row: int, first_header: str, years: list[int], lines: list[tuple[str, list[int]]], bold_first: bool = False) -> int:
    headers = [first_header, *[str(year) for year in years], f"Изменение {years[-1]} к {years[-2]}", "Изменение, %"]
    for column, value in enumerate(headers, start=1):
        cell = sheet.cell(row=start_row, column=column, value=value)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for offset, (name, counts) in enumerate(lines, start=1):
        change, percent = _dynamics(counts)
        for column, value in enumerate([name, *counts, change, percent], start=1):
            cell = sheet.cell(row=start_row + offset, column=column, value=value)
            if bold_first and offset == 1:
                cell.font = Font(bold=True)
    return start_row + len(lines) + 1


def headcount_workbook(report: Headcount, generated: date) -> bytes:
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Сводка"
    summary["A1"] = "Численность занимающихся спортивным программированием в Оренбургской области"
    summary["A1"].font = TITLE_FONT
    summary["A2"] = f"Период: {report.years[0]}–{report.years[-1]} гг. Сформировано {generated:%d.%m.%Y} на платформе ФСП Оренбургской области."
    row = _table(summary, 4, "Показатель", report.years, [("Всего занимающихся", report.total)], bold_first=True) + 1
    for section in report.sections:
        summary.cell(row=row, column=1, value=section.title).font = Font(bold=True, size=12)
        row = _table(summary, row + 1, section.title, report.years, [(line.name, line.counts) for line in section.rows]) + 1
    summary.cell(row=row, column=1, value=report.note).alignment = Alignment(wrap_text=True)
    summary.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(report.years) + 3)
    summary.row_dimensions[row].height = 48

    for section in report.sections:
        sheet = workbook.create_sheet(section.title[:31])
        sheet["A1"] = f"Численность занимающихся: {section.title.lower()}"
        sheet["A1"].font = TITLE_FONT
        _table(sheet, 3, section.title, report.years, [(line.name, line.counts) for line in section.rows] + [("Всего занимающихся", report.total)])
    for sheet in workbook.worksheets:
        sheet.column_dimensions["A"].width = 52
        for column in range(2, len(report.years) + 4):
            sheet.column_dimensions[get_column_letter(column)].width = 14
        sheet.freeze_panes = "B4" if sheet.title != "Сводка" else None
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def attachment(content: bytes, media_type: str, filename: str) -> Response:
    """Ответ-файл с русским именем (RFC 5987) и ASCII-запасным вариантом."""
    ascii_name = filename.encode("ascii", "ignore").decode().strip(" -") or "document"
    disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": disposition})


@router.get("/reports/headcount.xlsx")
async def headcount_xlsx(
    from_year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    to_year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    _admin: User = Depends(admin_read),
    db: AsyncSession = Depends(get_session),
) -> Response:
    groups = list(await db.scalars(select(AgeGroup).order_by(AgeGroup.sort_order, AgeGroup.id)))
    years = _years(from_year, to_year)
    report = build_headcount(await load_people(db), years, groups)
    return attachment(headcount_workbook(report, date.today()), XLSX, f"Численность занимающихся {years[0]}-{years[-1]}.xlsx")
