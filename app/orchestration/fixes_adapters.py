"""Cross-module orchestration adapters for EP-11 Fixes (BR-4 isolation).

@sad AD-08, AD-09
@origin [User Stories HU_DN_07_97 .. HU_DN_07_105]
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.infrastructure.models import UserModel
from app.modules.backlog.infrastructure.models import StoryTaskModel, TaskStatusHistoryModel
from app.modules.fixes.domain.entities import TaskSnapshot
from app.modules.notifications.infrastructure.models import NotificationModel
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.id_generator import UuidGenerator

_clock = SystemClock()
_id_gen = UuidGenerator()


def _task_model_to_snapshot(model: StoryTaskModel) -> TaskSnapshot:
    return TaskSnapshot(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        status=model.status,
        assignee_id=model.assignee_id,
        status_before_correction=model.status_before_correction,
        version=int(model.version) if model.version is not None else 1,
    )


class SqlAlchemyUserLookup:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_display(self, user_id: str) -> tuple[str, str | None] | None:
        user = self._session.get(UserModel, user_id)
        if user is None:
            return None
        return (user.name or "").strip(), user.avatar_key


class SqlAlchemyProjectLookup:
    def __init__(self, session: Session) -> None:
        self._session = session

    def is_active_member(self, project_id: str, user_id: str) -> bool:
        project = self._session.get(ProjectModel, project_id)
        if project is None or project.deleted_at is not None:
            return False
        user = self._session.get(UserModel, user_id)
        if user is None or not user.is_active:
            return False
        role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
        if role_val in ("admin", "administrador"):
            return True
        if project.manager_id == user_id:
            return True
        member = self._session.get(ProjectMemberModel, (project_id, user_id))
        return member is not None

    def is_active_developer_member(self, project_id: str, user_id: str) -> bool:
        project = self._session.get(ProjectModel, project_id)
        if project is None or project.deleted_at is not None:
            return False
        user = self._session.get(UserModel, user_id)
        if user is None or not user.is_active:
            return False
        role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
        if role_val.lower() not in ("developer", "desarrollador"):
            return False
        member = self._session.get(ProjectMemberModel, (project_id, user_id))
        return member is not None


class SqlAlchemyFixTaskCoordinator:
    """Locks and transitions StoryTask rows atomically inside the active UoW transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_task_snapshot(self, project_id: str, task_id: str) -> TaskSnapshot | None:
        stmt = select(StoryTaskModel).where(
            StoryTaskModel.id == task_id,
            StoryTaskModel.project_id == project_id,
        )
        model = self._session.scalars(stmt).first()
        return _task_model_to_snapshot(model) if model is not None else None

    def get_task_snapshots_map(self, task_ids: list[str]) -> dict[str, TaskSnapshot]:
        unique_ids = list({tid for tid in task_ids if tid})
        if not unique_ids:
            return {}
        stmt = select(StoryTaskModel).where(StoryTaskModel.id.in_(unique_ids))
        models = self._session.scalars(stmt).all()
        return {m.id: _task_model_to_snapshot(m) for m in models}

    def lock_task_for_update(self, project_id: str, task_id: str) -> TaskSnapshot | None:
        stmt = (
            select(StoryTaskModel)
            .where(
                StoryTaskModel.id == task_id,
                StoryTaskModel.project_id == project_id,
            )
            .with_for_update()
        )
        model = self._session.scalars(stmt).first()
        return _task_model_to_snapshot(model) if model is not None else None

    def transition_task_to_correction(
        self,
        *,
        task: TaskSnapshot,
        actor_id: str,
        history_id: str,
        when: datetime,
    ) -> TaskSnapshot:
        stmt = (
            select(StoryTaskModel)
            .where(
                StoryTaskModel.id == task.id,
                StoryTaskModel.project_id == task.project_id,
            )
            .with_for_update()
        )
        model = self._session.scalars(stmt).first()
        if model is None:
            raise LookupError("La tarea solicitada no existe.")

        if model.status != "CORRECTION":
            previous_status = model.status
            model.status_before_correction = previous_status
            model.status = "CORRECTION"
            self._session.add(
                TaskStatusHistoryModel(
                    id=history_id,
                    task_id=model.id,
                    user_id=actor_id,
                    previous_status=previous_status,
                    new_status="CORRECTION",
                    changed_at=when,
                )
            )

        model.version = (int(model.version) if model.version is not None else 1) + 1
        model.updated_at = when
        self._session.flush()
        return _task_model_to_snapshot(model)

    def restore_task_from_correction(
        self,
        *,
        task: TaskSnapshot,
        target_status: str,
        actor_id: str,
        history_id: str,
        when: datetime,
    ) -> TaskSnapshot:
        stmt = (
            select(StoryTaskModel)
            .where(
                StoryTaskModel.id == task.id,
                StoryTaskModel.project_id == task.project_id,
            )
            .with_for_update()
        )
        model = self._session.scalars(stmt).first()
        if model is None:
            raise LookupError("La tarea solicitada no existe.")

        previous_status = model.status
        model.status = target_status
        model.status_before_correction = None
        model.version = (int(model.version) if model.version is not None else 1) + 1
        model.updated_at = when
        self._session.add(
            TaskStatusHistoryModel(
                id=history_id,
                task_id=model.id,
                user_id=actor_id,
                previous_status=previous_status,
                new_status=target_status,
                changed_at=when,
            )
        )
        self._session.flush()
        return _task_model_to_snapshot(model)


