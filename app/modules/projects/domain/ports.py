"""
Repository ports for Projects domain.
@sad AD-09, 4.1.2
@origin [SAD-Propuesto]
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.projects.domain.entities import Project, ProjectMember
from app.modules.projects.domain.health import ProjectHealthSnapshot


@dataclass(frozen=True)
class MemberProfile:
    user_id: str
    name: str
    email: str
    role: str


class ManagerLookup(Protocol):
    """Cross-cutting lookup for active managers (implemented in orchestration, BR-4)."""

    def is_active_manager(self, user_id: str) -> bool: ...


class ProjectDeletionCollaborator(Protocol):
    """Optional cross-module cleanup when a project is soft-deleted (wired in orchestration)."""

    def after_project_soft_deleted(self, project_id: str, when: datetime) -> None: ...


class ActiveUserLookup(Protocol):
    """Resolves active users for project membership (BR-4 via orchestration)."""

    def is_active_user(self, user_id: str) -> bool: ...

    def display_name(self, user_id: str) -> str | None: ...

    def get_member_profile(self, user_id: str) -> MemberProfile | None: ...

    def list_active_users(self, *, query: str = "") -> list[MemberProfile]: ...


class ProjectRepository(Protocol):
    """Port for persisting and retrieving projects and members."""

    def get_by_id(self, project_id: str) -> Project | None: ...

    def list_visible_for_user(self, user_id: str, *, role: str) -> list[Project]: ...

    def save(self, project: Project) -> None: ...

    def update(self, project: Project) -> None: ...

    def add_member(self, member: ProjectMember) -> None: ...

    def remove_member(self, project_id: str, user_id: str) -> None: ...

    def get_members(self, project_id: str) -> list[ProjectMember]: ...

    def is_member(self, project_id: str, user_id: str) -> bool: ...

    def clear_assignee_tasks(self, project_id: str, user_id: str, *, when: datetime) -> None: ...

    def get_health_snapshot(self, project_id: str) -> ProjectHealthSnapshot: ...

    def soft_delete_cascade(self, project_id: str, when: datetime) -> None: ...

    def add_audit_entry(
        self,
        *,
        entry_id: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        when: datetime,
    ) -> None: ...
