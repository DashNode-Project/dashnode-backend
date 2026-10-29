"""Chat history isolation and retention (EP-10)."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.modules.ai.infrastructure.chat_history_repository import SqlAlchemyChatHistoryRepository
from app.modules.ai.infrastructure.models import AiChatMessageModel
from app.shared.infrastructure.id_generator import UuidGenerator
from tests.support import login_as


def test_chat_history_isolated_per_user(client: TestClient, db_engine: Engine) -> None:
    admin_id = login_as(client, db_engine, email="admin-chat@dashnode.local", role="admin")
    response = client.get("/api/v1/ai/chat/messages")
    assert response.status_code == 200
    assert response.json()["messages"] == []

    manager_id = login_as(client, db_engine, email="mgr-chat@dashnode.local", role="manager")
    response_mgr = client.get("/api/v1/ai/chat/messages")
    assert response_mgr.status_code == 200
    assert response_mgr.json()["messages"] == []
    assert admin_id != manager_id


def test_chat_history_purges_entries_older_than_retention(db_session: Session) -> None:
    repo = SqlAlchemyChatHistoryRepository(db_session)
    ids = UuidGenerator()
    user_id = ids.generate()
    old = datetime.now(timezone.utc) - timedelta(hours=30)
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.add(
        AiChatMessageModel(
            id=ids.generate(),
            user_id=user_id,
            role="user",
            text="viejo",
            input_source="text",
            created_at=old,
        )
    )
    db_session.add(
        AiChatMessageModel(
            id=ids.generate(),
            user_id=user_id,
            role="assistant",
            text="reciente",
            input_source=None,
            created_at=recent,
        )
    )
    db_session.flush()
    messages = repo.list_for_user(user_id)
    assert len(messages) == 1
    assert messages[0].text == "reciente"
