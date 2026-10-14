"""Authorization helpers for project operations (RN-AUT-03, RN-PRO-02)."""

from app.modules.projects.domain.entities import Project
from app.modules.projects.domain.ports import ProjectRepository
from app.shared.application.identity import CurrentUser


def can_create_project(user: CurrentUser) -> bool:
    return user.role == "manager"


def can_manage_project(user: CurrentUser, project: Project) -> bool:
    if project.is_deleted():
        return False
    return user.role == "manager" and project.manager_id == user.id


def can_view_project(user: CurrentUser, project: Project, repo: ProjectRepository) -> bool:
    if project.is_deleted():
        return False
    if user.role == "admin":
        return False
    if user.role == "manager" and project.manager_id == user.id:
        return True
    return repo.is_member(project.id, user.id)
