"""EP-14 Notifications HTTP API (HU_DN_09_119 .. HU_DN_09_123)."""

from __future__ import annotations

import base64
import json
import time
from collections import defaultdict
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.modules.auth.infrastructure.models import UserModel
from app.modules.availability.infrastructure.models import MeetingModel
from app.modules.backlog.infrastructure.models import StoryTaskModel
from app.modules.documentation.infrastructure.models import DocumentationEntryModel
from app.modules.fixes.infrastructure.models import FixModel
from app.modules.notifications.application.catalog import (
    ALLOWED_ROUTE_PREFIXES,
    NotificationEventType,
    build_route,
)
from app.modules.notifications.infrastructure.models import NotificationModel
from app.modules.projects.infrastructure.models import ProjectModel
from app.modules.sprints.infrastructure.models import SprintModel
from app.orchestration.fixes_adapters import SqlAlchemyProjectLookup
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.domain.errors import AppError, ErrorKind
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork, get_db_session

router = APIRouter(prefix="/notifications", tags=["notifications"])
_clock = SystemClock()

_RATE_WINDOW_SECONDS = 60
_RATE_MAX_REQUESTS = 120
_rate_buckets: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(user_id: str) -> None:
    now = time.monotonic()
    bucket = _rate_buckets[user_id]
    bucket[:] = [t for t in bucket if now - t < _RATE_WINDOW_SECONDS]
    if len(bucket) >= _RATE_MAX_REQUESTS:
        raise AppError(
            "RATE_LIMITED",
            "Demasiadas solicitudes. Intente nuevamente en un momento.",
            ErrorKind.RATE_LIMITED,
        )
    bucket.append(now)


class NotificationActorDTO(BaseModel):
    id: str
    name: str


class NotificationProjectDTO(BaseModel):
    id: str
    name: str


class NotificationItemDTO(BaseModel):
    id: str
    type: str
    title: str
    message: str
    project: NotificationProjectDTO | None = None
    actor: NotificationActorDTO | None = None
    created_at: datetime
    read_at: datetime | None


class NotificationListResponse(BaseModel):
    items: list[NotificationItemDTO]
    next_cursor: str | None


class UnreadCountResponse(BaseModel):
    count: int


class MarkReadBody(BaseModel):
    ids: list[str] = Field(default_factory=list, max_length=100)


class MarkReadResponse(BaseModel):
    updated: int
    unread_count: int


class DeleteAllBody(BaseModel):
    confirm: bool = False


class DeleteAllResponse(BaseModel):
    deleted: int
    unread_count: int


class OpenNotificationResponse(BaseModel):
    route: str
    read_at: datetime


