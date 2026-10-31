"""Cross-module adapter: pending task count for a user (HU_DN_01_19, BR-4)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.domain.ports import PendingAssignmentsQuery
from app.modules.tasks.infrastructure.models import TaskModel


class SqlAlchemyPendingAssignmentsQuery(PendingAssignmentsQuery):
    def __init__(self, session: Session) -> None:
        self._session = session

    def count_pending_for_user(self, user_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(TaskModel)
            .where(
                TaskModel.assignee_id == user_id,
                TaskModel.status != "completed",
            )
        )
        return int(self._session.execute(stmt).scalar_one())
