"""
Domain entities and value objects for the Auth module.
@sad AD-08, 4.1.1
@origin [SAD-Propuesto]
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    MANAGER = "manager"
    DEVELOPER = "developer"


@dataclass
class User:
    id: str
    email: str
    hashed_password: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    def can_authenticate(self) -> bool:
        """Determines if the user account is allowed to log in."""
        return self.is_active

    def deactivate(self, when: datetime) -> None:
        """Deactivates user account."""
        self.is_active = False
        self.updated_at = when
