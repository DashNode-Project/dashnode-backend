"""Ports for external AI services and quota tracking (EP-10)."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.modules.ai.application.assistant.data_models import ProjectRow


@dataclass(frozen=True)
class ProjectAiContext:
    project_name: str | None
    project_description: str | None
    active_sprint_name: str | None
    approved_doc_snippets: tuple[str, ...]
    workspace_summary: str | None = None
    project_metrics_summary: str | None = None


class TranscriptionPort(Protocol):
    def transcribe(self, audio_bytes: bytes, content_type: str) -> str: ...


class GenerationPort(Protocol):
    def generate(self, prompt: str) -> str: ...


class QuotaPort(Protocol):
    def check_and_consume(self, service: str) -> None: ...


class ProjectContextPort(Protocol):
    def build_context(
        self, project_id: str | None, user_id: str, user_role: str
    ) -> ProjectAiContext: ...


class AssistantDataPort(Protocol):
    """Read-only project data for the hybrid assistant (implemented in orchestration)."""

    def accessible_projects(self, user_id: str, role: str) -> list["ProjectRow"]: ...

    def ensure_project_access(self, project_id: str, user_id: str, role: str) -> object: ...

    def list_members(self, project_id: str, user_id: str, role: str) -> list[str]: ...

    def list_sprints(self, project_id: str, user_id: str, role: str) -> list[str]: ...

    def list_stories(
        self,
        project_id: str,
        user_id: str,
        role: str,
        *,
        sprint_id: str | None = None,
    ) -> list[str]: ...

    def list_tasks(
        self,
        project_id: str,
        user_id: str,
        role: str,
        *,
        task_filter: str,
    ) -> list[str]: ...

    def list_documentation(self, project_id: str, user_id: str, role: str) -> list[str]: ...

    def sprint_candidates(self, project_id: str) -> list[tuple[str, str]]: ...

    def project_name(self, project_id: str) -> str: ...

    def count_metrics(self, project_id: str) -> tuple[int, int, int]: ...
