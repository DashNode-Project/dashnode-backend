"""Ports for external AI services and quota tracking (EP-10)."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProjectAiContext:
    project_name: str | None
    project_description: str | None
    active_sprint_name: str | None
    approved_doc_snippets: tuple[str, ...]
    workspace_summary: str | None = None


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
