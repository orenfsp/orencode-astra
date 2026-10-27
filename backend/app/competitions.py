import os
import secrets
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_models import AuthSession, User
from app.auth_routes import is_active_admin, optional_auth_session, require_roles
from app.database import get_session
from app.models import (
    AgeGroup, CalendarPlan, Competition, CompetitionLevel, CompetitionStatus, CompetitionType,
    Discipline, competition_age_groups,
)
from app.schemas import (
    CompetitionCreate,
    CompetitionFields,
    CompetitionRead,
    CompetitionStatusUpdate,
    CompetitionUpdate,
)


router = APIRouter(prefix="/api/v1/competitions", tags=["competitions"])

REGULATION_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
}
REGULATION_MAX_BYTES = 10 * 1024 * 1024


def upload_dir() -> FilePath:
    path = FilePath(os.getenv("UPLOAD_DIR", "uploads")) / "regulations"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def get_existing_competition(
    competition_id: int,
    session: AsyncSession,
    *,
    include_archived: bool = False,
    include_drafts: bool = True,
) -> Competition:
    competition = await session.get(Competition, competition_id)
    if (
        competition is None
        or (competition.is_archived and not include_archived)
        or (competition.status == CompetitionStatus.DRAFT and not include_drafts)
    ):
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    return competition


def ensure_editable(competition: Competition) -> None:
    if competition.is_archived:
        raise HTTPException(status_code=409, detail="Архивное соревнование доступно только для чтения")


async def resolve_references(session: AsyncSession, fields: CompetitionFields) -> list[AgeGroup]:
    """Check foreign keys up front so the API answers 422 instead of a database error."""
    if await session.get(Discipline, fields.discipline_id) is None:
        raise HTTPException(status_code=422, detail="Неизвестная дисциплина")
    competition_type = await session.get(CompetitionType, fields.competition_type_id)
    if competition_type is None:
        raise HTTPException(status_code=422, detail="Неизвестный тип соревнования")
    age_groups = list(await session.scalars(select(AgeGroup).where(AgeGroup.id.in_(fields.age_group_ids))))
    if len(age_groups) != len(fields.age_group_ids):
        raise HTTPException(status_code=422, detail="Неизвестная возрастная группа")
    return age_groups


def validate_fields(data: dict) -> CompetitionFields:
    try:
        return CompetitionFields.model_validate(data)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=jsonable_encoder(error.errors(include_context=False))) from error


@router.get("", response_model=list[CompetitionRead])
async def get_competitions(
    status_filter: Annotated[CompetitionStatus | None, Query(alias="status")] = None,
    discipline_id: Annotated[int | None, Query(gt=0)] = None,
    level: CompetitionLevel | None = None,
    age_group_id: Annotated[int | None, Query(gt=0)] = None,
    calendar_plan: CalendarPlan | None = None,
    q: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    include_archived: bool = False,
    viewer: AuthSession | None = Depends(optional_auth_session),
    session: AsyncSession = Depends(get_session),
) -> list[Competition]:
    """Публичный календарь. Черновики и архив видит только федерация."""
    admin = is_active_admin(viewer)
    statement = select(Competition)
    if not (include_archived and admin):
        statement = statement.where(Competition.is_archived.is_(False))
    if not admin:
        statement = statement.where(Competition.status != CompetitionStatus.DRAFT)
    if status_filter is not None:
        statement = statement.where(Competition.status == status_filter)
    if discipline_id is not None:
        statement = statement.where(Competition.discipline_id == discipline_id)
    if level is not None:
        statement = statement.where(Competition.level == level)
    if calendar_plan is not None:
        statement = statement.where(Competition.calendar_plan == calendar_plan)
    if age_group_id is not None:
        statement = statement.where(
            Competition.id.in_(
                select(competition_age_groups.c.competition_id).where(competition_age_groups.c.age_group_id == age_group_id)
            )
        )
    if q is not None:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(Competition.title.ilike(f"%{escaped}%", escape="\\"))

    result = await session.scalars(statement.order_by(Competition.date, Competition.id))
    return list(result.all())


@router.post("", response_model=CompetitionRead, status_code=status.HTTP_201_CREATED)
async def create_competition(
    payload: CompetitionCreate,
    _admin: User = Depends(require_roles("federation_admin", csrf=True)),
    session: AsyncSession = Depends(get_session),
) -> Competition:
    age_groups = await resolve_references(session, payload)
    competition = Competition(**payload.model_dump(exclude={"age_group_ids"}), age_groups=age_groups, is_archived=False)
    session.add(competition)
    await session.commit()
    await session.refresh(competition)
    return competition


@router.get("/{competition_id}", response_model=CompetitionRead)
async def get_competition(
    competition_id: Annotated[int, Path(gt=0)],
    include_archived: bool = False,
    viewer: AuthSession | None = Depends(optional_auth_session),
    session: AsyncSession = Depends(get_session),
) -> Competition:
    admin = is_active_admin(viewer)
    return await get_existing_competition(competition_id, session, include_archived=include_archived and admin, include_drafts=admin)


