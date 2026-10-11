"""
Use cases for Tasks management.
@sad AD-09, 4.1.3, RN-TAR-01, RN-TAR-02
@origin [SAD-Propuesto]
"""

from app.modules.tasks.application.dtos import (
    AssignTaskCommand,
    CreateTaskCommand,
    TaskDTO,
    UpdateTaskStatusCommand,
)
from app.modules.tasks.domain.entities import Task, TaskStatus
from app.modules.tasks.domain.ports import TaskRepository
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork


class CreateTaskUseCase:
    """Handles task creation."""

    def __init__(
        self,
        task_repo: TaskRepository,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._repo = task_repo
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow

    def execute(self, cmd: CreateTaskCommand, creator_id: str, creator_role: str) -> TaskDTO:
        now = self._clock.now()
        task_id = self._id_gen.generate()

        task = Task(
            id=task_id,
            project_id=cmd.project_id,
            title=cmd.title.strip(),
            description=cmd.description.strip(),
            status=TaskStatus.TODO,
            priority=cmd.priority,
            assignee_id=cmd.assignee_id,
            creator_id=creator_id,
            has_open_fix=False,
            created_at=now,
            updated_at=now,
        )
        task.validate()

        with self._uow:
            self._repo.save(task)
            self._uow.commit()

        return self._to_dto(task)

    @staticmethod
    def _to_dto(task: Task) -> TaskDTO:
        return TaskDTO(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            assignee_id=task.assignee_id,
            creator_id=task.creator_id,
            has_open_fix=task.has_open_fix,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class UpdateTaskStatusUseCase:
    """Handles task state transitions enforcing RN-TAR-01 and AD-10."""

    def __init__(
        self,
        task_repo: TaskRepository,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._repo = task_repo
        self._clock = clock
        self._uow = uow

    def execute(
        self,
        task_id: str,
        cmd: UpdateTaskStatusCommand,
        actor_id: str,
        actor_role: str,
    ) -> TaskDTO:
        task = self._repo.get_by_id(task_id)
        if task is None:
            raise ValueError("Tarea no encontrada.")

        now = self._clock.now()
        task.change_status(
            target=cmd.status,
            actor_id=actor_id,
            actor_role=actor_role,
            when=now,
        )

        with self._uow:
            self._repo.update(task)
            self._uow.commit()

        return TaskDTO(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            assignee_id=task.assignee_id,
            creator_id=task.creator_id,
            has_open_fix=task.has_open_fix,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class AssignTaskUseCase:
    """Assigns or unassigns a task."""

    def __init__(
        self,
        task_repo: TaskRepository,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._repo = task_repo
        self._clock = clock
        self._uow = uow

    def execute(
        self,
        task_id: str,
        cmd: AssignTaskCommand,
        actor_id: str,
        actor_role: str,
    ) -> TaskDTO:
        task = self._repo.get_by_id(task_id)
        if task is None:
            raise ValueError("Tarea no encontrada.")

        # Only Manager, Admin or current Assignee can reassign
        if actor_role not in ["manager", "admin"] and task.assignee_id != actor_id:
            raise ValueError("No tienes permisos para reasignar esta tarea.")

        now = self._clock.now()
        task.assign(assignee_id=cmd.assignee_id, when=now)

        with self._uow:
            self._repo.update(task)
            self._uow.commit()

        return TaskDTO(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            assignee_id=task.assignee_id,
            creator_id=task.creator_id,
            has_open_fix=task.has_open_fix,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class ListProjectTasksUseCase:
    """Lists all tasks for a given project."""

    def __init__(self, task_repo: TaskRepository) -> None:
        self._repo = task_repo

    def execute(self, project_id: str) -> list[TaskDTO]:
        tasks = self._repo.list_by_project(project_id)
        return [
            TaskDTO(
                id=t.id,
                project_id=t.project_id,
                title=t.title,
                description=t.description,
                status=t.status,
                priority=t.priority,
                assignee_id=t.assignee_id,
                creator_id=t.creator_id,
                has_open_fix=t.has_open_fix,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tasks
        ]


class GetTaskUseCase:
    """Retrieves a single task by ID."""

    def __init__(self, task_repo: TaskRepository) -> None:
        self._repo = task_repo

    def execute(self, task_id: str) -> TaskDTO:
        task = self._repo.get_by_id(task_id)
        if task is None:
            raise ValueError("Tarea no encontrada.")

        return TaskDTO(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            assignee_id=task.assignee_id,
            creator_id=task.creator_id,
            has_open_fix=task.has_open_fix,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
