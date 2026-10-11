"""
SQLAlchemy repository implementation for Tasks.
@sad AD-09, 5.6
@origin [SAD-Propuesto]
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.tasks.domain.entities import Task, TaskPriority, TaskStatus
from app.modules.tasks.domain.ports import TaskRepository
from app.modules.tasks.infrastructure.models import TaskModel


class SqlAlchemyTaskRepository(TaskRepository):
    """SQLAlchemy implementation of the TaskRepository port."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_domain(self, model: TaskModel) -> Task:
        return Task(
            id=model.id,
            project_id=model.project_id,
            title=model.title,
            description=model.description,
            status=TaskStatus(model.status),
            priority=TaskPriority(model.priority),
            assignee_id=model.assignee_id,
            creator_id=model.creator_id,
            has_open_fix=model.has_open_fix,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def get_by_id(self, task_id: str) -> Task | None:
        stmt = select(TaskModel).where(TaskModel.id == task_id)
        result = self._session.execute(stmt).scalar_one_or_none()
        if result is None:
            return None
        return self._to_domain(result)

    def list_by_project(self, project_id: str) -> list[Task]:
        stmt = (
            select(TaskModel)
            .where(TaskModel.project_id == project_id)
            .order_by(TaskModel.created_at.asc())
        )
        results = self._session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in results]

    def list_by_assignee(self, assignee_id: str) -> list[Task]:
        stmt = (
            select(TaskModel)
            .where(TaskModel.assignee_id == assignee_id)
            .order_by(TaskModel.created_at.asc())
        )
        results = self._session.execute(stmt).scalars().all()
        return [self._to_domain(m) for m in results]

    def save(self, task: Task) -> None:
        model = TaskModel(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            status=task.status.value,
            priority=task.priority.value,
            assignee_id=task.assignee_id,
            creator_id=task.creator_id,
            has_open_fix=task.has_open_fix,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        self._session.add(model)

    def update(self, task: Task) -> None:
        stmt = select(TaskModel).where(TaskModel.id == task.id)
        model = self._session.execute(stmt).scalar_one_or_none()
        if model is not None:
            model.title = task.title
            model.description = task.description
            model.status = task.status.value
            model.priority = task.priority.value
            model.assignee_id = task.assignee_id
            model.has_open_fix = task.has_open_fix
            model.updated_at = task.updated_at
