from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_models import User
from app.auth_routes import require_roles
from app.database import get_session
from app.models import Competition, CompetitionStatus
from app.schemas import (
    CompetitionCreate,
    CompetitionFields,
    CompetitionRead,
    CompetitionStatusUpdate,
    CompetitionUpdate,
)


router = APIRouter(prefix="/api/v1/competitions", tags=["competitions"])


async def get_existing_competition(
    competition_id: int,
    session: AsyncSession,
    *,
    include_archived: bool = False,
) -> Competition:
    competition = await session.get(Competition, competition_id)
    if competition is None or (competition.is_archived and not include_archived):
        raise HTTPException(status_code=404, detail="Competition not found")
    return competition


@router.get("", response_model=list[CompetitionRead])
async def get_competitions(
    status_filter: Annotated[CompetitionStatus | None, Query(alias="status")] = None,
    discipline: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    include_archived: bool = False,
    session: AsyncSession = Depends(get_session),
) -> list[Competition]:
    statement = select(Competition)
    if not include_archived:
        statement = statement.where(Competition.is_archived.is_(False))
    if status_filter is not None:
        statement = statement.where(Competition.status == status_filter)
    if discipline is not None:
        statement = statement.where(Competition.discipline == discipline)
    if q is not None:
        statement = statement.where(Competition.title.ilike(f"%{q}%"))

    result = await session.scalars(statement.order_by(Competition.id))
    return list(result.all())


@router.post("", response_model=CompetitionRead, status_code=status.HTTP_201_CREATED)
async def create_competition(
    payload: CompetitionCreate,
    _admin: User = Depends(require_roles("federation_admin", csrf=True)),
    session: AsyncSession = Depends(get_session),
) -> Competition:
    competition = Competition(**payload.model_dump(), is_archived=False)
    session.add(competition)
    await session.commit()
    await session.refresh(competition)
    return competition


@router.get("/{competition_id}", response_model=CompetitionRead)
async def get_competition(
    competition_id: Annotated[int, Path(gt=0)],
    include_archived: bool = False,
    session: AsyncSession = Depends(get_session),
) -> Competition:
    return await get_existing_competition(
        competition_id,
        session,
        include_archived=include_archived,
    )


@router.patch("/{competition_id}", response_model=CompetitionRead)
async def update_competition(
    competition_id: Annotated[int, Path(gt=0)],
    payload: CompetitionUpdate,
    _admin: User = Depends(require_roles("federation_admin", csrf=True)),
    session: AsyncSession = Depends(get_session),
) -> Competition:
    competition = await get_existing_competition(
        competition_id,
        session,
        include_archived=True,
    )
    if competition.is_archived:
        raise HTTPException(status_code=409, detail="Archived competition is read-only")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one field is required")

    try:
        candidate = CompetitionFields.model_validate(
            {
                "title": competition.title,
                "discipline": competition.discipline,
                "date": competition.date,
                "location": competition.location,
                "description": competition.description,
                "event_format": competition.event_format,
                "registration_start": competition.registration_start,
                "registration_end": competition.registration_end,
                "status": competition.status,
                **changes,
            }
        )
    except ValidationError as error:
        raise HTTPException(
            status_code=422,
            detail=error.errors(include_context=False),
        ) from error
    for field, value in candidate.model_dump().items():
        if field in changes:
            setattr(competition, field, value)

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
    competition = await get_existing_competition(
        competition_id,
        session,
        include_archived=True,
    )
    if competition.is_archived:
        raise HTTPException(status_code=409, detail="Archived competition is read-only")

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
    competition = await get_existing_competition(
        competition_id,
        session,
        include_archived=True,
    )
    if competition.is_archived:
        raise HTTPException(status_code=409, detail="Archived competition is read-only")
    if competition.status != CompetitionStatus.REGISTRATION_OPEN:
        raise HTTPException(status_code=409, detail="Registration is not open")

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
    competition = await get_existing_competition(
        competition_id,
        session,
        include_archived=True,
    )
    competition.is_archived = True
    await session.commit()
    await session.refresh(competition)
    return competition
