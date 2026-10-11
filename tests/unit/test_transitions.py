"""
Unit tests for Task Transitions domain logic.
@sad AD-10
"""

from app.modules.tasks.domain.transitions import TaskStatus, can_transition


def test_valid_transitions() -> None:
    # TODO -> IN_PROGRESS
    allowed, reason = can_transition(TaskStatus.TODO, TaskStatus.IN_PROGRESS)
    assert allowed is True
    assert reason is None

    # IN_PROGRESS -> CODE_REVIEW
    allowed, reason = can_transition(TaskStatus.IN_PROGRESS, TaskStatus.CODE_REVIEW)
    assert allowed is True
    assert reason is None

    # IN_PROGRESS -> TODO
    allowed, reason = can_transition(TaskStatus.IN_PROGRESS, TaskStatus.TODO)
    assert allowed is True
    assert reason is None

    # CODE_REVIEW -> TESTING
    allowed, reason = can_transition(TaskStatus.CODE_REVIEW, TaskStatus.TESTING)
    assert allowed is True
    assert reason is None

    # TESTING -> COMPLETED
    allowed, reason = can_transition(TaskStatus.TESTING, TaskStatus.COMPLETED)
    assert allowed is True
    assert reason is None


def test_invalid_transition() -> None:
    # Direct jump TODO -> COMPLETED is forbidden
    allowed, reason = can_transition(TaskStatus.TODO, TaskStatus.COMPLETED)
    assert allowed is False
    assert reason is not None
    assert "Transición no permitida" in reason


def test_fixing_transition_requires_open_fix() -> None:
    # Without open fix
    allowed, reason = can_transition(TaskStatus.TESTING, TaskStatus.FIXING, has_open_fix=False)
    assert allowed is False
    assert reason == "No se puede pasar a corrección sin un fix abierto vinculado."

    # With open fix
    allowed, reason = can_transition(TaskStatus.TESTING, TaskStatus.FIXING, has_open_fix=True)
    assert allowed is True
    assert reason is None


def test_completed_is_terminal() -> None:
    allowed, reason = can_transition(TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS)
    assert allowed is False
    assert reason is not None
