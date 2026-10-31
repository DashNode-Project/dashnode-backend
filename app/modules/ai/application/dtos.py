"""DTOs for AI assistant endpoints (EP-10)."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class AssistantResponseStatus(StrEnum):
    RESPONDED = "RESPONDED"
    ERROR = "ERROR"


class VoiceProcessResponse(BaseModel):
    recognized_text: str | None = None
    assistant_response: str | None = None
    status: AssistantResponseStatus
    error: str | None = None


class VoiceTranscribeResponse(BaseModel):
    recognized_text: str


class TextGenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    project_id: str | None = None
    persist_user_message: bool = True


class ChatHistoryMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    text: str
    input_source: Literal["text", "voice"] | None = None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessage]


class TextGenerateResponse(BaseModel):
    recognized_text: str
    assistant_response: str | None = None
    status: AssistantResponseStatus
    error: str | None = None
