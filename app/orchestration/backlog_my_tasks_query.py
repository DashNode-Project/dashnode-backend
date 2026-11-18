"""Cross-module read model for GET /users/me/tasks (BR-4)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.backlog.application.dtos import MyTaskItemDTO
from app.modules.backlog.infrastructure.models import EpicModel, StoryTaskModel, UserStoryModel
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.sprints.infrastructure.models import SprintModel


class SqlAlchemyMyTasksQuery:
    """Single joined query for assignee task list."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_assignee(
        self,
        assignee_id: str,
        *,
        project_id: str | None = None,
        status_filter: str | None = None,
    ) -> list[MyTaskItemDTO]:
        stmt = (
            select(
                StoryTaskModel,
                ProjectModel,
                UserStoryModel,
                EpicModel,
                SprintModel,
            )
            .join(UserStoryModel, UserStoryModel.id == StoryTaskModel.user_story_id)
            .join(ProjectModel, ProjectModel.id == StoryTaskModel.project_id)
            .join(EpicModel, EpicModel.id == UserStoryModel.epic_id)
            .outerjoin(SprintModel, SprintModel.id == UserStoryModel.sprint_id)
            .where(StoryTaskModel.assignee_id == assignee_id)
            .order_by(StoryTaskModel.updated_at.desc())
        )
        if project_id:
            stmt = stmt.where(StoryTaskModel.project_id == project_id)
        if status_filter:
            stmt = stmt.where(StoryTaskModel.status == status_filter)
        rows = self._session.execute(stmt).all()
        items: list[MyTaskItemDTO] = []
        for task, project, story, epic, sprint in rows:
            sprint_payload = {"id": sprint.id, "name": sprint.name} if sprint is not None else None
            items.append(
                MyTaskItemDTO(
                    id=task.id,
                    name=task.name,
                    project={"id": project.id, "name": project.name},
                    user_story={"id": story.id, "title": story.title},
                    status=task.status,
                    estimated_hours=task.estimated_hours,
                    logged_hours=task.logged_hours,
                    epic={"id": epic.id, "name": epic.name},
                    sprint=sprint_payload,
                )
            )
        return items
