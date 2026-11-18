"""EP-14 closed event catalog: titles, templates and navigation routes."""

from __future__ import annotations

from enum import StrEnum


class NotificationEventType(StrEnum):
    TASK_ASSIGNED = "TASK_ASSIGNED"
    SPRINT_STARTED = "SPRINT_STARTED"
    ISSUE_REPORTED = "ISSUE_REPORTED"
    ISSUE_ASSIGNED = "ISSUE_ASSIGNED"
    MEETING_SCHEDULED = "MEETING_SCHEDULED"
    MEETING_CANCELLED = "MEETING_CANCELLED"
    DOC_APPROVED = "DOC_APPROVED"
    DOC_REJECTED = "DOC_REJECTED"


ENTITY_BY_TYPE: dict[NotificationEventType, str] = {
    NotificationEventType.TASK_ASSIGNED: "task",
    NotificationEventType.SPRINT_STARTED: "sprint",
    NotificationEventType.ISSUE_REPORTED: "issue",
    NotificationEventType.ISSUE_ASSIGNED: "issue",
    NotificationEventType.MEETING_SCHEDULED: "meeting",
    NotificationEventType.MEETING_CANCELLED: "meeting",
    NotificationEventType.DOC_APPROVED: "documentation_entry",
    NotificationEventType.DOC_REJECTED: "documentation_entry",
}


TITLE_BY_TYPE: dict[NotificationEventType, str] = {
    NotificationEventType.TASK_ASSIGNED: "Tarea asignada",
    NotificationEventType.SPRINT_STARTED: "Sprint iniciado",
    NotificationEventType.ISSUE_REPORTED: "Nuevo issue reportado",
    NotificationEventType.ISSUE_ASSIGNED: "Issue asignado",
    NotificationEventType.MEETING_SCHEDULED: "Reunión programada",
    NotificationEventType.MEETING_CANCELLED: "Reunión cancelada",
    NotificationEventType.DOC_APPROVED: "Entrada aprobada",
    NotificationEventType.DOC_REJECTED: "Entrada rechazada",
}


def build_route(event_type: NotificationEventType, project_id: str, entity_id: str) -> str:
    if event_type == NotificationEventType.TASK_ASSIGNED:
        return f"/proyectos/{project_id}/tareas/lista?task={entity_id}"
    if event_type == NotificationEventType.SPRINT_STARTED:
        return f"/proyectos/{project_id}/sprints"
    if event_type in (NotificationEventType.ISSUE_REPORTED, NotificationEventType.ISSUE_ASSIGNED):
        return f"/proyectos/{project_id}/issues?issue={entity_id}"
    if event_type in (
        NotificationEventType.MEETING_SCHEDULED,
        NotificationEventType.MEETING_CANCELLED,
    ):
        return f"/proyectos/{project_id}/reuniones?meeting={entity_id}"
    if event_type in (NotificationEventType.DOC_APPROVED, NotificationEventType.DOC_REJECTED):
        return f"/proyectos/{project_id}/conocimiento?entry={entity_id}"
    return f"/proyectos/{project_id}"


ALLOWED_ROUTE_PREFIXES: tuple[str, ...] = (
    "/proyectos/",
    "/mis-tareas",
    "/notificaciones",
)
