"""Kanban domain ports (EP-08)."""

from datetime import datetime
from typing import Protocol


class KanbanRepository(Protocol):
    def get_wip_limits(self, project_id: str) -> dict[str, int | None]: ...

    def set_wip_limit(
        self,
        new_id: str,
        project_id: str,
        column_id: str,
        wip_limit: int | None,
        when: datetime,
    ) -> None: ...
