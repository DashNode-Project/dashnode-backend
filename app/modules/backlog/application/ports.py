"""Cross-module ports for backlog use cases (wired in orchestration)."""

from typing import Protocol

from app.modules.backlog.application.access import ProjectContext


class ProjectLookupPort(Protocol):
    def get_project(self, project_id: str) -> ProjectContext | None: ...

    def is_member(self, project_id: str, user_id: str) -> bool: ...


class ActiveMemberLookupPort(Protocol):
    def is_active_project_member(self, project_id: str, user_id: str) -> bool: ...
