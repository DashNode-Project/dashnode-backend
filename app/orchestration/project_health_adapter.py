"""Cross-module project health metrics (BR-4)."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.backlog.domain.entities import StoryTaskStatus
from app.modules.backlog.infrastructure.repositories import SqlAlchemyBacklogRepository
from app.modules.fixes.domain.entities import IssueStatus
from app.modules.fixes.infrastructure.models import FixModel
from app.modules.projects.domain.health import ProjectHealthSnapshot
from app.modules.sprints.application.metrics import (
    compute_sprint_points,
    story_effective_points,
    story_is_completed,
)
from app.modules.sprints.domain.entities import SprintStatus
from app.modules.sprints.infrastructure.models import SprintModel


class SqlAlchemyProjectHealthSnapshotProvider:
    """Aggregates backlog and sprint data for project summary health indicators."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_health_snapshot(self, project_id: str) -> ProjectHealthSnapshot:
        backlog = SqlAlchemyBacklogRepository(self._session)
        stories = backlog.list_stories_by_project(project_id)
        tasks = backlog.list_tasks_by_project(project_id)

        active_sprint_id = self._session.scalar(
            select(SprintModel.id)
            .where(
                SprintModel.project_id == project_id,
                SprintModel.status == SprintStatus.ACTIVE.value,
            )
            .limit(1)
        )

        total = 0
        completed = 0
        for story in stories:
            pts = story_effective_points(story, tasks)
            total += pts
            if story_is_completed(story, tasks):
                completed += pts

        closed = self._session.scalars(
            select(SprintModel)
            .where(
                SprintModel.project_id == project_id,
                SprintModel.status == SprintStatus.CLOSED.value,
            )
            .order_by(SprintModel.closed_at.desc().nullslast(), SprintModel.end_date.desc())
            .limit(3)
        ).all()
        velocity_samples: list[float] = []
        for sprint in closed:
            _, sprint_completed, _ = compute_sprint_points(stories, tasks, sprint.id)
            velocity_samples.append(float(sprint_completed))
        if velocity_samples:
            velocity = sum(velocity_samples) / len(velocity_samples)
        elif active_sprint_id:
            _, sprint_completed, _ = compute_sprint_points(stories, tasks, active_sprint_id)
            velocity = float(sprint_completed)
        else:
            velocity = 0.0

        open_issues = int(
            self._session.scalar(
                select(func.count())
                .select_from(FixModel)
                .where(
                    FixModel.project_id == project_id,
                    FixModel.status == IssueStatus.OPEN.value,
                )
            )
            or 0
        )

        user_stories_completed = sum(1 for story in stories if story_is_completed(story, tasks))
        tasks_completed = sum(1 for task in tasks if task.status == StoryTaskStatus.DONE)

        return ProjectHealthSnapshot(
            completed_story_points=completed,
            total_story_points=total,
            velocity_points_per_sprint=velocity,
            open_issues=open_issues,
            user_stories_count=len(stories),
            user_stories_completed_count=user_stories_completed,
            tasks_count=len(tasks),
            tasks_completed_count=tasks_completed,
        )
