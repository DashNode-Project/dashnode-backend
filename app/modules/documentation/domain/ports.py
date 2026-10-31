from datetime import datetime
from typing import Protocol

from app.modules.documentation.domain.entities import DocumentationEntry


class DocumentationRepository(Protocol):
    def save(self, entry: DocumentationEntry) -> None: ...
    def get_by_id(self, entry_id: str) -> DocumentationEntry | None: ...
    def list_by_project(self, project_id: str) -> list[DocumentationEntry]: ...
    def list_pending_by_project(self, project_id: str) -> list[DocumentationEntry]: ...
    def log_audit(
        self,
        *,
        audit_id: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        when: datetime,
    ) -> None: ...
