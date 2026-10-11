"""
Unit tests for Projects domain logic.
@sad AD-08, 4.1.2
"""

from datetime import UTC, datetime

import pytest

from app.modules.projects.domain.entities import Project, ProjectMember, ProjectRole


def test_project_validation_success() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    project = Project(
        id="proj-1",
        name="Valid Project",
        description="A solid description",
        owner_id="usr-1",
        created_at=now,
        updated_at=now,
    )
    # Should not raise
    project.validate_name()
    assert project.name == "Valid Project"


def test_project_validation_name_too_short() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    project = Project(
        id="proj-1",
        name="ab",
        description="",
        owner_id="usr-1",
        created_at=now,
        updated_at=now,
    )
    with pytest.raises(ValueError, match="al menos 3 caracteres"):
        project.validate_name()


def test_project_validation_name_too_long() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    project = Project(
        id="proj-1",
        name="x" * 101,
        description="",
        owner_id="usr-1",
        created_at=now,
        updated_at=now,
    )
    with pytest.raises(ValueError, match="no puede exceder 100 caracteres"):
        project.validate_name()


def test_project_member_creation() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    member = ProjectMember(
        project_id="proj-1",
        user_id="usr-2",
        role=ProjectRole.MEMBER,
        joined_at=now,
    )
    assert member.role == ProjectRole.MEMBER
    assert member.user_id == "usr-2"
