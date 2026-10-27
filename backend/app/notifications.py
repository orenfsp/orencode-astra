"""Уведомления: в кабинете и дублирование на email (SMTP)."""

import asyncio
import logging
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth_models import AuthSession, Role, User, user_roles
from app.auth_routes import csrf_protected_session, current_auth_session
from app.auth_security import utcnow
from app.database import get_session
from app.notification_models import Notification


log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/me", tags=["notifications"])


async def notify(db: AsyncSession, user_ids, kind: str, title: str, body: str, link: str | None = None, dedupe_key: str | None = None) -> int:
    """Queue notifications in the current transaction; with dedupe_key a user gets it only once."""
    user_ids = set(user_ids)
    if not user_ids:
        return 0
    if dedupe_key:
        seen = set(await db.scalars(select(Notification.user_id).where(Notification.dedupe_key == dedupe_key, Notification.user_id.in_(user_ids))))
        user_ids -= seen
    now = utcnow()
    db.add_all(Notification(user_id=user_id, kind=kind, title=title, body=body, link=link, dedupe_key=dedupe_key, created_at=now) for user_id in user_ids)
    return len(user_ids)


async def admin_ids(db: AsyncSession) -> set[int]:
    return set(await db.scalars(
        select(user_roles.c.user_id).join(Role, Role.id == user_roles.c.role_id).where(Role.name == "federation_admin")
    ))


# ---------- email ----------

def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST"))


def _send(messages: list[EmailMessage]) -> None:
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "25")), timeout=10) as smtp:
        if os.getenv("SMTP_USER"):
            smtp.starttls()
            smtp.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
        for message in messages:
            smtp.send_message(message)


async def send_pending_emails(session_factory) -> int:
    """Отправить на email уведомления, которые ещё не уходили (для пользователей с включённой настройкой)."""
    if not smtp_configured():
        return 0
    app_url = os.getenv("APP_URL", "http://localhost:5173").rstrip("/")
    sender = os.getenv("SMTP_FROM", "ФСП Оренбург <noreply@fsp-orenburg.local>")
    async with session_factory() as db:
        rows = list(await db.execute(
            select(Notification, User.email, User.email_notifications)
            .join(User, User.id == Notification.user_id)
            .where(Notification.emailed_at.is_(None))
            .order_by(Notification.id)
            .limit(100)
        ))
        if not rows:
            return 0
        messages = []
        for notification, email, enabled in rows:
            if not enabled:
                continue
            message = EmailMessage()
            message["From"], message["To"], message["Subject"] = sender, email, notification.title
            link = f"\n\nОткрыть: {app_url}{notification.link}" if notification.link else ""
            message.set_content(f"{notification.body}{link}\n\n— Цифровая платформа ФСП Оренбургской области")
            messages.append(message)
        try:
            if messages:
                await asyncio.to_thread(_send, messages)
        except OSError as error:
            log.warning("SMTP delivery failed: %s", error)
            return 0
        now = utcnow()
        await db.execute(update(Notification).where(Notification.id.in_([row[0].id for row in rows])).values(emailed_at=now))
        await db.commit()
        return len(messages)


# ---------- API ----------

class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    body: str
    link: str | None
    created_at: datetime
    read_at: datetime | None


class ReadRequest(BaseModel):
    ids: list[int] | None = Field(default=None, max_length=500)


class Settings(BaseModel):
    email_notifications: bool


class UnreadCount(BaseModel):
    unread: int


@router.get("/notifications", response_model=list[NotificationRead])
async def my_notifications(auth_session: AuthSession = Depends(current_auth_session), db: AsyncSession = Depends(get_session)) -> list[Notification]:
    return list(await db.scalars(select(Notification).where(Notification.user_id == auth_session.user_id).order_by(Notification.id.desc()).limit(100)))


@router.get("/notifications/unread-count", response_model=UnreadCount)
async def unread_count(auth_session: AuthSession = Depends(current_auth_session), db: AsyncSession = Depends(get_session)) -> UnreadCount:
    count = await db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == auth_session.user_id, Notification.read_at.is_(None)))
    return UnreadCount(unread=count or 0)


@router.post("/notifications/read", response_model=UnreadCount)
async def mark_read(payload: ReadRequest, auth_session: AuthSession = Depends(csrf_protected_session), db: AsyncSession = Depends(get_session)) -> UnreadCount:
    statement = update(Notification).where(Notification.user_id == auth_session.user_id, Notification.read_at.is_(None))
    if payload.ids is not None:
        statement = statement.where(Notification.id.in_(payload.ids))
    await db.execute(statement.values(read_at=utcnow()))
    await db.commit()
    return await unread_count(auth_session, db)


@router.get("/settings", response_model=Settings)
async def get_settings(auth_session: AuthSession = Depends(current_auth_session)) -> Settings:
    return Settings(email_notifications=auth_session.user.email_notifications)


@router.put("/settings", response_model=Settings)
async def update_settings(payload: Settings, auth_session: AuthSession = Depends(csrf_protected_session), db: AsyncSession = Depends(get_session)) -> Settings:
    auth_session.user.email_notifications = payload.email_notifications
    await db.commit()
    return Settings(email_notifications=auth_session.user.email_notifications)
