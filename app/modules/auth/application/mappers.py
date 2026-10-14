"""
Mapping helpers between domain entities and DTOs.
@sad AD-09
@origin [Archetype Convention Addition]
"""

from app.modules.auth.application.dtos import ProfileDetailsDTO, ProfileDTO, UserDTO
from app.modules.auth.domain.entities import User


def avatar_url_for(user: User) -> str | None:
    if not user.avatar_key:
        return None
    return "/api/v1/auth/profile/avatar"


def to_user_dto(user: User) -> UserDTO:
    """Public projection of a user: never includes the password hash."""
    return UserDTO(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        avatar_url=avatar_url_for(user),
    )


def _profile_details_from_user(user: User) -> ProfileDetailsDTO:
    raw = user.profile_details or {}
    skills = raw.get("skills") or []
    if not isinstance(skills, list):
        skills = []
    return ProfileDetailsDTO(
        last_name=raw.get("last_name"),
        nickname=raw.get("nickname"),
        description=raw.get("description"),
        experience=raw.get("experience"),
        skills=[str(s) for s in skills],
        github=raw.get("github"),
        linkedin=raw.get("linkedin"),
    )


def to_profile_dto(user: User) -> ProfileDTO:
    return ProfileDTO(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        avatar_url=avatar_url_for(user),
        details=_profile_details_from_user(user),
    )