@router.patch("/{competition_id}", response_model=CompetitionRead)
async def update_competition(
    competition_id: Annotated[int, Path(gt=0)],
    payload: CompetitionUpdate,
    _admin: User = Depends(require_roles("federation_admin", csrf=True)),
    session: AsyncSession = Depends(get_session),
) -> Competition:
    competition = await get_existing_competition(competition_id, session, include_archived=True)
    ensure_editable(competition)

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Нужно передать хотя бы одно поле")

    current = {
        name: getattr(competition, name)
        for name in CompetitionFields.model_fields
        if name != "age_group_ids"
    }
    current["age_group_ids"] = [group.id for group in competition.age_groups]
    candidate = validate_fields({**current, **changes})
    age_groups = await resolve_references(session, candidate)

    for field, value in candidate.model_dump(exclude={"age_group_ids", "status"}).items():
        setattr(competition, field, value)
    competition.age_groups = age_groups

    await session.commit()
    await session.refresh(competition)
    return competition


@router.patch("/{competition_id}/status", response_model=CompetitionRead)
async def change_competition_status(
    competition_id: Annotated[int, Path(gt=0)],
    payload: CompetitionStatusUpdate,
    _admin: User = Depends(require_roles("federation_admin", csrf=True)),
    session: AsyncSession = Depends(get_session),
) -> Competition:
    competition = await get_existing_competition(competition_id, session, include_archived=True)
    ensure_editable(competition)

    competition.status = payload.status
    await session.commit()
    await session.refresh(competition)
    return competition


@router.post("/{competition_id}/close-registration", response_model=CompetitionRead)
async def close_competition_registration(
    competition_id: Annotated[int, Path(gt=0)],
    _admin: User = Depends(require_roles("federation_admin", csrf=True)),
    session: AsyncSession = Depends(get_session),
) -> Competition:
    competition = await get_existing_competition(competition_id, session, include_archived=True)
    ensure_editable(competition)
    if competition.status != CompetitionStatus.REGISTRATION_OPEN:
        raise HTTPException(status_code=409, detail="Приём заявок не открыт")

    competition.status = CompetitionStatus.REGISTRATION_CLOSED
    await session.commit()
    await session.refresh(competition)
    return competition


@router.post("/{competition_id}/archive", response_model=CompetitionRead)
async def archive_competition(
    competition_id: Annotated[int, Path(gt=0)],
    _admin: User = Depends(require_roles("federation_admin", csrf=True)),
    session: AsyncSession = Depends(get_session),
) -> Competition:
    competition = await get_existing_competition(competition_id, session, include_archived=True)
    competition.is_archived = True
    await session.commit()
    await session.refresh(competition)
    return competition


@router.put("/{competition_id}/regulation", response_model=CompetitionRead)
async def upload_regulation(
    competition_id: Annotated[int, Path(gt=0)],
    file: Annotated[UploadFile, File()],
    _admin: User = Depends(require_roles("federation_admin", csrf=True)),
    session: AsyncSession = Depends(get_session),
) -> Competition:
    """Опубликовать положение (регламент) соревнования: PDF или Word до 10 МБ."""
    competition = await get_existing_competition(competition_id, session, include_archived=True)
    ensure_editable(competition)
    original_name = FilePath(file.filename or "").name
    suffix = FilePath(original_name).suffix.lower()
    if suffix not in REGULATION_TYPES:
        raise HTTPException(status_code=422, detail="Положение должно быть в формате PDF, DOC или DOCX")
    content = await file.read(REGULATION_MAX_BYTES + 1)
    if len(content) > REGULATION_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Файл положения больше 10 МБ")
    if not content:
        raise HTTPException(status_code=422, detail="Файл положения пуст")

    stored_name = f"{competition.id}-{secrets.token_hex(8)}{suffix}"
    (upload_dir() / stored_name).write_bytes(content)
    if competition.regulation_path:
        (upload_dir() / competition.regulation_path).unlink(missing_ok=True)
    competition.regulation_filename = original_name[:255]
    competition.regulation_path = stored_name
    await session.commit()
    await session.refresh(competition)
    return competition


@router.get("/{competition_id}/regulation")
async def download_regulation(
    competition_id: Annotated[int, Path(gt=0)],
    viewer: AuthSession | None = Depends(optional_auth_session),
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    competition = await get_existing_competition(competition_id, session, include_archived=True, include_drafts=is_active_admin(viewer))
    if not competition.regulation_path:
        raise HTTPException(status_code=404, detail="Положение ещё не опубликовано")
    path = upload_dir() / competition.regulation_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл положения не найден")
    suffix = path.suffix.lower()
    return FileResponse(path, media_type=REGULATION_TYPES.get(suffix, "application/octet-stream"), filename=competition.regulation_filename or path.name)
