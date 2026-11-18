"""EP-14 notification catalog helpers."""

from app.modules.notifications.application.catalog import NotificationEventType, build_route


def test_build_route_variants() -> None:
    pid, eid = "proj-1", "ent-1"
    assert build_route(NotificationEventType.TASK_ASSIGNED, pid, eid).endswith(f"task={eid}")
    assert (
        build_route(NotificationEventType.SPRINT_STARTED, pid, eid) == f"/proyectos/{pid}/sprints"
    )
    assert build_route(NotificationEventType.ISSUE_REPORTED, pid, eid).endswith(f"issue={eid}")
    assert build_route(NotificationEventType.MEETING_SCHEDULED, pid, eid).endswith(f"meeting={eid}")
    assert build_route(NotificationEventType.MEETING_CANCELLED, pid, eid).endswith(f"meeting={eid}")
    assert build_route(NotificationEventType.ISSUE_ASSIGNED, pid, eid).endswith(f"issue={eid}")
    assert build_route(NotificationEventType.DOC_REJECTED, pid, eid).endswith(f"entry={eid}")
    assert build_route(NotificationEventType.DOC_APPROVED, pid, eid).endswith(f"entry={eid}")
