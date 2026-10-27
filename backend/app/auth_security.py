import hashlib
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from argon2.low_level import Type


SESSION_COOKIE = "fsp_session"
CSRF_COOKIE = "fsp_csrf"
SESSION_TTL = timedelta(hours=12)
PUBLIC_ROLES = {"athlete", "coach", "judge"}
ALL_ROLES = PUBLIC_ROLES | {"federation_admin"}

password_hasher = PasswordHasher(type=Type.ID)
DUMMY_PASSWORD_HASH = password_hasher.hash("not-a-real-user-password")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def utcnow() -> datetime:
    return datetime.now(UTC)


def cookie_secure() -> bool:
    return os.getenv("AUTH_COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}


def valid_admin_registration_code(value: str | None) -> bool:
    """Allow administrator signup only when the owner configured a non-empty secret."""
    configured = os.getenv("ADMIN_REGISTRATION_CODE", "")
    return bool(configured) and value is not None and secrets.compare_digest(configured, value)


class LoginRateLimiter:
    """Process-local limiter. Production with multiple workers needs Redis/shared storage."""

    def __init__(self, attempts: int = 5, window_seconds: int = 60) -> None:
        self.attempts = attempts
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - self.window_seconds:
                events.popleft()
            if len(events) >= self.attempts:
                return False
            events.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


login_limiter = LoginRateLimiter()
