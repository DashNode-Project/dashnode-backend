"""
Repository ports for Projects domain.
@sad AD-09, 4.1.2
@origin [SAD-Propuesto]
"""

from datetime import datetime
from typing import Protocol

from app.modules.projects.domain.entities import Project, ProjectMember


class ManagerLookup(Protocol):
    """Cross-cutting lookup for active managers (implemented in orchestration, BR-4)."""

    def is_active_manager(self, user_id: str) -> bool: ...


class ProjectRepository(Protocol):
    """Port for persisting and retrieving projects and members."""

    def get_by_id(self, project_id: str) -> Project | None: ...

    def list_visible_for_user(self, user_id: str, *, role: str) -> list[Project]: ...

    def save(self, project: Project) -> None: ...

    def update(self, project: Project) -> None: ...

    def add_member(self, member: ProjectMember) -> None: ...

    def get_members(self, project_id: str) -> list[ProjectMember]: ...

    def is_member(self, project_id: str, user_id: str) -> bool: ...

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
