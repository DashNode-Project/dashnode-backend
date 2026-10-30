"""Aggregate RBAC-safe project metrics for the AI assistant context."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.backlog.infrastructure.models import StoryTaskModel, UserStoryModel
from app.modules.projects.infrastructure.models import ProjectMemberModel
from app.modules.sprints.infrastructure.models import SprintModel


def metrics_line(session: Session, project_id: str) -> str:
    hu_count = session.scalar(
        select(func.count())
        .select_from(UserStoryModel)
        .where(UserStoryModel.project_id == project_id)
    )
    task_count = session.scalar(
        select(func.count())
        .select_from(StoryTaskModel)
        .where(StoryTaskModel.project_id == project_id)
    )
    member_count = session.scalar(
        select(func.count())
        .select_from(ProjectMemberModel)
        .where(ProjectMemberModel.project_id == project_id)
    )
    return (
        f"{hu_count or 0} HUs, {task_count or 0} tareas, {member_count or 0} miembros"
    )


def project_metrics_summary(session: Session, project_id: str) -> str:
    lines: list[str] = []
    lines.append(f"Resumen numérico: {metrics_line(session, project_id)}.")

    sprints = session.scalars(
        select(SprintModel)
        .where(SprintModel.project_id == project_id)
        .order_by(SprintModel.start_date.desc())
        .limit(6)
    ).all()
    if sprints:
        lines.append("Sprints (nombre, estado, inicio, fin):")
        for sprint in sprints:
            lines.append(
                f"- {sprint.name} [{sprint.status}]: {sprint.start_date.isoformat()} "
                f"a {sprint.end_date.isoformat()}"
            )

    stories = session.scalars(
        select(UserStoryModel)
        .where(UserStoryModel.project_id == project_id)
        .order_by(UserStoryModel.created_at.asc())
        .limit(40)
    ).all()
    if stories:
        lines.append(f"Historias de usuario ({len(stories)} listadas, orden cronológico):")
        sprint_names = _sprint_name_map(session, {s.sprint_id for s in stories if s.sprint_id})
        for story in stories:
            if story.sprint_id:
                sprint_label = sprint_names.get(story.sprint_id, "sin sprint")
            else:
                sprint_label = "sin sprint"
            created = story.created_at.date().isoformat()
            title = story.title.strip() or story.label or "Sin título"
            lines.append(f"- {title} (creada {created}, sprint: {sprint_label})")
    else:
        lines.append("Historias de usuario: 0 registradas.")

    tasks = session.execute(
        select(StoryTaskModel.status, func.count())
        .where(StoryTaskModel.project_id == project_id)
        .group_by(StoryTaskModel.status)
    ).all()
    if tasks:
        breakdown = ", ".join(f"{status}={count}" for status, count in tasks)
        lines.append(f"Tareas por estado: {breakdown}.")

    return "\n".join(lines)


def _sprint_name_map(session: Session, sprint_ids: set[str | None]) -> dict[str | None, str]:
    ids = [sid for sid in sprint_ids if sid]
    if not ids:
        return {}
    rows = session.scalars(select(SprintModel).where(SprintModel.id.in_(ids))).all()
    return {row.id: row.name for row in rows}
