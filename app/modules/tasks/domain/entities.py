"""
Domain entities and value objects for Tasks module.
@sad AD-08, AD-10, 4.1.3
@origin [SAD-Propuesto]
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.modules.tasks.domain.transitions import TaskStatus, can_transition
from app.shared.domain.policy import can

__all__ = ["Task", "TaskPriority", "TaskStatus", "can_transition"]


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Task:
    id: str
    project_id: str
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    assignee_id: str | None
    creator_id: str
    has_open_fix: bool
    created_at: datetime
    updated_at: datetime

    def validate(self) -> None:
        """Validates that title and description meet invariants."""
        clean_title = self.title.strip()
        if len(clean_title) < 3:
            raise ValueError("El título de la tarea debe tener al menos 3 caracteres.")
        if len(clean_title) > 200:
            raise ValueError("El título de la tarea no puede exceder 200 caracteres.")

    def change_status(
        self,
        target: TaskStatus,
        actor_id: str,
        actor_role: str,
        when: datetime,
    ) -> None:
        """
        Transitions the task to a new status according to RN-TAR-01 and AD-10.
        """
        # 1. Evaluate authorization policy (ABAC)
        decision = can(
            actor_role=actor_role,
            action="task.update_status",
            context={"assignee_id": self.assignee_id, "user_id": actor_id},
        )
        if not decision.allowed:
            raise ValueError(decision.reason or "No autorizado para cambiar el estado de la tarea.")

        # 2. Evaluate state transition rule
        allowed, reason = can_transition(
            current=self.status,
            target=target,
            has_open_fix=self.has_open_fix,
        )
        if not allowed:
            raise ValueError(reason or f"Transición no permitida de {self.status} a {target}.")

        self.status = target
        self.updated_at = when

    def assign(self, assignee_id: str | None, when: datetime) -> None:
        """Assigns task to a user or clears assignment."""
        self.assignee_id = assignee_id
        self.updated_at = when
