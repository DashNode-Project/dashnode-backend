"""Sprint authorization (admin or project manager)."""

from app.modules.backlog.application.access import (
    ProjectAccessPort,
    ProjectContext,
    can_manage_backlog_structure,
    can_view_backlog,
)
from app.shared.application.identity import CurrentUser

__all__ = [
    "ProjectAccessPort",
    "ProjectContext",
    "can_manage_sprints",
    "can_view_sprints",
]


def can_manage_sprints(user: CurrentUser, project: ProjectContext) -> bool:
    return can_manage_backlog_structure(user, project)


def can_view_sprints(user: CurrentUser, project: ProjectContext, repo: ProjectAccessPort) -> bool:
    return can_view_backlog(user, project, repo)
