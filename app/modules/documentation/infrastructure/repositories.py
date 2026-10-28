"""SQLAlchemy repository implementation for Documentation and Knowledge Base (EP-09)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.documentation.domain.entities import (
    DocumentationApprovalStatus,
    DocumentationCategory,
    DocumentationEntry,
)
from app.modules.documentation.domain.ports import DocumentationRepository
from app.modules.documentation.infrastructure.models import DocumentationEntryModel


class SqlAlchemyDocumentationRepository(DocumentationRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_domain(self, model: DocumentationEntryModel) -> DocumentationEntry:
        return DocumentationEntry(
            id=model.id,
            project_id=model.project_id,
            author_id=model.author_id,
            title=model.title,
            category=DocumentationCategory(model.category),
            objective=model.objective,
            tags=model.tags,
            content=model.content,
            external_url=model.external_url,
            approval_status=DocumentationApprovalStatus(model.approval_status),
            is_pinned=model.is_pinned,
            is_deleted=model.is_deleted,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def save(self, entry: DocumentationEntry) -> None:
        model = self._session.get(DocumentationEntryModel, entry.id)
        cat_val = entry.category.value if hasattr(entry.category, "value") else str(entry.category)
        status_val = (
            entry.approval_status.value
            if hasattr(entry.approval_status, "value")
            else str(entry.approval_status)
        )

        if model is None:
            model = DocumentationEntryModel(
                id=entry.id,
                project_id=entry.project_id,
                author_id=entry.author_id,
                title=entry.title,
                category=cat_val,
                objective=entry.objective,
                tags=entry.tags,
                content=entry.content,
                external_url=entry.external_url,
                approval_status=status_val,
                is_pinned=entry.is_pinned,
                is_deleted=entry.is_deleted,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
            )
            self._session.add(model)
        else:
            model.title = entry.title
            model.category = cat_val
            model.objective = entry.objective
            model.tags = entry.tags
            model.content = entry.content
            model.external_url = entry.external_url
            model.approval_status = status_val
            model.is_pinned = entry.is_pinned
            model.is_deleted = entry.is_deleted
            model.updated_at = entry.updated_at

    def get_by_id(self, entry_id: str) -> DocumentationEntry | None:
        model = self._session.get(DocumentationEntryModel, entry_id)
        if model is None:
            return None
        return self._to_domain(model)

    def list_by_project(self, project_id: str) -> list[DocumentationEntry]:
        stmt = (
            select(DocumentationEntryModel)
            .where(
                DocumentationEntryModel.project_id == project_id,
                DocumentationEntryModel.is_deleted.is_(False),
            )
            .order_by(
                DocumentationEntryModel.is_pinned.desc(),
                DocumentationEntryModel.created_at.desc(),
            )
        )
        return [self._to_domain(row) for row in self._session.scalars(stmt).all()]
