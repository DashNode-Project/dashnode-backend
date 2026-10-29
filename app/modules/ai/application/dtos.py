"""DTOs for AI assistant endpoints (EP-10)."""

from enum import StrEnum

from pydantic import BaseModel, Field


class AssistantResponseStatus(StrEnum):
    RESPONDED = "RESPONDED"
    ERROR = "ERROR"


class VoiceProcessResponse(BaseModel):
    recognized_text: str | None = None
    assistant_response: str | None = None
    status: AssistantResponseStatus
    error: str | None = None


class TextGenerateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    project_id: str | None = None


class TextGenerateResponse(BaseModel):
    recognized_text: str
    assistant_response: str | None = None
    status: AssistantResponseStatus
    error: str | None = None
