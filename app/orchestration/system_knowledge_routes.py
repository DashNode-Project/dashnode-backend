"""CRUD for the system knowledge base (FIX-01)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.system_knowledge.infrastructure.models import SystemKnowledgeEntryModel
from app.orchestration.security import get_current_user, require_admin_or_manager
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import get_db_session
from app.shared.infrastructure.id_generator import UuidGenerator

router = APIRouter(prefix="/knowledge/system", tags=["system-knowledge"])
_id_gen = UuidGenerator()
_clock = SystemClock()


class KnowledgeEntryDTO(BaseModel):
    id: str
    question: str
    answer_md: str
    tags: str
    updated_at: datetime


class KnowledgeUpsertCommand(BaseModel):
    question: str = Field(max_length=500)
    answer_md: str = Field(max_length=50000)
    tags: str = Field(default="", max_length=500)


class KnowledgeSearchResponse(BaseModel):
    items: list[KnowledgeEntryDTO]


def _to_dto(model: SystemKnowledgeEntryModel) -> KnowledgeEntryDTO:
    return KnowledgeEntryDTO(
        id=model.id,
        question=model.question,
        answer_md=model.answer_md,
        tags=model.tags,
        updated_at=model.updated_at,
    )


@router.get("", response_model=KnowledgeSearchResponse)
def search_system_knowledge(
    q: str = Query(default="", max_length=200),
    db: Session = Depends(get_db_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> KnowledgeSearchResponse:
    _ = current_user
    stmt = select(SystemKnowledgeEntryModel).where(
        SystemKnowledgeEntryModel.is_deleted.is_(False),
        SystemKnowledgeEntryModel.is_published.is_(True),
    )
    term = q.strip().lower()
    if term:
        pattern = f"%{term}%"
        stmt = stmt.where(
            or_(
                SystemKnowledgeEntryModel.question.ilike(pattern),
                SystemKnowledgeEntryModel.answer_md.ilike(pattern),
                SystemKnowledgeEntryModel.tags.ilike(pattern),
            )
        )
    rows = db.scalars(stmt.order_by(SystemKnowledgeEntryModel.updated_at.desc()).limit(50)).all()
    return KnowledgeSearchResponse(items=[_to_dto(row) for row in rows])


@router.post("", response_model=KnowledgeEntryDTO)
def create_system_knowledge(
    cmd: KnowledgeUpsertCommand,
    db: Session = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_admin_or_manager),
) -> KnowledgeEntryDTO:
    now = _clock.now()
    entry = SystemKnowledgeEntryModel(
        id=_id_gen.generate(),
        question=cmd.question.strip(),
        answer_md=cmd.answer_md.strip(),
        tags=cmd.tags.strip(),
        author_id=current_user.id,
        is_published=True,
        is_deleted=False,
        created_at=now,
        updated_at=now,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _to_dto(entry)


@router.put("/{entry_id}", response_model=KnowledgeEntryDTO)
def update_system_knowledge(
    entry_id: str,
    cmd: KnowledgeUpsertCommand,
    db: Session = Depends(get_db_session),
    current_user: CurrentUser = Depends(require_admin_or_manager),
) -> KnowledgeEntryDTO:
    entry = db.get(SystemKnowledgeEntryModel, entry_id)
    if entry is None or entry.is_deleted:
        from app.shared.domain.errors import AppError, ErrorKind

        raise AppError("NOT_FOUND", "Entrada no encontrada.", ErrorKind.NOT_FOUND)
    entry.question = cmd.question.strip()
    entry.answer_md = cmd.answer_md.strip()
    entry.tags = cmd.tags.strip()
    entry.author_id = current_user.id
    entry.updated_at = _clock.now()
    db.commit()
    db.refresh(entry)
    return _to_dto(entry)
