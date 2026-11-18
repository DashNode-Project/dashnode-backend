"""Cross-module orchestration adapters for EP-11 Fixes (BR-4 isolation).

@sad AD-08, AD-09
@origin [User Stories HU_DN_07_97 .. HU_DN_07_105]
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ai.infrastructure.models import AiDailyUsageModel, SystemConfigModel
from app.modules.auth.infrastructure.models import UserModel
from app.modules.backlog.infrastructure.models import StoryTaskModel, TaskStatusHistoryModel
from app.modules.fixes.domain.entities import TaskSnapshot
from app.orchestration.notification_adapters import SqlAlchemyDomainNotificationBridge
from app.modules.projects.infrastructure.models import (
    AuditLogModel,
    ProjectMemberModel,
    ProjectModel,
)
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
        self._bridge = SqlAlchemyDomainNotificationBridge(session)

    def _project_name(self, project_id: str) -> str:
        project = self._session.get(ProjectModel, project_id)
        return (project.name if project else "") or "el proyecto"

    def notify_issue_created(
        self,
        project_id: str,
        issue_id: str,
        title: str,
        reporter_id: str,
        *,
        severity: str = "MEDIA",
        actor_id: str | None = None,
    ) -> None:
        self._bridge.notify_issue_reported_in_tx(
            project_id=project_id,
            issue_id=issue_id,
            title=title,
            project_name=self._project_name(project_id),
            severity=severity,
            actor_id=actor_id or reporter_id,
        )

    def notify_issue_assigned_in_tx(
        self,
        *,
        project_id: str,
        issue_id: str,
        title: str,
        assignee_id: str | None,
        actor_id: str,
        when: datetime,
        version: int = 1,
    ) -> None:
        _ = when
        if not assignee_id:
            return
        self._bridge.notify_issue_assigned_in_tx(
            project_id=project_id,
            issue_id=issue_id,
            title=title,
            project_name=self._project_name(project_id),
            assignee_id=assignee_id,
            actor_id=actor_id,
            version=version,
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
        _ = (
            project_id,
            issue_id,
            title,
            reporter_id,
            assignee_id,
            actor_id,
            when,
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
        severity: str = "MEDIA",
    ) -> None:
        _ = (task_id, task_name, when)
        self._bridge.notify_issue_reported_in_tx(
            project_id=project_id,
            issue_id=issue_id,
            title=title,
            project_name=self._project_name(project_id),
            severity=severity,
            actor_id=reporter_id,
        )


class SqlAlchemyAiQuotaLookup:
    """Manages per-user and global daily vision AI limits (Anexo F)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def check_user_limit(self, user_id: str) -> bool:
        today = _clock.now().date()
        user_limit = self._get_config_int("ai_user_daily_limit", default=20)
        global_limit = self._get_config_int("ai_vision_daily_limit", default=200)

        # Check user count
        user_row = self._session.get(
            AiDailyUsageModel, {"service": f"vision_user_{user_id}", "usage_date": today}
        )
        user_count = user_row.count if user_row else 0
        if user_count >= user_limit:
            return False

        # Check global vision count
        global_row = self._session.get(
            AiDailyUsageModel, {"service": "vision_global", "usage_date": today}
        )
        global_count = global_row.count if global_row else 0
        return global_count < global_limit

    def consume_quota(self, user_id: str) -> None:
        today = _clock.now().date()

        # Increment user count
        user_service = f"vision_user_{user_id}"
        user_row = self._session.get(
            AiDailyUsageModel, {"service": user_service, "usage_date": today}
        )
        if user_row is None:
            self._session.add(AiDailyUsageModel(service=user_service, usage_date=today, count=1))
        else:
            user_row.count += 1

        # Increment global vision count
        global_row = self._session.get(
            AiDailyUsageModel, {"service": "vision_global", "usage_date": today}
        )
        if global_row is None:
            self._session.add(AiDailyUsageModel(service="vision_global", usage_date=today, count=1))
        else:
            global_row.count += 1

        self._session.flush()

    def _get_config_int(self, key: str, default: int) -> int:
        row = self._session.get(SystemConfigModel, key)
        if row is None:
            return default
        try:
            return int(row.value)
        except ValueError:
            return default


class SqlAlchemyAuditLogRecorder:
    """Records audit trail events for AI response deletions (RNF-SEG-07)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        created_at: datetime,
    ) -> None:
        self._session.add(
            AuditLogModel(
                id=_id_gen.generate(),
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                created_at=created_at,
            )
        )
        self._session.flush()
