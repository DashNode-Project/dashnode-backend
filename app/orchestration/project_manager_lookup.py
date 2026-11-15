"""Orchestration adapter: active manager checks for projects (BR-4)."""

from app.modules.auth.infrastructure.repositories import SqlAlchemyUserRepository
from app.modules.projects.domain.ports import ManagerLookup


class SqlAlchemyManagerLookup(ManagerLookup):
    def __init__(self, user_repo: SqlAlchemyUserRepository) -> None:
        self._users = user_repo

    def is_active_manager(self, user_id: str) -> bool:
        user = self._users.get_by_id(user_id)
        return user is not None and user.is_active and user.role.value == "manager"
