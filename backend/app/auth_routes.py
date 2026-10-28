import hmac
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_models import AuthSession, Role, User
from app.auth_schemas import LoginRequest, RegisterRequest, RoleAddRequest, RoleSwitchRequest, UserRead
from app.auth_security import (
    ALL_ROLES, CSRF_COOKIE, DUMMY_PASSWORD_HASH, SESSION_COOKIE, SESSION_TTL, cookie_secure,
    hash_password, login_limiter, new_token, normalize_email, token_hash, utcnow,
    valid_admin_registration_code, verify_password,
)
from app.database import get_session
from app.profile_models import Profile


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
INVALID_CREDENTIALS = "Неверный email или пароль"


def _default_active_role(user: User) -> str:
    """Prefer the privileged role only when it is actually assigned."""
    roles = {role.name for role in user.roles}
    for privileged in ("federation_admin", "ministry"):
        if privileged in roles:
            return privileged
    return sorted(roles)[0]


def set_audit_actor(db: AsyncSession, user_id: int | None, role: str | None) -> None:
    """Автор изменений этого запроса для журнала действий (см. app.audit)."""
    db.sync_session.info["audit_actor"] = (user_id, role)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


async def _user_read(db: AsyncSession, auth_session: AuthSession) -> UserRead:
    roles = sorted(role.name for role in auth_session.user.roles)
    profile = await db.get(Profile, auth_session.user.id)
    full_name = " ".join(part for part in (profile.last_name, profile.first_name, profile.middle_name) if part) if profile else None
    return UserRead(id=auth_session.user.id, email=auth_session.user.email, roles=roles, active_role=auth_session.active_role, full_name=full_name)


def _set_auth_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    secure = cookie_secure()
    max_age = int(SESSION_TTL.total_seconds())
    response.set_cookie(SESSION_COOKIE, session_token, max_age=max_age, httponly=True, secure=secure, samesite="lax", path="/")
    response.set_cookie(CSRF_COOKIE, csrf_token, max_age=max_age, httponly=False, secure=secure, samesite="lax", path="/")


def _clear_auth_cookies(response: Response) -> None:
    secure = cookie_secure()
    response.delete_cookie(SESSION_COOKIE, httponly=True, secure=secure, samesite="lax", path="/")
    response.delete_cookie(CSRF_COOKIE, httponly=False, secure=secure, samesite="lax", path="/")


async def current_auth_session(
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    db: AsyncSession = Depends(get_session),
) -> AuthSession:
    if not session_token:
        raise HTTPException(status_code=401, detail="Требуется вход")
    result = await db.scalars(select(AuthSession).where(AuthSession.token_hash == token_hash(session_token)))
    auth_session = result.one_or_none()
    if auth_session is not None and _aware(auth_session.expires_at) <= utcnow():
        # Expired rows are removed lazily here; the rest are pruned on every login.
        await db.delete(auth_session)
        await db.commit()
        auth_session = None
    if auth_session is None or auth_session.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Сессия недействительна")
    set_audit_actor(db, auth_session.user_id, auth_session.active_role)
    return auth_session


async def optional_auth_session(
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    db: AsyncSession = Depends(get_session),
) -> AuthSession | None:
    """Public endpoints use this to widen what a signed-in user may see; never raises."""
    if not session_token:
        return None
    try:
        return await current_auth_session(session_token, db)
    except HTTPException:
        return None


def is_active_admin(auth_session: AuthSession | None) -> bool:
    if auth_session is None or auth_session.active_role != "federation_admin":
        return False
    return "federation_admin" in {role.name for role in auth_session.user.roles}


async def csrf_protected_session(
    auth_session: AuthSession = Depends(current_auth_session),
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE)] = None,
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> AuthSession:
    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header) or not hmac.compare_digest(token_hash(csrf_header), auth_session.csrf_hash):
        raise HTTPException(status_code=403, detail="CSRF-проверка не пройдена")
    return auth_session


