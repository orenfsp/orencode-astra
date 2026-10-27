"""Краткие карточки людей для списков, протоколов и реестров."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application_schemas import AthleteBrief
from app.profile_models import AthleteProfile, Profile


def full_name(profile: Profile | None, user_id: int) -> str:
    if profile is None:
        return f"Пользователь #{user_id}"
    return " ".join(part for part in (profile.last_name, profile.first_name, profile.middle_name) if part)


async def names(db: AsyncSession, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    profiles = {item.user_id: item for item in await db.scalars(select(Profile).where(Profile.user_id.in_(user_ids)))}
    return {user_id: full_name(profiles.get(user_id), user_id) for user_id in user_ids}


async def athlete_briefs(db: AsyncSession, user_ids: set[int]) -> dict[int, AthleteBrief]:
    if not user_ids:
        return {}
    profiles = {item.user_id: item for item in await db.scalars(select(Profile).where(Profile.user_id.in_(user_ids)))}
    athletes = {item.user_id: item for item in await db.scalars(select(AthleteProfile).where(AthleteProfile.user_id.in_(user_ids)))}
    briefs = {}
    for user_id in user_ids:
        profile, athlete = profiles.get(user_id), athletes.get(user_id)
        briefs[user_id] = AthleteBrief(
            id=user_id,
            full_name=full_name(profile, user_id),
            birth_date=profile.birth_date if profile else None,
            municipality=profile.municipality.name if profile and profile.municipality else None,
            organization=athlete.organization.name if athlete and athlete.organization else None,
        )
    return briefs
