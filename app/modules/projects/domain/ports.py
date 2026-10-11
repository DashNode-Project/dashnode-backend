"""
Repository ports for Projects domain.
@sad AD-09, 4.1.2
@origin [SAD-Propuesto]
"""

from typing import Protocol

from app.modules.projects.domain.entities import Project, ProjectMember


class ProjectRepository(Protocol):
    """Port for persisting and retrieving projects and members."""

    def get_by_id(self, project_id: str) -> Project | None:
        ...

    def list_by_user(self, user_id: str) -> list[Project]:
        ...

    def save(self, project: Project) -> None:
        ...

    def update(self, project: Project) -> None:
        ...

    def add_member(self, member: ProjectMember) -> None:
        ...

    def get_members(self, project_id: str) -> list[ProjectMember]:
        ...

    def is_member(self, project_id: str, user_id: str) -> bool:
        ...
