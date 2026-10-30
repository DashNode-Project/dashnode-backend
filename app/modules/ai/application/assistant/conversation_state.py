"""Short-lived conversational references (per user)."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.modules.ai.infrastructure.models import AiConversationStateModel


class ConversationStateStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def load(self, user_id: str) -> dict:
        row = self._session.get(AiConversationStateModel, user_id)
        if row is None or not row.payload:
            return {"last_project_ids": [], "last_project_names": []}
        try:
            data = json.loads(row.payload)
        except json.JSONDecodeError:
            return {"last_project_ids": [], "last_project_names": []}
        if not isinstance(data, dict):
            return {"last_project_ids": [], "last_project_names": []}
        return data

    def save(self, user_id: str, data: dict) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        row = self._session.get(AiConversationStateModel, user_id)
        if row is None:
            self._session.add(AiConversationStateModel(user_id=user_id, payload=payload))
        else:
            row.payload = payload
        self._session.flush()
