"""DevOps practices repository port."""

from __future__ import annotations

from typing import Protocol

from app.modules.devops.domain.entities import DevOpsRevision, ProjectDevOpsProfile


class DevOpsProfileRepository(Protocol):
    def get_by_project_id(self, project_id: str) -> ProjectDevOpsProfile | None: ...

    def save(self, profile: ProjectDevOpsProfile) -> None: ...

    def add_revision(self, revision: DevOpsRevision) -> None: ...

    def list_revisions(
        self,
        project_id: str,
        *,
        limit: int,
        offset: int,
    ) -> list[DevOpsRevision]: ...
