"""
DTOs and Commands for Auth application layer.
@sad AD-09, 4.1.1
@origin [SAD-Propuesto]
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105


class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class RegisterManagerResponse(BaseModel):
    message: str
    user: UserDTO
