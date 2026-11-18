"""Orchestration adapters for meetings module satisfying BR-4."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.infrastructure.models import UserModel
from app.modules.availability.domain.entities import Meeting
from app.modules.availability.domain.ports import (
    NotificationSender,
    ProjectBasicInfo,
    ProjectLookup,
    UserBasicInfo,
    UserLookup,
)
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.orchestration.notification_adapters import SqlAlchemyDomainNotificationBridge
from app.shared.application.ports import Clock, IdGenerator


class SqlAlchemyProjectLookup(ProjectLookup):
    """Resolves project details and membership for availability and meetings."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_project(self, project_id: str) -> ProjectBasicInfo | None:
        p = self._session.scalar(
            select(ProjectModel).where(
                ProjectModel.id == project_id,
                ProjectModel.deleted_at.is_(None),
            )
        )
        if p is None:
            return None
        member_ids = self._session.scalars(
            select(ProjectMemberModel.user_id).where(ProjectMemberModel.project_id == project_id)
        ).all()
        return ProjectBasicInfo(
            id=p.id,
            name=p.name,
            manager_id=p.manager_id,
            meeting_link=p.meeting_link,
            member_ids=list(member_ids),
        )

    def get_managed_project_ids(self, manager_id: str) -> list[str]:
        pids = self._session.scalars(
            select(ProjectModel.id).where(
                ProjectModel.manager_id == manager_id,
                ProjectModel.deleted_at.is_(None),
            )
        ).all()
        return list(pids)

    def is_user_project_member(self, project_id: str, user_id: str) -> bool:
        exists = self._session.scalar(
            select(ProjectMemberModel.user_id).where(
                ProjectMemberModel.project_id == project_id,
                ProjectMemberModel.user_id == user_id,
            )
        )
        return exists is not None

    def list_managed_projects(self, user_id: str, role: str) -> list[ProjectBasicInfo]:
        query = select(ProjectModel).where(ProjectModel.deleted_at.is_(None))
        if role != "admin":
            query = query.where(ProjectModel.manager_id == user_id)
        query = query.order_by(ProjectModel.name.asc())

        projects = self._session.scalars(query).all()
        result: list[ProjectBasicInfo] = []
        for p in projects:
            member_ids = self._session.scalars(
                select(ProjectMemberModel.user_id).where(ProjectMemberModel.project_id == p.id)
            ).all()
            result.append(
                ProjectBasicInfo(
                    id=p.id,
                    name=p.name,
                    manager_id=p.manager_id,
                    meeting_link=p.meeting_link,
                    member_ids=list(member_ids),
                )
            )
        return result


class SqlAlchemyUserLookup(UserLookup):
    """Resolves basic user details for meeting participants and creators."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_users_info(self, user_ids: list[str]) -> dict[str, UserBasicInfo]:
        if not user_ids:
            return {}
        users = self._session.scalars(select(UserModel).where(UserModel.id.in_(user_ids))).all()
        return {
            u.id: UserBasicInfo(id=u.id, name=u.name, email=u.email, role=u.role) for u in users
        }


class SqlAlchemyMeetingNotificationSender(NotificationSender):
    """Sends notifications to meeting participants."""

    def __init__(self, session: Session, id_gen: IdGenerator, clock: Clock) -> None:
        self._session = session
        self._clock = clock
        self._bridge = SqlAlchemyDomainNotificationBridge(session)

    def _when_label(self, meeting: Meeting) -> str:
        return f"{meeting.date} {meeting.start_time}-{meeting.end_time}"

    def notify_meeting_scheduled(self, meeting: Meeting, participant_ids: list[str]) -> None:
        if not meeting.project_id:
            return
        self._bridge.notify_meeting_scheduled_in_tx(
            project_id=meeting.project_id,
            meeting_id=meeting.id,
            meeting_title=meeting.title,
            when_label=self._when_label(meeting),
            participant_ids=participant_ids,
            actor_id=meeting.creator_id,
        )

    def notify_meeting_cancelled(self, meeting: Meeting, participant_ids: list[str]) -> None:
        if not meeting.project_id:
            return
        self._bridge.notify_meeting_cancelled_in_tx(
            project_id=meeting.project_id,
            meeting_id=meeting.id,
            meeting_title=meeting.title,
            when_label=self._when_label(meeting),
            participant_ids=participant_ids,
            actor_id=None,
        )
