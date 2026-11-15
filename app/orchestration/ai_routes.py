"""AI assistant HTTP routes (EP-10)."""

import asyncio
import secrets

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.modules.ai.application.dtos import (
    ChatHistoryResponse,
    TextGenerateRequest,
    TextGenerateResponse,
    VoiceProcessResponse,
    VoiceTranscribeResponse,
)
from app.modules.ai.application.use_cases import (
    GenerateTextUseCase,
    ProcessVoiceUseCase,
    TextGenerateCommand,
    TranscribeVoiceUseCase,
    VoiceProcessCommand,
)
from app.modules.ai.domain import messages as ai_msg
from app.modules.ai.infrastructure.chat_history_repository import SqlAlchemyChatHistoryRepository
from app.modules.ai.infrastructure.gemini_client import GenAiGeminiClient
from app.modules.ai.infrastructure.quota_repository import SqlAlchemyQuotaRepository
from app.modules.ai.infrastructure.whisper_client import HttpWhisperClient
from app.orchestration.assistant_data_queries import AssistantDataService
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.domain.errors import AppError, ErrorKind
from app.shared.infrastructure.ai_request_trace import (
    bind_request_id,
    log_ai_stage,
    reset_request_id,
)
from app.shared.infrastructure.database import get_db_session

router = APIRouter(prefix="/ai", tags=["ai"])


def _chat_history(db: Session) -> SqlAlchemyChatHistoryRepository:
    return SqlAlchemyChatHistoryRepository(db)


def _voice_use_case(db: Session = Depends(get_db_session)) -> ProcessVoiceUseCase:
    return ProcessVoiceUseCase(
        session=db,
        transcription=HttpWhisperClient(),
        generation=GenAiGeminiClient(),
        quotas=SqlAlchemyQuotaRepository(db),
        data=AssistantDataService(db),
        min_bytes=settings.AI_VOICE_MIN_BYTES,
        max_bytes=settings.AI_VOICE_MAX_BYTES,
        max_seconds=float(settings.AI_VOICE_MAX_SECONDS),
    )


def _transcribe_use_case(db: Session = Depends(get_db_session)) -> TranscribeVoiceUseCase:
    return TranscribeVoiceUseCase(
        transcription=HttpWhisperClient(),
        quotas=SqlAlchemyQuotaRepository(db),
        min_bytes=settings.AI_VOICE_MIN_BYTES,
        max_bytes=settings.AI_VOICE_MAX_BYTES,
        max_seconds=float(settings.AI_VOICE_MAX_SECONDS),
    )


def _text_use_case(db: Session = Depends(get_db_session)) -> GenerateTextUseCase:
    return GenerateTextUseCase(
        session=db,
        generation=GenAiGeminiClient(),
        quotas=SqlAlchemyQuotaRepository(db),
        data=AssistantDataService(db),
    )


@router.get("/chat/messages", response_model=ChatHistoryResponse)
def list_chat_messages(
    actor: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ChatHistoryResponse:
    messages = _chat_history(db).list_for_user(actor.id)
    db.commit()
    return ChatHistoryResponse(messages=messages)


@router.post("/voice-transcribe", response_model=VoiceTranscribeResponse)
async def voice_transcribe(
    audio: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    duration_seconds: float | None = Form(default=None),
    actor: CurrentUser = Depends(get_current_user),
    use_case: TranscribeVoiceUseCase = Depends(_transcribe_use_case),
    db: Session = Depends(get_db_session),
) -> VoiceTranscribeResponse:
    content_type = audio.content_type or "application/octet-stream"
    raw = await audio.read()
    cmd = VoiceProcessCommand(
        audio_bytes=raw,
        content_type=content_type,
        duration_seconds=duration_seconds,
        project_id=project_id,
        user_id=actor.id,
        user_role=actor.role,
    )
    text = await run_in_threadpool(use_case.execute, cmd)
    _chat_history(db).append(actor.id, role="user", text=text, input_source="voice")
    db.commit()
    return VoiceTranscribeResponse(recognized_text=text)


@router.post("/voice-process", response_model=VoiceProcessResponse)
async def voice_process(
    audio: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    duration_seconds: float | None = Form(default=None),
    actor: CurrentUser = Depends(get_current_user),
    use_case: ProcessVoiceUseCase = Depends(_voice_use_case),
    db: Session = Depends(get_db_session),
) -> VoiceProcessResponse:
    content_type = audio.content_type or "application/octet-stream"
    raw = await audio.read()
    cmd = VoiceProcessCommand(
        audio_bytes=raw,
        content_type=content_type,
        duration_seconds=duration_seconds,
        project_id=project_id,
        user_id=actor.id,
        user_role=actor.role,
    )
    result = await run_in_threadpool(use_case.execute, cmd)
    chat = _chat_history(db)
    if result.recognized_text:
        chat.append(actor.id, role="user", text=result.recognized_text, input_source="voice")
    if result.assistant_response:
        chat.append(actor.id, role="assistant", text=result.assistant_response)
    db.commit()
    return result


@router.post("/text-generate", response_model=TextGenerateResponse)
async def text_generate(
    body: TextGenerateRequest,
    actor: CurrentUser = Depends(get_current_user),
    use_case: GenerateTextUseCase = Depends(_text_use_case),
    db: Session = Depends(get_db_session),
) -> TextGenerateResponse:
    request_id = secrets.token_hex(6)
    trace_token = bind_request_id(request_id)
    log_ai_stage("route_enter", endpoint="text-generate", user_id=actor.id)
    try:
        cmd = TextGenerateCommand(
            text=body.text,
            project_id=body.project_id,
            user_id=actor.id,
            user_role=actor.role,
        )
        chat = _chat_history(db)
        trimmed = body.text.strip()
        if body.persist_user_message and trimmed:
            chat.append(actor.id, role="user", text=trimmed, input_source="text")
            log_ai_stage("chat_user_persisted")

        def _run_use_case() -> TextGenerateResponse:
            log_ai_stage("orchestrator_dispatch")
            return use_case.execute(cmd)

        try:
            result = await asyncio.wait_for(
                run_in_threadpool(_run_use_case),
                timeout=float(settings.AI_TEXT_GENERATE_TIMEOUT_SECONDS),
            )
        except TimeoutError as exc:
            log_ai_stage(
                "route_timeout",
                limit_s=settings.AI_TEXT_GENERATE_TIMEOUT_SECONDS,
            )
            raise AppError(
                "AI_REQUEST_TIMEOUT",
                ai_msg.AI_REQUEST_TIMEOUT,
                ErrorKind.UNAVAILABLE,
            ) from exc

        if result.assistant_response:
            chat.append(actor.id, role="assistant", text=result.assistant_response)
            log_ai_stage("chat_assistant_persisted")
        db.commit()
        log_ai_stage("route_response", status=result.status.value)
        return result
    finally:
        reset_request_id(trace_token)
