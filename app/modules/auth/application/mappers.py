"""
Mapping helpers between domain entities and DTOs.
@sad AD-09
@origin [Archetype Convention Addition]
"""

from app.modules.auth.application.dtos import UserDTO
from app.modules.auth.domain.entities import User


def to_user_dto(user: User) -> UserDTO:
    """Public projection of a user: never includes the password hash."""
    return UserDTO(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
    )
