"""
Unit tests for ABAC Policy and Decision domain logic.
@sad AD-08
"""

from app.shared.domain.decision import Decision
from app.shared.domain.policy import can


def test_decision_creation() -> None:
    perm = Decision.permit()
    assert perm.allowed is True
    assert perm.reason is None

    den = Decision.deny("Razón de rechazo")
    assert den.allowed is False
    assert den.reason == "Razón de rechazo"


def test_admin_has_full_access() -> None:
    decision = can(actor_role="admin", action="any.action", context={})
    assert decision.allowed is True


def test_task_update_status_policy() -> None:
    # Assigned user can update status
    decision = can(
        actor_role="developer",
        action="task.update_status",
        context={"assignee_id": "user-123", "user_id": "user-123"},
    )
    assert decision.allowed is True

    # Different user cannot update status
    decision_other = can(
        actor_role="developer",
        action="task.update_status",
        context={"assignee_id": "user-123", "user_id": "user-456"},
    )
    assert decision_other.allowed is False
    assert "Solo el desarrollador asignado" in (decision_other.reason or "")


def test_task_create_policy() -> None:
    # Manager can create
    decision_manager = can(actor_role="manager", action="task.create", context={})
    assert decision_manager.allowed is True

    # Developer cannot create directly if policy restricts to manager/admin
    decision_dev = can(actor_role="developer", action="task.create", context={})
    assert decision_dev.allowed is False
    assert "Solo un Gerente o Administrador" in (decision_dev.reason or "")


def test_unhandled_action_defaults_to_deny() -> None:
    decision = can(actor_role="developer", action="unknown.action", context={})
    assert decision.allowed is False
    assert "Operación no permitida" in (decision.reason or "")
