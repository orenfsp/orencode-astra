from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_models import AuthSession, User
from app.auth_routes import csrf_protected_session, current_auth_session, require_roles
from app.auth_security import utcnow
from app.database import get_session
from app.models import Discipline, Municipality, Organization
from app.profile_models import AthleteProfile, CoachProfile, Profile
from app.profile_schemas import AthleteWrite, CoachWrite, MyProfileRead, ProfileWrite


router = APIRouter(prefix="/api/v1/me", tags=["profile"])


def age_on(birth_date: date | None, today: date | None = None) -> int | None:
    if birth_date is None:
        return None
    today = today or date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


async def _my_profile(db: AsyncSession, user: User) -> MyProfileRead:
    profile = await db.get(Profile, user.id)
    age = age_on(profile.birth_date if profile else None)
    return MyProfileRead(
        profile=profile,
        athlete=await db.get(AthleteProfile, user.id),
        coach=await db.get(CoachProfile, user.id),
        age=age,
        is_minor=age is not None and age < 18,
        pd_consent_at=user.pd_consent_at,
    )


async def _check_organization(db: AsyncSession, organization_id: int | None) -> None:
    if organization_id is not None and await db.get(Organization, organization_id) is None:
        raise HTTPException(status_code=422, detail="Неизвестная организация")


@router.get("/profile", response_model=MyProfileRead)
async def get_my_profile(auth_session: AuthSession = Depends(current_auth_session), db: AsyncSession = Depends(get_session)) -> MyProfileRead:
    return await _my_profile(db, auth_session.user)


@router.put("/profile", response_model=MyProfileRead)
async def update_my_profile(payload: ProfileWrite, auth_session: AuthSession = Depends(csrf_protected_session), db: AsyncSession = Depends(get_session)) -> MyProfileRead:
    user = auth_session.user
    if payload.municipality_id is not None and await db.get(Municipality, payload.municipality_id) is None:
        raise HTTPException(status_code=422, detail="Неизвестный муниципалитет")
    profile = await db.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id, updated_at=utcnow())
        db.add(profile)
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    profile.updated_at = utcnow()
    await db.commit()
    await db.refresh(profile)
    return await _my_profile(db, user)


@router.put("/athlete", response_model=MyProfileRead)
async def update_my_athlete_profile(payload: AthleteWrite, user: User = Depends(require_roles("athlete", csrf=True)), db: AsyncSession = Depends(get_session)) -> MyProfileRead:
    profile = await db.get(Profile, user.id)
    if profile is None or profile.birth_date is None:
        raise HTTPException(status_code=422, detail="Сначала укажите дату рождения в общем профиле: по ней определяется возрастная группа")
    await _check_organization(db, payload.organization_id)
    disciplines = list(await db.scalars(select(Discipline).where(Discipline.id.in_(set(payload.discipline_ids)))))
    if len(disciplines) != len(set(payload.discipline_ids)):
        raise HTTPException(status_code=422, detail="Неизвестная дисциплина")

    age = age_on(profile.birth_date)
    athlete = await db.get(AthleteProfile, user.id)
    if athlete is None:
        athlete = AthleteProfile(user_id=user.id, updated_at=utcnow())
        db.add(athlete)
    if age is not None and age < 18:
        # 152-ФЗ: за несовершеннолетнего согласие даёт законный представитель.
        if not payload.guardian_name or not payload.guardian_phone:
            raise HTTPException(status_code=422, detail="Для несовершеннолетнего укажите ФИО и телефон законного представителя")
        if not payload.guardian_consent and athlete.guardian_consent_at is None:
            raise HTTPException(status_code=422, detail="Нужно согласие законного представителя на обработку персональных данных")
        if payload.guardian_consent and athlete.guardian_consent_at is None:
            athlete.guardian_consent_at = utcnow()

    athlete.organization_id = payload.organization_id
    athlete.disciplines = disciplines
    athlete.start_year = payload.start_year
    athlete.training_stage = payload.training_stage
    athlete.guardian_name = payload.guardian_name
    athlete.guardian_phone = payload.guardian_phone
    athlete.rusada_completed_on = payload.rusada_completed_on
    athlete.rusada_certificate_url = str(payload.rusada_certificate_url) if payload.rusada_certificate_url else None
    athlete.updated_at = utcnow()
    await db.commit()
    await db.refresh(athlete, ["organization", "disciplines"])
    return await _my_profile(db, user)


@router.put("/coach", response_model=MyProfileRead)
async def update_my_coach_profile(payload: CoachWrite, user: User = Depends(require_roles("coach", csrf=True)), db: AsyncSession = Depends(get_session)) -> MyProfileRead:
    await _check_organization(db, payload.organization_id)
    coach = await db.get(CoachProfile, user.id)
    if coach is None:
        coach = CoachProfile(user_id=user.id, updated_at=utcnow())
        db.add(coach)
    coach.organization_id = payload.organization_id
    coach.updated_at = utcnow()
    await db.commit()
    await db.refresh(coach, ["organization"])
    return await _my_profile(db, user)
