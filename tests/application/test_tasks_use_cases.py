"""
Application tests for Tasks use cases.
@sad AD-09, 4.1.3
"""

from datetime import UTC, datetime

import pytest

from app.modules.tasks.application.dtos import (
    AssignTaskCommand,
    CreateTaskCommand,
    UpdateTaskStatusCommand,
)
from app.modules.tasks.application.use_cases import (
    AssignTaskUseCase,
    CreateTaskUseCase,
    GetTaskUseCase,
    ListProjectTasksUseCase,
    UpdateTaskStatusUseCase,
)
from app.modules.tasks.domain.entities import Task, TaskPriority, TaskStatus
from app.shared.application.ports import UnitOfWork


class FakeTaskRepository:
    def __init__(self) -> None:
        self.tasks: dict[str, Task] = {}

    def get_by_id(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    def list_by_project(self, project_id: str) -> list[Task]:
        return [t for t in self.tasks.values() if t.project_id == project_id]

    def list_by_assignee(self, assignee_id: str) -> list[Task]:
        return [t for t in self.tasks.values() if t.assignee_id == assignee_id]

    def save(self, task: Task) -> None:
        self.tasks[task.id] = task

    def update(self, task: Task) -> None:
        self.tasks[task.id] = task


class FakeClock:
    def __init__(self, now_time: datetime) -> None:
        self._now = now_time

    def now(self) -> datetime:
        return self._now


class FakeIdGenerator:
    def __init__(self, fixed_id: str = "task-555") -> None:
        self.fixed_id = fixed_id

    def generate(self) -> str:
        return self.fixed_id


class FakeUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self) -> "FakeUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        pass

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass


def test_create_task_use_case() -> None:
    repo = FakeTaskRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    id_gen = FakeIdGenerator("t-123")
    uow = FakeUnitOfWork()

    uc = CreateTaskUseCase(task_repo=repo, id_gen=id_gen, clock=clock, uow=uow)
    cmd = CreateTaskCommand(
        project_id="proj-1",
        title="Setup Database",
        description="Run migration",
        priority=TaskPriority.HIGH,
        assignee_id="dev-1",
    )
    result = uc.execute(cmd=cmd, creator_id="mgr-1", creator_role="manager")

    assert result.id == "t-123"
    assert result.title == "Setup Database"
    assert result.status == TaskStatus.TODO
    assert result.priority == TaskPriority.HIGH
    assert result.assignee_id == "dev-1"
    assert uow.committed is True


def test_update_task_status_use_case() -> None:
    repo = FakeTaskRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    uow = FakeUnitOfWork()

    task = Task(
        id="t-1",
        project_id="p-1",
        title="Fix bug",
        description="",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        assignee_id="dev-1",
        creator_id="mgr-1",
        has_open_fix=False,
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    repo.save(task)

    uc = UpdateTaskStatusUseCase(task_repo=repo, clock=clock, uow=uow)
    cmd = UpdateTaskStatusCommand(status=TaskStatus.IN_PROGRESS)
    result = uc.execute(task_id="t-1", cmd=cmd, actor_id="dev-1", actor_role="developer")

    assert result.status == TaskStatus.IN_PROGRESS
    assert uow.committed is True


def test_assign_task_use_case() -> None:
    repo = FakeTaskRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))
    uow = FakeUnitOfWork()

    task = Task(
        id="t-1",
        project_id="p-1",
        title="Task",
        description="",
        status=TaskStatus.TODO,
        priority=TaskPriority.LOW,
        assignee_id=None,
        creator_id="mgr-1",
        has_open_fix=False,
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    repo.save(task)

    uc = AssignTaskUseCase(task_repo=repo, clock=clock, uow=uow)
    cmd = AssignTaskCommand(assignee_id="dev-2")

    # Manager can assign
    result = uc.execute(task_id="t-1", cmd=cmd, actor_id="mgr-1", actor_role="manager")
    assert result.assignee_id == "dev-2"
    assert uow.committed is True

    # Unauthorized dev cannot assign
    with pytest.raises(ValueError, match="No tienes permisos"):
        uc.execute(task_id="t-1", cmd=cmd, actor_id="stranger-dev", actor_role="developer")


def test_list_and_get_tasks() -> None:
    repo = FakeTaskRepository()
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC))

    task = Task(
        id="t-1",
        project_id="p-1",
        title="Task 1",
        description="",
        status=TaskStatus.TODO,
        priority=TaskPriority.LOW,
        assignee_id=None,
        creator_id="mgr-1",
        has_open_fix=False,
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    repo.save(task)

    list_uc = ListProjectTasksUseCase(task_repo=repo)
    tasks = list_uc.execute("p-1")
    assert len(tasks) == 1
    assert tasks[0].id == "t-1"

    get_uc = GetTaskUseCase(task_repo=repo)
    t = get_uc.execute("t-1")
    assert t.title == "Task 1"

    with pytest.raises(ValueError, match="no encontrada"):
        get_uc.execute("non-existent-task")