class SqlAlchemyIssueNotificationSender:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _project_recipients(self, project_id: str, exclude_user_id: str) -> set[str]:
        project = self._session.get(ProjectModel, project_id)
        if project is None:
            return set()
        recipients: set[str] = set()
        if project.manager_id and project.manager_id != exclude_user_id:
            recipients.add(project.manager_id)
        members = (
            self._session.query(ProjectMemberModel.user_id)
            .filter(ProjectMemberModel.project_id == project_id)
            .all()
        )
        for (m_id,) in members:
            if m_id != exclude_user_id:
                recipients.add(m_id)
        return recipients

    def notify_issue_created(
        self,
        project_id: str,
        issue_id: str,
        title: str,
        reporter_id: str,
    ) -> None:
        recipients = self._project_recipients(project_id, reporter_id)
        now = _clock.now()
        for r_id in recipients:
            self._session.add(
                NotificationModel(
                    id=_id_gen.generate(),
                    recipient_id=r_id,
                    type="issue_created",
                    title="Nuevo Fix creado",
                    message=f"Se ha registrado el issue: {title}",
                    is_read=False,
                    created_at=now,
                )
            )
        try:
            self._session.commit()
        except Exception:
            self._session.rollback()

    def notify_issue_assigned_in_tx(
        self,
        *,
        project_id: str,
        issue_id: str,
        title: str,
        assignee_id: str | None,
        actor_id: str,
        when: datetime,
    ) -> None:
        if not assignee_id or assignee_id == actor_id:
            return
        self._session.add(
            NotificationModel(
                id=_id_gen.generate(),
                recipient_id=assignee_id,
                type="issue_assigned",
                title="Issue asignado",
                message=f"Se te ha asignado el issue: {title}",
                is_read=False,
                created_at=when,
            )
        )

    def notify_issue_resolved_in_tx(
        self,
        *,
        project_id: str,
        issue_id: str,
        title: str,
        reporter_id: str,
        assignee_id: str | None,
        actor_id: str,
        when: datetime,
    ) -> None:
        recipients: set[str] = set()
        project = self._session.get(ProjectModel, project_id)
        if project and project.manager_id and project.manager_id != actor_id:
            recipients.add(project.manager_id)
        if reporter_id != actor_id:
            recipients.add(reporter_id)
        if assignee_id and assignee_id != actor_id:
            recipients.add(assignee_id)
        for r_id in recipients:
            self._session.add(
                NotificationModel(
                    id=_id_gen.generate(),
                    recipient_id=r_id,
                    type="issue_resolved",
                    title="Issue resuelto",
                    message=f"Se ha resuelto el issue: {title}",
                    is_read=False,
                    created_at=when,
                )
            )

    def notify_task_fix_reported_in_tx(
        self,
        *,
        project_id: str,
        issue_id: str,
        task_id: str,
        task_name: str,
        title: str,
        reporter_id: str,
        when: datetime,
    ) -> None:
        recipients = self._project_recipients(project_id, reporter_id)
        for r_id in recipients:
            self._session.add(
                NotificationModel(
                    id=_id_gen.generate(),
                    recipient_id=r_id,
                    type="task_fix_reported",
                    title="Fix reportado en tarea",
                    message=f"Se reportó el fix '{title}' en la tarea: {task_name}",
                    is_read=False,
                    created_at=when,
                )
            )