def _encode_cursor(created_at: datetime, notification_id: str) -> str:
    payload = {"t": created_at.isoformat(), "i": notification_id}
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        data = json.loads(raw)
        created = datetime.fromisoformat(str(data["t"]))
        return created, str(data["i"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AppError(
            "VALIDATION_ERROR",
            "Parámetros no válidos.",
            ErrorKind.VALIDATION,
            {"cursor": "Cursor no válido."},
        ) from exc


def _actor_dto(
    model: NotificationModel, users: dict[str, UserModel]
) -> NotificationActorDTO | None:
    if not model.actor_id:
        return None
    user = users.get(model.actor_id)
    if user is None:
        return NotificationActorDTO(id=model.actor_id, name="Usuario no disponible")
    name = (user.name or "").strip() or "Usuario no disponible"
    return NotificationActorDTO(id=user.id, name=name)


def _project_dto(
    model: NotificationModel, projects: dict[str, ProjectModel]
) -> NotificationProjectDTO | None:
    if not model.project_id:
        return None
    project = projects.get(model.project_id)
    if project is None:
        return NotificationProjectDTO(id=model.project_id, name="Proyecto")
    return NotificationProjectDTO(id=project.id, name=(project.name or "").strip() or "Proyecto")


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
    cursor: str | None = Query(None),
    unread_only: bool = Query(False),
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> NotificationListResponse:
    stmt = select(NotificationModel).where(NotificationModel.recipient_id == actor.id)
    if unread_only:
        stmt = stmt.where(NotificationModel.read_at.is_(None))
    if cursor:
        cursor_created, cursor_id = _decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                NotificationModel.created_at < cursor_created,
                and_(
                    NotificationModel.created_at == cursor_created,
                    NotificationModel.id < cursor_id,
                ),
            )
        )
    stmt = stmt.order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc()).limit(
        limit + 1
    )
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > limit
    page = rows[:limit]

    project_ids = {r.project_id for r in page if r.project_id}
    actor_ids = {r.actor_id for r in page if r.actor_id}
    projects = {}
    users = {}
    if project_ids:
        project_stmt = select(ProjectModel).where(ProjectModel.id.in_(project_ids))
        for project in db.scalars(project_stmt).all():
            projects[project.id] = project
    if actor_ids:
        for user in db.scalars(select(UserModel).where(UserModel.id.in_(actor_ids))).all():
            users[user.id] = user

    items = [
        NotificationItemDTO(
            id=row.id,
            type=row.type,
            title=row.title,
            message=row.message,
            project=_project_dto(row, projects),
            actor=_actor_dto(row, users),
            created_at=row.created_at,
            read_at=row.read_at,
        )
        for row in page
    ]
    next_cursor = _encode_cursor(page[-1].created_at, page[-1].id) if has_more and page else None
    return NotificationListResponse(items=items, next_cursor=next_cursor)


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(
    response: Response,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> UnreadCountResponse:
    _check_rate_limit(actor.id)
    response.headers["Cache-Control"] = "no-store"
    count = db.scalar(
        select(func.count())
        .select_from(NotificationModel)
        .where(
            NotificationModel.recipient_id == actor.id,
            NotificationModel.read_at.is_(None),
        )
    )
    return UnreadCountResponse(count=int(count or 0))


def _unread_count(db: Session, user_id: str) -> int:
    value = db.scalar(
        select(func.count())
        .select_from(NotificationModel)
        .where(NotificationModel.recipient_id == user_id, NotificationModel.read_at.is_(None))
    )
    return int(value or 0)


@router.post("/read", response_model=MarkReadResponse)
def mark_read(
    body: MarkReadBody,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> MarkReadResponse:
    if len(body.ids) > 100:
        raise AppError(
            "VALIDATION_ERROR",
            "Parámetros no válidos.",
            ErrorKind.VALIDATION,
            {"ids": "Máximo 100 elementos."},
        )
    if not body.ids:
        return MarkReadResponse(updated=0, unread_count=_unread_count(db, actor.id))
    now = _clock.now()
    stmt = (
        update(NotificationModel)
        .where(
            NotificationModel.recipient_id == actor.id,
            NotificationModel.id.in_(body.ids),
            NotificationModel.read_at.is_(None),
        )
        .values(read_at=now)
    )
    with SqlAlchemyUnitOfWork(db):
        result = db.execute(stmt)
        db.commit()
    updated = int(getattr(result, "rowcount", 0) or 0)
    return MarkReadResponse(updated=updated, unread_count=_unread_count(db, actor.id))


@router.post("/read-all", response_model=MarkReadResponse)
def mark_read_all(
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> MarkReadResponse:
    now = _clock.now()
    stmt = (
        update(NotificationModel)
        .where(
            NotificationModel.recipient_id == actor.id,
            NotificationModel.read_at.is_(None),
        )
        .values(read_at=now)
    )
    with SqlAlchemyUnitOfWork(db):
        result = db.execute(stmt)
        db.commit()
    return MarkReadResponse(updated=int(getattr(result, "rowcount", 0) or 0), unread_count=0)


@router.post("/delete-all", response_model=DeleteAllResponse)
def delete_all(
    body: DeleteAllBody,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> DeleteAllResponse:
    if body.confirm is not True:
        raise AppError(
            "CONFIRMATION_REQUIRED",
            "Debe confirmar la acción.",
            ErrorKind.VALIDATION,
            {"confirm": "Debe ser verdadero."},
        )
    count = db.scalar(
        select(func.count())
        .select_from(NotificationModel)
        .where(NotificationModel.recipient_id == actor.id)
    )
    total = int(count or 0)
    if total == 0:
        return DeleteAllResponse(deleted=0, unread_count=0)
    stmt = delete(NotificationModel).where(NotificationModel.recipient_id == actor.id)
    with SqlAlchemyUnitOfWork(db):
        db.execute(stmt)
        db.commit()
    return DeleteAllResponse(deleted=total, unread_count=0)


def _entity_access(
    *,
    db: Session,
    lookups: SqlAlchemyProjectLookup,
    actor_id: str,
    model: NotificationModel,
) -> None:
    if not model.project_id:
        raise AppError(
            "ENTITY_NOT_AVAILABLE",
            "El elemento ya no está disponible.",
            ErrorKind.NOT_FOUND,
        )
    if not lookups.is_active_member(model.project_id, actor_id):
        raise AppError(
            "ENTITY_ACCESS_DENIED",
            "No tiene acceso a este elemento.",
            ErrorKind.FORBIDDEN,
        )
    entity_exists = False
    if model.entity_type == "task":
        entity_exists = (
            db.scalar(
                select(func.count())
                .select_from(StoryTaskModel)
                .where(
                    StoryTaskModel.id == model.entity_id,
                    StoryTaskModel.project_id == model.project_id,
                )
            )
            or 0
        ) > 0
    elif model.entity_type == "issue":
        entity_exists = (
            db.scalar(
                select(func.count()).select_from(FixModel).where(FixModel.id == model.entity_id)
            )
            or 0
        ) > 0
    elif model.entity_type == "meeting":
        entity_exists = (
            db.scalar(
                select(func.count())
                .select_from(MeetingModel)
                .where(MeetingModel.id == model.entity_id)
            )
            or 0
        ) > 0
    elif model.entity_type == "documentation_entry":
        entity_exists = (
            db.scalar(
                select(func.count())
                .select_from(DocumentationEntryModel)
                .where(DocumentationEntryModel.id == model.entity_id)
            )
            or 0
        ) > 0
    elif model.entity_type == "sprint":
        entity_exists = (
            db.scalar(
                select(func.count())
                .select_from(SprintModel)
                .where(
                    SprintModel.id == model.entity_id,
                    SprintModel.project_id == model.project_id,
                )
            )
            or 0
        ) > 0
    if not entity_exists:
        raise AppError(
            "ENTITY_NOT_AVAILABLE",
            "El elemento ya no está disponible.",
            ErrorKind.NOT_FOUND,
        )


@router.post("/{notification_id}/open", response_model=OpenNotificationResponse)
def open_notification(
    notification_id: str,
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> OpenNotificationResponse:
    model = db.scalar(
        select(NotificationModel).where(
            NotificationModel.id == notification_id,
            NotificationModel.recipient_id == actor.id,
        )
    )
    if model is None:
        raise AppError(
            "NOTIFICATION_NOT_FOUND",
            "La notificación no existe.",
            ErrorKind.NOT_FOUND,
        )
    lookups = SqlAlchemyProjectLookup(db)
    try:
        _entity_access(db=db, lookups=lookups, actor_id=actor.id, model=model)
    except AppError as exc:
        if exc.code == "ENTITY_NOT_AVAILABLE":
            now = _clock.now()
            if model.read_at is None:
                model.read_at = now
                db.commit()
        raise

    event_type = NotificationEventType(model.type)
    route = build_route(event_type, model.project_id or "", model.entity_id)
    if not any(route.startswith(prefix) for prefix in ALLOWED_ROUTE_PREFIXES):
        raise AppError(
            "ENTITY_NOT_AVAILABLE",
            "El elemento ya no está disponible.",
            ErrorKind.NOT_FOUND,
        )
    now = _clock.now()
    if model.read_at is None:
        model.read_at = now
        db.commit()
    else:
        now = model.read_at
    return OpenNotificationResponse(route=route, read_at=now)
