"""EP-14 recipient resolution and domain event wiring (orchestration layer)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.infrastructure.models import UserModel
from app.modules.notifications.application.catalog import NotificationEventType
from app.modules.notifications.application.notification_service import (
    NotificationEvent,
    NotificationService,
)
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.id_generator import UuidGenerator

_clock = SystemClock()
_id_gen = UuidGenerator()

_MANAGER_MEMBER_ROLES = frozenset({"manager", "gerente", "lead", "admin", "administrador"})


def build_notification_service(session: Session) -> NotificationService:
    return NotificationService(session=session, id_gen=_id_gen, clock=_clock)


class SqlAlchemyNotificationRecipients:
    def __init__(self, session: Session) -> None:
        self._session = session

    def active_project_member_ids(
        self, project_id: str, *, exclude: str | None = None
    ) -> list[str]:
        ids: set[str] = set()
        members = self._session.scalars(
            select(ProjectMemberModel.user_id).where(ProjectMemberModel.project_id == project_id)
        ).all()
        for user_id in members:
            if exclude is None or user_id != exclude:
                ids.add(user_id)
        project = self._session.get(ProjectModel, project_id)
        if project and project.manager_id and project.manager_id != exclude:
            ids.add(project.manager_id)
        active: list[str] = []
        if not ids:
            return active
        users = self._session.scalars(
            select(UserModel.id).where(UserModel.id.in_(ids), UserModel.is_active.is_(True))
        ).all()
        return list(users)

    def project_manager_ids(self, project_id: str, *, exclude: str | None = None) -> list[str]:
        recipients: set[str] = set()
        project = self._session.get(ProjectModel, project_id)
        if project and project.manager_id and project.manager_id != exclude:
            recipients.add(project.manager_id)
        rows = self._session.execute(
            select(ProjectMemberModel.user_id, ProjectMemberModel.role).where(
                ProjectMemberModel.project_id == project_id
            )
        ).all()
        for user_id, role in rows:
            if exclude is not None and user_id == exclude:
                continue
            if (role or "").lower() in _MANAGER_MEMBER_ROLES:
                recipients.add(user_id)
        if not recipients:
            return []
        active = self._session.scalars(
            select(UserModel.id).where(
                UserModel.id.in_(recipients),
                UserModel.is_active.is_(True),
            )
        ).all()
        return list(active)


class SqlAlchemyDomainNotificationBridge:
    """Facade used by other orchestration adapters."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._service = build_notification_service(session)
        self._recipients = SqlAlchemyNotificationRecipients(session)

    def notify_task_assigned_in_tx(
        self,
        *,
        project_id: str,
        task_id: str,
        task_name: str,
        project_name: str,
        assignee_id: str,
        actor_id: str,
        version: int,
    ) -> None:
        event = NotificationEvent(
            type=NotificationEventType.TASK_ASSIGNED,
            event_key=f"TASK_ASSIGNED:{task_id}:{version}",
            project_id=project_id,
            entity_id=task_id,
            actor_id=actor_id,
            context={"task": task_name, "project": project_name},
        )
        self._service.notify(event=event, recipients=[assignee_id], actor_id=actor_id)

    def notify_sprint_started_in_tx(
        self,
        *,
        project_id: str,
        sprint_id: str,
        sprint_name: str,
        project_name: str,
        actor_id: str,
    ) -> None:
        recipients = self._recipients.active_project_member_ids(project_id, exclude=actor_id)
        event = NotificationEvent(
            type=NotificationEventType.SPRINT_STARTED,
            event_key=f"SPRINT_STARTED:{sprint_id}:1",
            project_id=project_id,
            entity_id=sprint_id,
            actor_id=actor_id,
            context={"sprint": sprint_name, "project": project_name},
        )
        self._service.notify(event=event, recipients=recipients, actor_id=actor_id)

    def notify_issue_reported_in_tx(
        self,
        *,
        project_id: str,
        issue_id: str,
        title: str,
        project_name: str,
        severity: str,
        actor_id: str,
        version: int = 1,
    ) -> None:
        recipients = self._recipients.project_manager_ids(project_id, exclude=actor_id)
        event = NotificationEvent(
            type=NotificationEventType.ISSUE_REPORTED,
            event_key=f"ISSUE_REPORTED:{issue_id}:{version}",
            project_id=project_id,
            entity_id=issue_id,
            actor_id=actor_id,
            context={"issue": title, "project": project_name, "severity": severity},
        )
        self._service.notify(event=event, recipients=recipients, actor_id=actor_id)

    def notify_issue_assigned_in_tx(
        self,
        *,
        project_id: str,
        issue_id: str,
        title: str,
        project_name: str,
        assignee_id: str | None,
        actor_id: str,
        version: int,
    ) -> None:
        if not assignee_id:
            return
        event = NotificationEvent(
            type=NotificationEventType.ISSUE_ASSIGNED,
            event_key=f"ISSUE_ASSIGNED:{issue_id}:{version}",
            project_id=project_id,
            entity_id=issue_id,
            actor_id=actor_id,
            context={"issue": title, "project": project_name},
        )
        self._service.notify(event=event, recipients=[assignee_id], actor_id=actor_id)

    def notify_meeting_scheduled_in_tx(
        self,
        *,
        project_id: str,
        meeting_id: str,
        meeting_title: str,
        when_label: str,
        participant_ids: list[str],
        actor_id: str | None,
    ) -> None:
        event = NotificationEvent(
            type=NotificationEventType.MEETING_SCHEDULED,
            event_key=f"MEETING_SCHEDULED:{meeting_id}:1",
            project_id=project_id,
            entity_id=meeting_id,
            actor_id=actor_id,
            context={"meeting": meeting_title, "when": when_label},
        )
        self._service.notify(event=event, recipients=participant_ids, actor_id=actor_id)

    def notify_meeting_cancelled_in_tx(
        self,
        *,
        project_id: str,
        meeting_id: str,
        meeting_title: str,
        when_label: str,
        participant_ids: list[str],
        actor_id: str | None,
    ) -> None:
        event = NotificationEvent(
            type=NotificationEventType.MEETING_CANCELLED,
            event_key=f"MEETING_CANCELLED:{meeting_id}:1",
            project_id=project_id,
            entity_id=meeting_id,
            actor_id=actor_id,
            context={"meeting": meeting_title, "when": when_label},
        )
        self._service.notify(event=event, recipients=participant_ids, actor_id=actor_id)

    def notify_doc_approved_in_tx(
        self,
        *,
        project_id: str,
        entry_id: str,
        entry_title: str,
        author_id: str,
        actor_id: str,
    ) -> None:
        event = NotificationEvent(
            type=NotificationEventType.DOC_APPROVED,
            event_key=f"DOC_APPROVED:{entry_id}:1",
            project_id=project_id,
            entity_id=entry_id,
            actor_id=actor_id,
            context={"entry": entry_title},
        )
        self._service.notify(event=event, recipients=[author_id], actor_id=actor_id)

    def notify_doc_rejected_in_tx(
        self,
        *,
        project_id: str,
        entry_id: str,
        entry_title: str,
        author_id: str,
        actor_id: str,
    ) -> None:
        event = NotificationEvent(
            type=NotificationEventType.DOC_REJECTED,
            event_key=f"DOC_REJECTED:{entry_id}:1",
            project_id=project_id,
            entity_id=entry_id,
            actor_id=actor_id,
            context={"entry": entry_title},
        )
        self._service.notify(event=event, recipients=[author_id], actor_id=actor_id)
