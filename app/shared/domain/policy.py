"""
@sad AD-08
@origin [SAD-Propuesto]
"""

from app.shared.domain.decision import Decision


def can(actor_role: str, action: str, context: dict[str, object]) -> Decision:
    """
    Evaluates permissions based on actor, action, and resource context.
    Default deny.
    """
    if actor_role == "admin":
        return Decision.permit()

    if action == "task.update_status":
        # SAD RN-TAR-01: Only assigned user can move task
        assignee_id = context.get("assignee_id")
        user_id = context.get("user_id")
        if assignee_id and user_id and assignee_id == user_id:
            return Decision.permit()
        return Decision.deny("Solo el desarrollador asignado puede cambiar el estado de la tarea.")

    if action == "task.create":
        # Manager or Admin can create tasks
        if actor_role in ["manager", "admin"]:
            return Decision.permit()
        return Decision.deny("Solo un Gerente o Administrador puede crear tareas.")

    return Decision.deny("Operación no permitida para el rol.")
