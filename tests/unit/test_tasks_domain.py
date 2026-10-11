"""
Unit tests for Tasks domain entities and invariants.
@sad AD-08, AD-10, 4.1.3, RN-TAR-01
"""

from datetime import UTC, datetime

import pytest

from app.modules.tasks.domain.entities import Task, TaskPriority, TaskStatus


def test_task_validation() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    task = Task(
        id="t-1",
        project_id="p-1",
        title="Valid Title",
        description="",
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        assignee_id="u-1",
        creator_id="u-2",
        has_open_fix=False,
        created_at=now,
        updated_at=now,
    )
    task.validate()

    task.title = "ab"
    with pytest.raises(ValueError, match="al menos 3 caracteres"):
        task.validate()

    task.title = "x" * 201
    with pytest.raises(ValueError, match="no puede exceder 200 caracteres"):
        task.validate()


def test_change_status_authorized_assignee() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    task = Task(
        id="t-1",
        project_id="p-1",
        title="Implement Feature",
        description="",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        assignee_id="dev-123",
        creator_id="mgr-1",
        has_open_fix=False,
        created_at=now,
        updated_at=now,
    )

    # Assigned developer can advance status to in-progress
    later = datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC)
    task.change_status(
        target=TaskStatus.IN_PROGRESS,
        actor_id="dev-123",
        actor_role="developer",
        when=later,
    )
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.updated_at == later


def test_change_status_unauthorized_developer() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    task = Task(
        id="t-1",
        project_id="p-1",
        title="Implement Feature",
        description="",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        assignee_id="dev-123",
        creator_id="mgr-1",
        has_open_fix=False,
        created_at=now,
        updated_at=now,
    )

    # Different developer is denied by RN-TAR-01
    with pytest.raises(ValueError, match="Solo el desarrollador asignado"):
        task.change_status(
            target=TaskStatus.IN_PROGRESS,
            actor_id="other-dev",
            actor_role="developer",
            when=now,
        )


def test_change_status_requires_open_fix_for_fixing() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    task = Task(
        id="t-1",
        project_id="p-1",
        title="Implement Feature",
        description="",
        status=TaskStatus.TESTING,
        priority=TaskPriority.HIGH,
        assignee_id="dev-1",
        creator_id="admin-1",
        has_open_fix=False,
        created_at=now,
        updated_at=now,
    )

    # Admin transition without open fix is rejected
    with pytest.raises(ValueError, match="sin un fix abierto"):
        task.change_status(
            target=TaskStatus.FIXING,
            actor_id="admin-1",
            actor_role="admin",
            when=now,
        )

    # With open fix is permitted
    task.has_open_fix = True
    task.change_status(
        target=TaskStatus.FIXING,
        actor_id="admin-1",
        actor_role="admin",
        when=now,
    )
    assert task.status == TaskStatus.FIXING


def test_task_assignment() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    task = Task(
        id="t-1",
        project_id="p-1",
        title="Task",
        description="",
        status=TaskStatus.TODO,
        priority=TaskPriority.LOW,
        assignee_id=None,
        creator_id="u-1",
        has_open_fix=False,
        created_at=now,
        updated_at=now,
    )
    later = datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC)
    task.assign("dev-new", later)
    assert task.assignee_id == "dev-new"
    assert task.updated_at == later
