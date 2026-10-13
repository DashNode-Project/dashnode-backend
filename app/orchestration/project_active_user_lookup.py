"""Active user lookup for project membership (BR-4)."""

from app.modules.auth.infrastructure.repositories import SqlAlchemyUserRepository
from app.modules.projects.domain.ports import ActiveUserLookup, MemberProfile


class SqlAlchemyActiveUserLookup(ActiveUserLookup):
    def __init__(self, user_repo: SqlAlchemyUserRepository) -> None:
        self._users = user_repo

    def is_active_user(self, user_id: str) -> bool:
        user = self._users.get_by_id(user_id)
        return user is not None and user.is_active

    def display_name(self, user_id: str) -> str | None:
        user = self._users.get_by_id(user_id)
        if user is None:
            return None
        return user.name

    def get_member_profile(self, user_id: str) -> MemberProfile | None:
        user = self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            return None
        return MemberProfile(
            user_id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
        )

    def list_active_users(self, *, query: str = "") -> list[MemberProfile]:
        rows = self._users.list_active_users(name_contains=query or None)
        return [
            MemberProfile(user_id=u.id, name=u.name, email=u.email, role=u.role) for u in rows
        ]
