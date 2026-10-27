from typing import Literal

from pydantic import BaseModel, Field, field_validator


RegistrationRole = Literal["athlete", "coach", "judge", "federation_admin"]


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=128)
    role: RegistrationRole = "athlete"
    admin_registration_code: str | None = Field(default=None, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized.count("@") != 1:
            raise ValueError("Некорректный email")
        local, domain = normalized.rsplit("@", 1)
        if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("Некорректный email")
        return normalized


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class RoleSwitchRequest(BaseModel):
    role: str = Field(min_length=1, max_length=40)


class UserRead(BaseModel):
    id: int
    email: str
    roles: list[str]
    active_role: str
