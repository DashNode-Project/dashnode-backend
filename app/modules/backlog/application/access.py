"""Backlog authorization (HU_DN_04_47 .. HU_DN_04_55)."""

from typing import Protocol

from app.shared.application.identity import CurrentUser


class ProjectAccessPort(Protocol):
    def is_member(self, project_id: str, user_id: str) -> bool: ...


class ProjectContext(Protocol):
    id: str
    name: str
    manager_id: str

    def is_deleted(self) -> bool: ...


def can_manage_backlog_structure(user: CurrentUser, project: ProjectContext) -> bool:
    if user.role == "admin":
        return True
    return user.role == "manager" and project.manager_id == user.id


def can_view_backlog(user: CurrentUser, project: ProjectContext, repo: ProjectAccessPort) -> bool:
    if user.role == "admin":
        return True
    if project.is_deleted():
        return False
    if user.role == "manager" and project.manager_id == user.id:
        return True
    return repo.is_member(project.id, user.id)


def can_manage_story_tasks(
    user: CurrentUser, project: ProjectContext, repo: ProjectAccessPort
) -> bool:
    if can_manage_backlog_structure(user, project):
        return True
    return user.role == "developer" and repo.is_member(project.id, user.id)
