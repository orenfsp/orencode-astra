"""Журнал действий: автоматическая запись изменений через события сессии SQLAlchemy и API для федерации.

Каждый запрос получает свою сессию; после проверки входа в неё кладётся автор (пользователь и активная роль).
Перед сохранением слушатель собирает новые, изменённые и удалённые записи отслеживаемых сущностей,
а после — дописывает строки журнала с уже известными идентификаторами в ту же транзакцию.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import event, func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import RelationshipProperty, Session

from app.application_models import Application, Result
from app.audit_models import AuditEntry
from app.auth_models import User
from app.auth_routes import require_roles
from app.auth_security import utcnow
from app.coaching_models import CoachLink
from app.database import get_session
from app.models import AgeGroup, Competition, CompetitionType, Organization
from app.people import names
from app.profile_models import AthleteProfile, CoachProfile, Profile
from app.qualification_models import AthleteRank, JudgeAssignment, JudgeCategoryRequest, JudgeProfile, RankNorm, RankRequest
from app.rating_models import RatingPoints, RatingSettings, Sanction, Team


router = APIRouter(prefix="/api/v1", tags=["audit"])

ENTITY_NAMES: dict[type, str] = {
    User: "Аккаунт", Profile: "Профиль", AthleteProfile: "Профиль спортсмена", CoachProfile: "Профиль тренера",
    Competition: "Соревнование", Application: "Заявка на соревнование", Result: "Результат",
    CoachLink: "Связь тренер — спортсмен", JudgeProfile: "Судейская категория", JudgeCategoryRequest: "Заявка на судейскую категорию",
    JudgeAssignment: "Назначение судьи", RankRequest: "Заявка на разряд", AthleteRank: "Спортивный разряд", RankNorm: "Норма ЕВСК",
    RatingPoints: "Баллы рейтинга", RatingSettings: "Настройки рейтинга", Sanction: "Дисквалификация / отстранение", Team: "Сборная",
    Organization: "Организация", CompetitionType: "Тип соревнования", AgeGroup: "Возрастная группа",
}
ACTION_LABELS = {"create": "создание", "update": "изменение", "delete": "удаление"}
# Служебные и секретные поля в журнал не попадают.
SKIP_FIELDS = {"password_hash", "updated_at", "created_at", "regulation_path", "events", "sessions"}
TITLE_FIELDS = ("title", "name", "last_name", "email")


def _plain(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if hasattr(value, "__tablename__"):
        return getattr(value, "name", None) or getattr(value, "title", None) or getattr(value, "id", None)
    return value


def _changes(obj) -> dict:
    """Изменённые поля: [было, стало]; для списков (роли, дисциплины, группы) — полный список до и после."""
    state = inspect(obj)
    changes = {}
    for attr in state.mapper.attrs:
        if attr.key in SKIP_FIELDS:
            continue
        history = state.attrs[attr.key].history
        if not history.has_changes():
            continue
        if isinstance(attr, RelationshipProperty):
            if not attr.uselist:
                continue  # одиночные связи видны по полю-ключу (…_id)
            old = _plain(list(history.unchanged) + list(history.deleted))
            new = _plain(list(history.unchanged) + list(history.added))
        else:
            old = _plain(history.deleted[0] if history.deleted else None)
            new = _plain(history.added[0] if history.added else None)
        if old != new:
            changes[attr.key] = [old, new]
    return changes


def _snapshot(obj) -> dict:
    state = inspect(obj)
    return {column.key: _plain(getattr(obj, column.key)) for column in state.mapper.column_attrs if column.key not in SKIP_FIELDS}


def _label(obj) -> str:
    for field in TITLE_FIELDS:
        value = getattr(obj, field, None)
        if value:
            return str(value)
    return ""


def _identity(obj) -> str:
    key = inspect(obj).identity
    return ":".join(str(part) for part in key) if key else "?"


@event.listens_for(Session, "before_flush")
def _collect(session: Session, _context, _instances) -> None:
    if session.info.get("audit_disabled"):
        return
    pending = session.info.setdefault("audit_pending", [])
    for obj in session.new:
        if type(obj) in ENTITY_NAMES:
            pending.append(("create", obj, None))
    for obj in session.dirty:
        if type(obj) in ENTITY_NAMES and session.is_modified(obj, include_collections=True):
            changes = _changes(obj)
            if changes:
                pending.append(("update", obj, changes))
    for obj in session.deleted:
        if type(obj) in ENTITY_NAMES:
            pending.append(("delete", obj, _snapshot(obj)))


@event.listens_for(Session, "after_flush_postexec")
def _write(session: Session, _context) -> None:
    pending = session.info.pop("audit_pending", [])
    if not pending:
        return
    user_id, role = session.info.get("audit_actor", (None, None))
    now = utcnow()
    for action, obj, changes in pending:
        entity = ENTITY_NAMES[type(obj)]
        author = user_id
        if author is None and action == "create" and isinstance(obj, User):
            author = obj.id  # самостоятельная регистрация: автор — сам новый пользователь
        label = _label(obj)
        if action == "create":
            changes = _snapshot(obj)
        status = changes.get("status") if action == "update" and changes else None
        summary = f"{entity}: {ACTION_LABELS[action]}" + (f" «{label}»" if label else "")
        if status:
            summary += f", статус {status[0]} → {status[1]}"
        session.add(AuditEntry(
            created_at=now, user_id=author, role=role, action="status" if status else action, entity_type=entity,
            entity_id=_identity(obj), summary=summary[:500], changes=changes,
        ))


class AuditRead(BaseModel):
    id: int
    created_at: datetime
    user_id: int | None
    user_name: str
    role: str | None
    action: str
    entity_type: str
    entity_id: str
    summary: str
    changes: dict | None


class AuditPage(BaseModel):
    total: int
    items: list[AuditRead]
    entity_types: list[str]


@router.get("/audit", response_model=AuditPage)
async def audit_log(
    entity_type: str | None = None,
    action: str | None = None,
    user_id: Annotated[int | None, Query(gt=0)] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    _admin: User = Depends(require_roles("federation_admin")),
    db: AsyncSession = Depends(get_session),
) -> AuditPage:
    statement = select(AuditEntry)
    if entity_type:
        statement = statement.where(AuditEntry.entity_type == entity_type)
    if action:
        statement = statement.where(AuditEntry.action == action)
    if user_id:
        statement = statement.where(AuditEntry.user_id == user_id)
    if q:
        statement = statement.where(AuditEntry.summary.ilike(f"%{q.replace('%', '').replace('_', '')}%"))
    total = await db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = list(await db.scalars(statement.order_by(AuditEntry.id.desc()).limit(limit).offset(offset)))
    people = await names(db, {item.user_id for item in items if item.user_id})
    return AuditPage(
        total=total,
        items=[AuditRead(
            id=item.id, created_at=item.created_at, user_id=item.user_id,
            user_name=people.get(item.user_id, "система") if item.user_id else "система",
            role=item.role, action=item.action, entity_type=item.entity_type, entity_id=item.entity_id,
            summary=item.summary, changes=item.changes,
        ) for item in items],
        entity_types=sorted(set(await db.scalars(select(AuditEntry.entity_type).distinct()))),
    )
