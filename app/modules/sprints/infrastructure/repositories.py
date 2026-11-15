"""SQLAlchemy sprint repository."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.backlog.infrastructure.models import UserStoryModel
from app.modules.sprints.domain.entities import Sprint, SprintStatus
from app.modules.sprints.infrastructure.models import SprintModel


class SqlAlchemySprintRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(model: SprintModel) -> Sprint:
        return Sprint(
            id=model.id,
            project_id=model.project_id,
            name=model.name,
            goal=model.goal,
            start_date=model.start_date,
            end_date=model.end_date,
            status=SprintStatus(model.status),
            created_at=model.created_at,
            closed_at=model.closed_at,
        )

    def save(self, sprint: Sprint) -> None:
        self._session.add(
            SprintModel(
                id=sprint.id,
                project_id=sprint.project_id,
                name=sprint.name,
                goal=sprint.goal,
                start_date=sprint.start_date,
                end_date=sprint.end_date,
                status=sprint.status.value,
                created_at=sprint.created_at,
            )
        )

    def update(self, sprint: Sprint) -> None:
        model = self._session.get(SprintModel, sprint.id)
        if model is None:
            return
        model.name = sprint.name
        model.goal = sprint.goal
        model.start_date = sprint.start_date
        model.end_date = sprint.end_date
        model.status = sprint.status.value
        model.closed_at = sprint.closed_at

    def get_by_id(self, sprint_id: str) -> Sprint | None:
        model = self._session.get(SprintModel, sprint_id)
        return self._to_domain(model) if model else None

    def list_by_project(self, project_id: str) -> list[Sprint]:
        stmt = (
            select(SprintModel)
            .where(SprintModel.project_id == project_id)
            .order_by(SprintModel.start_date.desc())
        )
        return [self._to_domain(row) for row in self._session.scalars(stmt)]

    def get_active_for_project(self, project_id: str) -> Sprint | None:
        stmt = select(SprintModel).where(
            SprintModel.project_id == project_id,
            SprintModel.status == SprintStatus.ACTIVE.value,
        )
        model = self._session.scalars(stmt).first()
        return self._to_domain(model) if model else None

    def has_other_active_sprint(self, project_id: str, exclude_sprint_id: str) -> bool:
        stmt = (
            select(func.count())
            .select_from(SprintModel)
            .where(
                SprintModel.project_id == project_id,
                SprintModel.status == SprintStatus.ACTIVE.value,
                SprintModel.id != exclude_sprint_id,
            )
        )
        return int(self._session.scalar(stmt) or 0) > 0

    def count_stories(self, sprint_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(UserStoryModel)
            .where(UserStoryModel.sprint_id == sprint_id)
        )
        return int(self._session.scalar(stmt) or 0)

    def sum_story_points(self, sprint_id: str) -> int:
        _ = sprint_id
        return 0

    def set_status(self, sprint_id: str, status: SprintStatus) -> None:
        model = self._session.get(SprintModel, sprint_id)
        if model:
            model.status = status.value

    def list_closed_by_project(self, project_id: str) -> list[Sprint]:
        stmt = (
            select(SprintModel)
            .where(
                SprintModel.project_id == project_id,
                SprintModel.status == SprintStatus.CLOSED.value,
            )
            .order_by(SprintModel.end_date.desc())
        )
        return [self._to_domain(row) for row in self._session.scalars(stmt)]
