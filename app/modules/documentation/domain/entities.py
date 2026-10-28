"""Domain entities for Documentation and Knowledge Base (EP-09)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class DocumentationCategory(StrEnum):
    TECNICA = "Técnica"
    FUNCIONAL = "Funcional"
    REUNION = "Reunión"
    GENERAL = "General"
    PROMPT = "Prompt"


class DocumentationApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class DocumentationEntry:
    id: str
    project_id: str
    author_id: str
    title: str
    category: DocumentationCategory
    objective: str | None
    tags: str | None
    content: str | None
    external_url: str | None
    approval_status: DocumentationApprovalStatus
    is_pinned: bool
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    def can_view(self, user_id: str, user_role: str) -> bool:
        if self.is_deleted:
            return False
        if str(user_role).lower() in ("admin", "manager", "administrador", "gerente"):
            return True
        if self.author_id == user_id:
            return True
        return self.approval_status == DocumentationApprovalStatus.APPROVED

    def can_edit(self, user_id: str, user_role: str) -> bool:
        if self.is_deleted:
            return False
        if str(user_role).lower() in ("admin", "manager", "administrador", "gerente"):
            return True
        return self.author_id == user_id and self.approval_status in (
            DocumentationApprovalStatus.PENDING,
            DocumentationApprovalStatus.REJECTED,
        )

    def can_delete(self, user_role: str) -> bool:
        if self.is_deleted:
            return False
        return str(user_role).lower() in ("admin", "manager", "administrador", "gerente")
