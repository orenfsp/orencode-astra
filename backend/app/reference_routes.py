from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_models import User
from app.auth_routes import require_roles
from app.database import get_session
from app.models import AgeGroup, CompetitionType, Discipline, JudgePosition, Municipality, Organization
from app.schemas import (
    AgeGroupRead, AgeGroupWrite, CompetitionTypeRead, CompetitionTypeWrite, OrganizationRead,
    OrganizationWrite, ReferenceBundle,
)


router = APIRouter(prefix="/api/v1/reference", tags=["reference"])
admin_only = require_roles("federation_admin", csrf=True)


@router.get("", response_model=ReferenceBundle)
async def get_reference(session: AsyncSession = Depends(get_session)) -> ReferenceBundle:
    """Все справочники одним запросом: формы и фильтры фронтенда строятся из них."""
    return ReferenceBundle(
        disciplines=list(await session.scalars(select(Discipline).order_by(Discipline.sort_order))),
        competition_types=list(await session.scalars(select(CompetitionType).order_by(CompetitionType.id))),
        age_groups=list(await session.scalars(select(AgeGroup).order_by(AgeGroup.sort_order, AgeGroup.id))),
        municipalities=list(await session.scalars(select(Municipality).order_by(Municipality.name))),
        organizations=list(await session.scalars(select(Organization).order_by(Organization.name))),
        judge_positions=list(await session.scalars(select(JudgePosition).order_by(JudgePosition.id))),
    )


async def _commit_unique(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Запись с таким названием уже есть") from None


async def _get_or_404(session: AsyncSession, model, item_id: int):
    item = await session.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Запись справочника не найдена")
    return item


@router.post("/competition-types", response_model=CompetitionTypeRead, status_code=status.HTTP_201_CREATED)
async def create_competition_type(payload: CompetitionTypeWrite, _admin: User = Depends(admin_only), session: AsyncSession = Depends(get_session)) -> CompetitionType:
    item = CompetitionType(name=payload.name.strip(), is_active=payload.is_active)
    session.add(item)
    await _commit_unique(session)
    return item


@router.put("/competition-types/{item_id}", response_model=CompetitionTypeRead)
async def update_competition_type(item_id: Annotated[int, Path(gt=0)], payload: CompetitionTypeWrite, _admin: User = Depends(admin_only), session: AsyncSession = Depends(get_session)) -> CompetitionType:
    item = await _get_or_404(session, CompetitionType, item_id)
    item.name, item.is_active = payload.name.strip(), payload.is_active
    await _commit_unique(session)
    return item


@router.post("/age-groups", response_model=AgeGroupRead, status_code=status.HTTP_201_CREATED)
async def create_age_group(payload: AgeGroupWrite, _admin: User = Depends(admin_only), session: AsyncSession = Depends(get_session)) -> AgeGroup:
    item = AgeGroup(name=payload.name.strip(), min_age=payload.min_age, max_age=payload.max_age, sort_order=payload.min_age)
    session.add(item)
    await _commit_unique(session)
    return item


@router.put("/age-groups/{item_id}", response_model=AgeGroupRead)
async def update_age_group(item_id: Annotated[int, Path(gt=0)], payload: AgeGroupWrite, _admin: User = Depends(admin_only), session: AsyncSession = Depends(get_session)) -> AgeGroup:
    item = await _get_or_404(session, AgeGroup, item_id)
    item.name, item.min_age, item.max_age = payload.name.strip(), payload.min_age, payload.max_age
    await _commit_unique(session)
    return item


async def _check_municipality(session: AsyncSession, municipality_id: int | None) -> None:
    if municipality_id is not None and await session.get(Municipality, municipality_id) is None:
        raise HTTPException(status_code=422, detail="Неизвестный муниципалитет")


@router.post("/organizations", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(payload: OrganizationWrite, _admin: User = Depends(admin_only), session: AsyncSession = Depends(get_session)) -> Organization:
    await _check_municipality(session, payload.municipality_id)
    item = Organization(**payload.model_dump() | {"name": payload.name.strip()})
    session.add(item)
    await _commit_unique(session)
    await session.refresh(item)
    return item


@router.put("/organizations/{item_id}", response_model=OrganizationRead)
async def update_organization(item_id: Annotated[int, Path(gt=0)], payload: OrganizationWrite, _admin: User = Depends(admin_only), session: AsyncSession = Depends(get_session)) -> Organization:
    item = await _get_or_404(session, Organization, item_id)
    await _check_municipality(session, payload.municipality_id)
    for field, value in (payload.model_dump() | {"name": payload.name.strip()}).items():
        setattr(item, field, value)
    await _commit_unique(session)
    await session.refresh(item)
    return item
