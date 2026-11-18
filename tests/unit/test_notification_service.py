"""Unit tests for EP-14 NotificationService."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.modules.notifications.application.catalog import NotificationEventType
from app.modules.notifications.application.notification_service import (
    NotificationEvent,
    NotificationService,
)
from app.modules.notifications.infrastructure.models import NotificationModel
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import Base
from app.shared.infrastructure.id_generator import UuidGenerator


def test_notify_excludes_actor_and_is_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    clock = SystemClock()
    id_gen = UuidGenerator()
    with Session(engine) as session:
        service = NotificationService(session, id_gen, clock)
        event = NotificationEvent(
            type=NotificationEventType.TASK_ASSIGNED,
            event_key="TASK_ASSIGNED:t1:1",
            project_id="p1",
            entity_id="t1",
            actor_id="actor",
            context={"task": "Demo", "project": "DashNode"},
        )
        first = service.notify(event=event, recipients=["actor", "dev1"], actor_id="actor")
        second = service.notify(event=event, recipients=["dev1"], actor_id="actor")
        session.commit()
        assert first == 1
        assert second == 0
        rows = session.scalars(select(NotificationModel)).all()
        assert len(rows) == 1
        assert rows[0].recipient_id == "dev1"
        assert rows[0].actor_id == "actor"


def test_notify_render_messages_cover_event_types() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    clock = SystemClock()
    id_gen = UuidGenerator()
    samples: list[tuple[NotificationEventType, dict[str, str], str]] = [
        (
            NotificationEventType.SPRINT_STARTED,
            {"sprint": "S1", "project": "P"},
            "inició",
        ),
        (
            NotificationEventType.ISSUE_REPORTED,
            {"issue": "Bug", "project": "P", "severity": "ALTA"},
            "reportado",
        ),
        (
            NotificationEventType.MEETING_SCHEDULED,
            {"meeting": "Daily", "when": "2026-11-18 09:00"},
            "Daily",
        ),
        (
            NotificationEventType.DOC_APPROVED,
            {"entry": "Wiki"},
            "aprobada",
        ),
        (
            NotificationEventType.MEETING_CANCELLED,
            {"meeting": "Retro", "when": "hoy"},
            "cancelada",
        ),
        (
            NotificationEventType.ISSUE_ASSIGNED,
            {"issue": "INC-1", "project": "P"},
            "asignó",
        ),
    ]
    with Session(engine) as session:
        service = NotificationService(session, id_gen, clock)
        for n, (etype, ctx, _needle) in enumerate(samples):
            service.notify(
                event=NotificationEvent(
                    type=etype,
                    event_key=f"{etype.value}:e{n}:1",
                    project_id="p1",
                    entity_id=f"e{n}",
                    actor_id=None,
                    context=ctx,
                ),
                recipients=["dev1"],
                actor_id=None,
            )
        session.commit()
        rows = session.scalars(select(NotificationModel)).all()
        assert len(rows) == len(samples)
        for row, (_, _, needle) in zip(rows, samples, strict=True):
            assert needle in row.message


def test_notify_truncates_long_context_names() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    long_task = "A" * 80
    with Session(engine) as session:
        service = NotificationService(session, UuidGenerator(), SystemClock())
        service.notify(
            event=NotificationEvent(
                type=NotificationEventType.TASK_ASSIGNED,
                event_key="TASK_ASSIGNED:long:1",
                project_id="p1",
                entity_id="t1",
                actor_id=None,
                context={"task": long_task, "project": "P"},
            ),
            recipients=["dev1"],
            actor_id=None,
        )
        session.commit()
        row = session.scalars(select(NotificationModel)).one()
        assert "…" in row.message


def test_notify_returns_zero_without_recipients() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = NotificationService(session, UuidGenerator(), SystemClock())
        count = service.notify(
            event=NotificationEvent(
                type=NotificationEventType.TASK_ASSIGNED,
                event_key="TASK_ASSIGNED:x:1",
                project_id="p1",
                entity_id="x",
                actor_id="a",
                context={"task": "T", "project": "P"},
            ),
            recipients=[],
            actor_id="a",
        )
        assert count == 0


def test_notify_issue_reported_without_recipients_returns_zero() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        service = NotificationService(session, UuidGenerator(), SystemClock())
        count = service.notify(
            event=NotificationEvent(
                type=NotificationEventType.ISSUE_REPORTED,
                event_key="ISSUE_REPORTED:i1:1",
                project_id="p1",
                entity_id="i1",
                actor_id="reporter",
                context={"issue": "X", "project": "P", "severity": "ALTA"},
            ),
            recipients=["reporter"],
            actor_id="reporter",
        )
        assert count == 0
