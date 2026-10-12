"""
DTOs and Commands for Auth application layer.
@sad AD-09, 4.1.1
@origin [SAD-Propuesto]
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from app.modules.auth.domain.entities import UserRole


class RegisterManagerCommand(BaseModel):
    """Public registration payload (HU_DN_01_02).

    Business validation is performed by the use case so each failure maps to its
    literal message; here only types and a generous size guard are enforced. `role` is
    accepted only to reject any value other than the Manager role explicitly.
    """

    name: str = Field(default="", max_length=1000)
    email: str = Field(default="", max_length=1000)
    password: str = Field(default="", max_length=1000)
    confirm_password: str = Field(default="", max_length=1000)
    role: str | None = Field(default=None, max_length=50)


class LoginCommand(BaseModel):
    """Login payload (HU_DN_01_03). Validated by the use case for literal messages."""

    email: str = Field(default="", max_length=1000)
    password: str = Field(default="", max_length=1000)


class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    avatar_url: str | None = None


class ProfileDTO(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole
    avatar_url: str | None = None


class UpdateProfileCommand(BaseModel):
    name: str = Field(default="", max_length=1000)


class ProfileResponse(BaseModel):
    message: str | None = None
    profile: ProfileDTO


class RegisterManagerResponse(BaseModel):
    message: str
    user: UserDTO


class SessionInfo(BaseModel):
    """What the client may know about its session (never the token)."""

    user: UserDTO
    expires_at: datetime


class LogoutResponse(BaseModel):
    message: str


class MessageResponse(BaseModel):
    message: str


class RequestPasswordResetCommand(BaseModel):
    email: str = Field(default="", max_length=1000)


class CompletePasswordResetCommand(BaseModel):
    token: str = Field(default="", max_length=512)
    password: str = Field(default="", max_length=1000)
    confirm_password: str = Field(default="", max_length=1000)


class AdminUserSummaryDTO(BaseModel):
    id: str
    name: str
    email: str
    role: UserRole
    is_active: bool


class CreateUserByAdminCommand(BaseModel):
    name: str = Field(default="", max_length=1000)
    email: str = Field(default="", max_length=1000)
    role: str = Field(default="", max_length=50)


class InviteDeveloperCommand(BaseModel):
    name: str = Field(default="", max_length=1000)
    email: str = Field(default="", max_length=1000)
    role: str | None = Field(default=None, max_length=50)


class UpdateUserByAdminCommand(BaseModel):
    name: str = Field(default="", max_length=1000)
    email: str = Field(default="", max_length=1000)
    role: str = Field(default="", max_length=50)


class UpdateUserByAdminResponse(BaseModel):
    message: str
    user: UserDTO


@dataclass(frozen=True)
class LoginResult:
    """Internal result: carries the raw token so the API layer can set the cookie."""

    session: SessionInfo
    token: str = field(repr=False)  # never printed or logged


@dataclass(frozen=True)
class SecurityPolicy:
    """Session and brute-force limits (from configuration)."""

    session_ttl: timedelta
    session_retention: timedelta
    max_failed_attempts: int
    attempt_window: timedelta
