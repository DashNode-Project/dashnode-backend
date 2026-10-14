"""Cancels scheduled meetings when a project is soft-deleted (BR-4 adapter)."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.availability.infrastructure.repositories import SqlAlchemyAvailabilityRepository
from app.modules.projects.domain.ports import ProjectDeletionCollaborator


class MeetingCleanupOnProjectDelete(ProjectDeletionCollaborator):
    def __init__(self, session: Session) -> None:
        self._availability = SqlAlchemyAvailabilityRepository(session=session)

    def after_project_soft_deleted(self, project_id: str, when: datetime) -> None:
        self._availability.cancel_scheduled_meetings_for_project(project_id, when)
