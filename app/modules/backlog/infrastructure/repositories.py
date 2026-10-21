"""SQLAlchemy backlog repository."""

from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.backlog.domain.entities import (
    Epic,
    MoscowPriority,
    StoryTask,
    StoryTaskStatus,
    StoryTaskType,
    UserStory,
    parse_story_task_status,
)
from app.modules.backlog.domain.ports import BacklogRepository
from app.modules.backlog.infrastructure.models import (
    EpicModel,
    StoryTaskModel,
    TaskStatusHistoryModel,
    TaskTimeLogModel,
    UserStoryModel,
)


class SqlAlchemyBacklogRepository(BacklogRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _epic_to_domain(model: EpicModel) -> Epic:
        return Epic(
            id=model.id,
            project_id=model.project_id,
            name=model.name,
            description=model.description,
            color=model.color,
            sort_order=model.sort_order,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _story_to_domain(model: UserStoryModel) -> UserStory:
        return UserStory(
            id=model.id,
            epic_id=model.epic_id,
            project_id=model.project_id,
            title=model.title,
            user_role=model.user_role,
            reason=model.reason,
            acceptance_criteria=model.acceptance_criteria,
            moscow_priority=MoscowPriority(model.moscow_priority),
            story_points=model.story_points,
            sprint_id=model.sprint_id,
            sort_order=model.sort_order,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
            label=model.label or "",
        )

    @staticmethod
    def _task_to_domain(model: StoryTaskModel) -> StoryTask:
        hours = model.estimated_hours
        parsed = parse_story_task_status(model.status) or StoryTaskStatus.TODO
        logged = model.logged_hours if model.logged_hours is not None else Decimal("0")
        return StoryTask(
            id=model.id,
            user_story_id=model.user_story_id,
            project_id=model.project_id,
            name=model.name,
            task_type=StoryTaskType(model.task_type),
            notes=model.notes,
            status=parsed,
            assignee_id=model.assignee_id,
            estimated_hours=Decimal(hours) if hours is not None else None,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
            logged_hours=Decimal(logged),
            label=model.label or "",
        )

    def save_epic(self, epic: Epic) -> None:
        self._session.add(
            EpicModel(
                id=epic.id,
                project_id=epic.project_id,
                name=epic.name,
                description=epic.description,
                color=epic.color,
                sort_order=epic.sort_order,
                created_by=epic.created_by,
                created_at=epic.created_at,
                updated_at=epic.updated_at,
            )
        )

    def update_epic(self, epic: Epic) -> None:
        model = self._session.get(EpicModel, epic.id)
        if model is None:
            return
        model.name = epic.name
        model.description = epic.description
        model.color = epic.color
        model.sort_order = epic.sort_order
        model.updated_at = epic.updated_at

    def get_epic(self, epic_id: str) -> Epic | None:
        model = self._session.get(EpicModel, epic_id)
        return self._epic_to_domain(model) if model else None

    def list_epics_by_project(self, project_id: str) -> list[Epic]:
        stmt = (
            select(EpicModel)
            .where(EpicModel.project_id == project_id)
            .order_by(EpicModel.sort_order.asc(), EpicModel.created_at.asc())
        )
        return [self._epic_to_domain(row) for row in self._session.scalars(stmt).all()]

    def next_epic_sort_order(self, project_id: str) -> int:
        stmt = select(func.coalesce(func.max(EpicModel.sort_order), -1)).where(
            EpicModel.project_id == project_id
        )
        current = self._session.scalar(stmt)
        return int(current or -1) + 1

    def save_user_story(self, story: UserStory) -> None:
        self._session.add(
            UserStoryModel(
                id=story.id,
                epic_id=story.epic_id,
                project_id=story.project_id,
                title=story.title,
                user_role=story.user_role,
                reason=story.reason,
                acceptance_criteria=story.acceptance_criteria,
                moscow_priority=story.moscow_priority.value,
                story_points=story.story_points,
                sprint_id=story.sprint_id,
                sort_order=story.sort_order,
                created_by=story.created_by,
                created_at=story.created_at,
                updated_at=story.updated_at,
            )
        )

    def update_user_story(self, story: UserStory) -> None:
        model = self._session.get(UserStoryModel, story.id)
        if model is None:
            return
        model.epic_id = story.epic_id
        model.title = story.title
        model.user_role = story.user_role
        model.reason = story.reason
        model.acceptance_criteria = story.acceptance_criteria
        model.moscow_priority = story.moscow_priority.value
        model.story_points = story.story_points
        model.updated_at = story.updated_at

    def get_user_story(self, story_id: str) -> UserStory | None:
        model = self._session.get(UserStoryModel, story_id)
        return self._story_to_domain(model) if model else None

    def list_stories_by_epic(self, epic_id: str) -> list[UserStory]:
        stmt = (
            select(UserStoryModel)
            .where(UserStoryModel.epic_id == epic_id)
            .order_by(UserStoryModel.sort_order.asc(), UserStoryModel.created_at.asc())
        )
        return [self._story_to_domain(row) for row in self._session.scalars(stmt).all()]

    def list_stories_by_project(self, project_id: str) -> list[UserStory]:
        stmt = (
            select(UserStoryModel)
            .where(UserStoryModel.project_id == project_id)
            .order_by(UserStoryModel.sort_order.asc())
        )
        return [self._story_to_domain(row) for row in self._session.scalars(stmt).all()]

    def next_story_sort_order(self, epic_id: str) -> int:
        stmt = select(func.coalesce(func.max(UserStoryModel.sort_order), -1)).where(
            UserStoryModel.epic_id == epic_id
        )
        current = self._session.scalar(stmt)
        return int(current or -1) + 1

    def save_story_task(self, task: StoryTask) -> None:
        self._session.add(
            StoryTaskModel(
                id=task.id,
                user_story_id=task.user_story_id,
                project_id=task.project_id,
                name=task.name,
                task_type=task.task_type.value,
                notes=task.notes,
                status=task.status.value,
                assignee_id=task.assignee_id,
                estimated_hours=task.estimated_hours,
                logged_hours=task.logged_hours,
                label=task.label,
                created_by=task.created_by,
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
        )

    def update_story_task(self, task: StoryTask) -> None:
        model = self._session.get(StoryTaskModel, task.id)
        if model is None:
            return
        model.name = task.name
        model.task_type = task.task_type.value
        model.notes = task.notes
        model.assignee_id = task.assignee_id
        model.estimated_hours = task.estimated_hours
        model.status = task.status.value
        model.logged_hours = task.logged_hours
        model.label = task.label
        model.updated_at = task.updated_at

    def delete_story_task(self, task_id: str) -> None:
        self._session.execute(delete(StoryTaskModel).where(StoryTaskModel.id == task_id))

    def get_story_task(self, task_id: str) -> StoryTask | None:
        model = self._session.get(StoryTaskModel, task_id)
        return self._task_to_domain(model) if model else None

    def list_tasks_by_story(self, user_story_id: str) -> list[StoryTask]:
        stmt = (
            select(StoryTaskModel)
            .where(StoryTaskModel.user_story_id == user_story_id)
            .order_by(StoryTaskModel.created_at.asc())
        )
        return [self._task_to_domain(row) for row in self._session.scalars(stmt).all()]

    def list_tasks_by_project(self, project_id: str) -> list[StoryTask]:
        stmt = select(StoryTaskModel).where(StoryTaskModel.project_id == project_id)
        return [self._task_to_domain(row) for row in self._session.scalars(stmt).all()]

    def list_tasks_for_assignee(self, assignee_id: str) -> list[StoryTask]:
        stmt = (
            select(StoryTaskModel)
            .where(StoryTaskModel.assignee_id == assignee_id)
            .order_by(StoryTaskModel.updated_at.desc())
        )
        return [self._task_to_domain(row) for row in self._session.scalars(stmt).all()]

    def add_time_log(
        self,
        *,
        log_id: str,
        task_id: str,
        user_id: str,
        hours: Decimal,
        comment: str | None,
        when,
    ) -> None:
        self._session.add(
            TaskTimeLogModel(
                id=log_id,
                task_id=task_id,
                user_id=user_id,
                hours_spent=hours,
                comment=comment,
                created_at=when,
            )
        )

    def add_status_history(
        self,
        *,
        history_id: str,
        task_id: str,
        user_id: str,
        previous_status: str,
        new_status: str,
        when,
    ) -> None:
        self._session.add(
            TaskStatusHistoryModel(
                id=history_id,
                task_id=task_id,
                user_id=user_id,
                previous_status=previous_status,
                new_status=new_status,
                changed_at=when,
            )
        )