def require_roles(*allowed: str, csrf: bool = False):
    unknown = set(allowed) - ALL_ROLES
    if unknown:
        raise ValueError(f"Unknown roles: {sorted(unknown)}")

    session_dependency = csrf_protected_session if csrf else current_auth_session

    async def dependency(auth_session: AuthSession = Depends(session_dependency)) -> User:
        assigned = {role.name for role in auth_session.user.roles}
        if auth_session.active_role not in allowed or auth_session.active_role not in assigned:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        return auth_session.user
    return dependency


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, response: Response, db: AsyncSession = Depends(get_session)) -> UserRead:
    email = normalize_email(payload.email)
    if payload.role == "federation_admin" and not valid_admin_registration_code(payload.admin_registration_code):
        raise HTTPException(status_code=403, detail="Код администратора недействителен")
    role = await db.scalar(select(Role).where(Role.name == payload.role))
    if role is None:
        role = Role(name=payload.role)
        db.add(role)
        await db.flush()
    now = utcnow()
    user = User(email=email, password_hash=hash_password(payload.password), created_at=now, pd_consent_at=now, roles=[role])
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Не удалось зарегистрировать аккаунт") from None
    set_audit_actor(db, user.id, payload.role)
    db.add(Profile(user_id=user.id, last_name=payload.last_name, first_name=payload.first_name, middle_name=payload.middle_name, updated_at=now))
    session_token, csrf_token = new_token(), new_token()
    auth_session = AuthSession(user=user, token_hash=token_hash(session_token), csrf_hash=token_hash(csrf_token), active_role=payload.role, created_at=utcnow(), expires_at=utcnow() + SESSION_TTL)
    db.add(auth_session)
    await db.commit()
    _set_auth_cookies(response, session_token, csrf_token)
    return await _user_read(db, auth_session)


@router.post("/login", response_model=UserRead)
async def login(payload: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_session)) -> UserRead:
    email = normalize_email(payload.email)
    key = f"{request.client.host if request.client else 'unknown'}:{email}"
    if not login_limiter.allow(key):
        raise HTTPException(status_code=429, detail="Слишком много попыток. Повторите позже")
    user = await db.scalar(select(User).where(User.email == email))
    password_ok = verify_password(user.password_hash if user else DUMMY_PASSWORD_HASH, payload.password)
    if user is None or not password_ok:
        raise HTTPException(status_code=401, detail=INVALID_CREDENTIALS)
    await db.execute(delete(AuthSession).where(AuthSession.expires_at <= utcnow()))
    active_role = _default_active_role(user)
    session_token, csrf_token = new_token(), new_token()
    auth_session = AuthSession(user=user, token_hash=token_hash(session_token), csrf_hash=token_hash(csrf_token), active_role=active_role, created_at=utcnow(), expires_at=utcnow() + SESSION_TTL)
    db.add(auth_session)
    await db.commit()
    _set_auth_cookies(response, session_token, csrf_token)
    return await _user_read(db, auth_session)


@router.get("/me", response_model=UserRead)
async def me(auth_session: AuthSession = Depends(current_auth_session), db: AsyncSession = Depends(get_session)) -> UserRead:
    return await _user_read(db, auth_session)


@router.post("/logout", status_code=204)
async def logout(response: Response, auth_session: AuthSession = Depends(csrf_protected_session), db: AsyncSession = Depends(get_session)) -> None:
    auth_session.revoked_at = utcnow()
    await db.commit()
    _clear_auth_cookies(response)


@router.post("/role", response_model=UserRead)
async def switch_role(payload: RoleSwitchRequest, auth_session: AuthSession = Depends(csrf_protected_session), db: AsyncSession = Depends(get_session)) -> UserRead:
    assigned = {role.name for role in auth_session.user.roles}
    if payload.role not in assigned:
        raise HTTPException(status_code=403, detail="Роль не назначена пользователю")
    auth_session.active_role = payload.role
    await db.commit()
    return await _user_read(db, auth_session)


@router.post("/roles", response_model=UserRead)
async def add_role(payload: RoleAddRequest, auth_session: AuthSession = Depends(csrf_protected_session), db: AsyncSession = Depends(get_session)) -> UserRead:
    """Добавить себе публичную роль (спортсмен, тренер, судья) и сразу сделать её активной."""
    user = auth_session.user
    if payload.role not in {role.name for role in user.roles}:
        role = await db.scalar(select(Role).where(Role.name == payload.role))
        if role is None:
            role = Role(name=payload.role)
            db.add(role)
        user.roles.append(role)
    auth_session.active_role = payload.role
    await db.commit()
    await db.refresh(user)
    return await _user_read(db, auth_session)
