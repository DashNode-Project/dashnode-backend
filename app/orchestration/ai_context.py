"""RBAC-filtered project context for the AI assistant (HU 96)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ai.domain.ports import ProjectAiContext
from app.modules.documentation.domain.entities import DocumentationApprovalStatus
from app.modules.documentation.infrastructure.models import DocumentationEntryModel
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.projects.infrastructure.repositories import SqlAlchemyProjectRepository
from app.modules.sprints.infrastructure.models import SprintModel
from app.orchestration.backlog_adapters import SqlAlchemyProjectLookup


class SqlAlchemyProjectContextBuilder:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._projects = SqlAlchemyProjectLookup(session)

    def build_context(
        self, project_id: str | None, user_id: str, user_role: str
    ) -> ProjectAiContext:
        if not project_id:
            return ProjectAiContext(
                None,
                None,
                None,
                (),
                workspace_summary=self._workspace_summary(user_id, user_role),
            )
        workspace = self._workspace_summary(user_id, user_role)
        if user_role != "admin" and not self._projects.is_member(project_id, user_id):
            return ProjectAiContext(None, None, None, (), workspace_summary=workspace)

        project = self._session.get(ProjectModel, project_id)
        if project is None:
            return ProjectAiContext(None, None, None, (), workspace_summary=workspace)

        sprint = self._session.scalar(
            select(SprintModel)
            .where(SprintModel.project_id == project_id, SprintModel.status == "ACTIVE")
            .limit(1)
        )
        docs = self._session.scalars(
            select(DocumentationEntryModel).where(
                DocumentationEntryModel.project_id == project_id,
                DocumentationEntryModel.is_deleted.is_(False),
                DocumentationEntryModel.approval_status
                == DocumentationApprovalStatus.APPROVED.value,
            )
        ).all()
        snippets: list[str] = []
        for doc in docs:
            if user_role == "developer" and not doc.is_visible_to_devs and doc.author_id != user_id:
                continue
            fragment = doc.content or doc.objective or doc.title
            if fragment:
                snippets.append(f"{doc.title}: {fragment[:240]}")

        return ProjectAiContext(
            project_name=project.name,
            project_description=project.description or None,
            active_sprint_name=sprint.name if sprint else None,
            approved_doc_snippets=tuple(snippets[:8]),
            workspace_summary=self._workspace_summary(user_id, user_role),
        )

    def _workspace_summary(self, user_id: str, user_role: str) -> str:
        repo = SqlAlchemyProjectRepository(self._session)
        projects = repo.list_visible_for_user(user_id, role=user_role)
        if not projects:
            return "El usuario no tiene proyectos visibles en DashNode."
        preview = ", ".join(project.name for project in projects[:15])
        extra = len(projects) - 15
        suffix = f" (y {extra} más)" if extra > 0 else ""
        return f"Proyectos accesibles para el usuario: {len(projects)}. Nombres: {preview}{suffix}."
