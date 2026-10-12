"""
Shared identity representations for authenticated users.
Enables module independence under BR-4.
@sad AD-08, AD-09
@origin [SAD-Propuesto]
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CurrentUser(BaseModel):
    """Normalized identity of an authenticated caller across all modules."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime


class CurrentSession(BaseModel):
    """Authenticated caller together with the validity of the session."""

    user: CurrentUser
    expires_at: datetime
