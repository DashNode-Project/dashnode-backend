"""
Repository ports for Tasks domain.
@sad AD-09, 4.1.3
@origin [SAD-Propuesto]
"""

from typing import Protocol

from app.modules.tasks.domain.entities import Task


class TaskRepository(Protocol):
    """Port for persisting and querying Task domain entities."""

    def get_by_id(self, task_id: str) -> Task | None: ...

    def list_by_project(self, project_id: str) -> list[Task]: ...

    def list_by_assignee(self, assignee_id: str) -> list[Task]: ...

    def save(self, task: Task) -> None: ...

    def update(self, task: Task) -> None: ...
