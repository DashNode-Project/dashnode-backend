"""
@sad AD-10
@origin [SAD-Propuesto]
"""

from enum import StrEnum


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in-progress"
    CODE_REVIEW = "code-review"
    TESTING = "testing"
    FIXING = "fixing"
    COMPLETED = "completed"


# Explicit valid state transitions
VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.TODO: {TaskStatus.IN_PROGRESS},
    TaskStatus.IN_PROGRESS: {TaskStatus.CODE_REVIEW, TaskStatus.TODO},
    TaskStatus.CODE_REVIEW: {TaskStatus.TESTING, TaskStatus.IN_PROGRESS},
    TaskStatus.TESTING: {TaskStatus.FIXING, TaskStatus.COMPLETED},
    TaskStatus.FIXING: {TaskStatus.IN_PROGRESS},
    TaskStatus.COMPLETED: set(),  # terminal state
}


def can_transition(
    current: TaskStatus, target: TaskStatus, has_open_fix: bool = False
) -> tuple[bool, str | None]:
    """
    Checks if a transition between two task statuses is allowed.
    Returns (is_allowed, reason).
    """
    if target == TaskStatus.FIXING and not has_open_fix:
        return False, "No se puede pasar a corrección sin un fix abierto vinculado."

    if target in VALID_TRANSITIONS.get(current, set()):
        return True, None

    return False, f"Transición no permitida de {current.value} a {target.value}."
