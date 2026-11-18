import pytest
from sqlalchemy.orm import Session

from app.modules.ai_metrics.application.ai_metrics_service import AiMetricsService
from app.modules.ai_metrics.application.interaction_registry import (
    SOURCE_ASSISTANT_TEXT,
    SOURCE_ASSISTANT_VOICE,
    SOURCE_METRICS_QUERY,
    InteractionRegistry,
)
from app.modules.ai_metrics.domain import messages as iam_msg
from app.modules.projects.infrastructure.models import ProjectModel
from app.shared.application.identity import CurrentUser
from app.shared.domain.errors import AppError
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.id_generator import UuidGenerator


def _user(role: str) -> CurrentUser:
    now = SystemClock().now()
    return CurrentUser(
        id="user-1",
        email="u@test.local",
        name="Tester",
        role=role,
        is_active=True,
        created_at=now,
    )


def test_developer_forbidden(db_session: Session) -> None:
    service = AiMetricsService(db_session)
    with pytest.raises(AppError) as exc:
        service.get_summary(
            _user("developer"),
            period="30d",
            from_iso=None,
            to_iso=None,
            project_id=None,
        )
    assert exc.value.message == iam_msg.AI_METRICS_DEVELOPER_FORBIDDEN


def test_usage_excludes_metrics_query(db_session: Session) -> None:
    registry = InteractionRegistry(db_session)
    admin = _user("admin")

    usage_id = registry.start_pending(
        user_id=admin.id,
        project_id=None,
        source=SOURCE_ASSISTANT_TEXT,
        request_text="hola",
    )
    registry.complete_success(usage_id, response_text="ok", model_id="test")

    metrics_id = registry.start_pending(
        user_id=admin.id,
        project_id=None,
        source=SOURCE_METRICS_QUERY,
        request_text="metricas",
        counts_as_usage=False,
    )
    registry.complete_success(metrics_id, response_text="resumen", model_id=None)
    db_session.commit()

    service = AiMetricsService(db_session)
    summary = service.get_summary(admin, period="30d", from_iso=None, to_iso=None, project_id=None)
    block = summary["summary"]
    assert isinstance(block, dict)
    assert block["total_interactions"] == 1


def test_manager_scope_filters_other_projects(db_session: Session) -> None:
    ids = UuidGenerator()
    clock = SystemClock()
    now = clock.now()
    managed = ProjectModel(
        id=ids.generate(),
        name="Managed",
        description="",
        owner_id="owner",
        manager_id="mgr-1",
        created_at=now,
        updated_at=now,
    )
    other = ProjectModel(
        id=ids.generate(),
        name="Other",
        description="",
        owner_id="owner",
        manager_id="mgr-2",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([managed, other])
    db_session.flush()

    registry = InteractionRegistry(db_session)
    in_scope = registry.start_pending(
        user_id="dev",
        project_id=managed.id,
        source=SOURCE_ASSISTANT_TEXT,
        request_text="a",
    )
    out_scope = registry.start_pending(
        user_id="dev",
        project_id=other.id,
        source=SOURCE_ASSISTANT_TEXT,
        request_text="b",
    )
    registry.complete_success(in_scope, response_text="x", model_id=None)
    registry.complete_success(out_scope, response_text="y", model_id=None)
    db_session.commit()

    manager = CurrentUser(
        id="mgr-1",
        email="m@test.local",
        name="Mgr",
        role="manager",
        is_active=True,
        created_at=now,
    )
    service = AiMetricsService(db_session)
    listed = service.list_interactions(
        manager, period="30d", from_iso=None, to_iso=None, project_id=None, source=None
    )
    items = listed["items"]
    assert isinstance(items, list)
    project_ids = {item["project_id"] for item in items if isinstance(item, dict)}
    assert other.id not in project_ids
    assert managed.id in project_ids


def test_summary_reports_audio_tokens_and_project_name(db_session: Session) -> None:
    ids = UuidGenerator()
    clock = SystemClock()
    now = clock.now()
    project = ProjectModel(
        id=ids.generate(),
        name="Helix",
        description="",
        owner_id="owner",
        manager_id="mgr-1",
        created_at=now,
        updated_at=now,
    )
    db_session.add(project)
    db_session.flush()

    registry = InteractionRegistry(db_session)
    voice_id = registry.start_pending(
        user_id="mgr-1",
        project_id=project.id,
        source=SOURCE_ASSISTANT_VOICE,
        request_text="hola voz",
        audio_duration_ms=4500,
    )
    registry.complete_success(
        voice_id,
        response_text="ok",
        model_id="gemini",
        input_tokens=10,
        output_tokens=5,
        audio_duration_ms=4500,
    )
    db_session.commit()

    manager = CurrentUser(
        id="mgr-1",
        email="m@test.local",
        name="Mgr",
        role="manager",
        is_active=True,
        created_at=now,
    )
    summary = AiMetricsService(db_session).get_summary(
        manager,
        period="30d",
        from_iso=None,
        to_iso=None,
        project_id=project.id,
    )
    block = summary["summary"]
    assert isinstance(block, dict)
    assert block["audio_duration_ms"] == 4500
    assert block["input_tokens"] == 10
    assert summary.get("scope_name") == "Helix"
