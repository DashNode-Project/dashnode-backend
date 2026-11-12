"""Kanban repository implementation (EP-08)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.kanban.infrastructure.models import KanbanColumnSettingsModel


class SqlAlchemyKanbanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_wip_limits(self, project_id: str) -> dict[str, int | None]:
        stmt = select(KanbanColumnSettingsModel).where(
            KanbanColumnSettingsModel.project_id == project_id
        )
        rows = self._session.scalars(stmt).all()
        return {row.column_id: row.wip_limit for row in rows}

    def set_wip_limit(
        self,
        new_id: str,
        project_id: str,
        column_id: str,
        wip_limit: int | None,
        when: datetime,
    ) -> None:
        stmt = select(KanbanColumnSettingsModel).where(
            KanbanColumnSettingsModel.project_id == project_id,
            KanbanColumnSettingsModel.column_id == column_id,
        )
        row = self._session.scalars(stmt).first()
        if row is not None:
            row.wip_limit = wip_limit
            row.updated_at = when
        else:
            new_row = KanbanColumnSettingsModel(
                id=new_id,
                project_id=project_id,
                column_id=column_id,
                wip_limit=wip_limit,
                updated_at=when,
            )
            self._session.add(new_row)
