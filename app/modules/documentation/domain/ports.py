"""Domain repository port for Documentation and Knowledge Base (EP-09)."""

from typing import Protocol

from app.modules.documentation.domain.entities import DocumentationEntry


class DocumentationRepository(Protocol):
    def save(self, entry: DocumentationEntry) -> None: ...
    def get_by_id(self, entry_id: str) -> DocumentationEntry | None: ...
    def list_by_project(self, project_id: str) -> list[DocumentationEntry]: ...
