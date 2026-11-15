"""Project access aligns list_visible with assistant RBAC."""

from datetime import UTC, datetime

from app.modules.projects.domain.entities import (
    Project,
    ProjectPriority,
    ProjectStatus,
)
from tests.application.test_projects_use_cases import FakeProjectRepository


def test_manager_assigned_without_membership_can_access() -> None:
    repo = FakeProjectRepository()
    now = datetime.now(UTC)
    project = Project(
        id="medifast-like",
        name="Medifast",
        description="Legacy project",
        owner_id="owner-1",
        manager_id="mgr-1",
        priority=ProjectPriority.MEDIA,
        tech_stack=[],
        meeting_link=None,
        status=ProjectStatus.ACTIVO,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    repo.save(project)
    assert repo.is_member(project.id, "mgr-1") is False
    assert repo.user_can_access(project.id, "mgr-1", "manager") is True
    assert repo.user_can_access(project.id, "stranger", "manager") is False
