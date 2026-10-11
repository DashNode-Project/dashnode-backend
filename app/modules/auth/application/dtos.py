"""
DTOs and Commands for Auth application layer.
@sad AD-09, 4.1.1
@origin [SAD-Propuesto]
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.auth.domain.entities import UserRole


class RegisterUserCommand(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=2, max_length=100)
    role: UserRole = UserRole.DEVELOPER


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
