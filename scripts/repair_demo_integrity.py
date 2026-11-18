"""Normalize invalid project member roles and demo progress on the active database."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.backlog.domain.entities import StoryTaskStatus
from app.modules.backlog.infrastructure.models import StoryTaskModel, UserStoryModel
from app.modules.projects.infrastructure.models import ProjectMemberModel, ProjectModel
from app.modules.sprints.infrastructure.models import SprintModel
from app.shared.infrastructure import database as db_runtime
from app.shared.infrastructure.database import initialize_database

DEMO_NAMES = ("Helix Health Portal", "OrbitLogistics TMS")


def _repair_member_roles(db: Session) -> int:
    rows = db.scalars(
        select(ProjectMemberModel).where(ProjectMemberModel.role.notin_(["lead", "member"]))
    ).all()
    fixed = 0
    for row in rows:
        project = db.get(ProjectModel, row.project_id)
        if project and row.user_id == project.manager_id:
            row.role = "lead"
        else:
            row.role = "member"
        fixed += 1
    return fixed


def _repair_demo_progress(db: Session, project: ProjectModel) -> None:
    stories = list(
        db.scalars(
            select(UserStoryModel)
            .where(UserStoryModel.project_id == project.id)
            .order_by(UserStoryModel.sort_order.asc())
        ).all()
    )
    sprints = list(
        db.scalars(select(SprintModel).where(SprintModel.project_id == project.id)).all()
    )
    now = datetime.now(UTC)
    for sprint in sprints:
        if sprint.status == "CLOSED" and sprint.closed_at is None:
            sprint.closed_at = now
    for idx, story in enumerate(stories):
        tasks = list(
            db.scalars(select(StoryTaskModel).where(StoryTaskModel.user_story_id == story.id)).all()
        )
        if not tasks:
            continue
        if idx % 3 == 0:
            for t in tasks:
                t.status = StoryTaskStatus.DONE.value
        elif idx % 3 == 1:
            for j, t in enumerate(tasks):
                t.status = StoryTaskStatus.DONE.value if j % 2 == 0 else StoryTaskStatus.IN_PROGRESS.value
        else:
            for t in tasks:
                if t.status == StoryTaskStatus.TESTING.value:
                    t.status = StoryTaskStatus.IN_PROGRESS.value


def main() -> None:
    initialize_database()
    if db_runtime.SessionLocal is None:
        raise RuntimeError("SessionLocal not initialized")
    with db_runtime.SessionLocal() as db:
        roles = _repair_member_roles(db)
        projects = db.scalars(
            select(ProjectModel).where(ProjectModel.deleted_at.is_(None))
        ).all()
        for project in projects:
            _repair_demo_progress(db, project)
        db.commit()
        print(f"[repair] project member roles fixed: {roles}")
        print(f"[repair] projects recalibrated for metrics: {len(projects)}")


if __name__ == "__main__":
    main()