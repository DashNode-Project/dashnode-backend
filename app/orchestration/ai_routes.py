"""AI assistant HTTP routes (EP-10)."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

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
from app.modules.ai.infrastructure.chat_history_repository import SqlAlchemyChatHistoryRepository
from app.modules.ai.infrastructure.gemini_client import HttpGeminiClient
from app.modules.ai.infrastructure.quota_repository import SqlAlchemyQuotaRepository
from app.modules.ai.infrastructure.whisper_client import HttpWhisperClient
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.database import get_db_session

router = APIRouter(prefix="/ai", tags=["ai"])


def _chat_history(db: Session) -> SqlAlchemyChatHistoryRepository:
    return SqlAlchemyChatHistoryRepository(db)


def _voice_use_case(db: Session = Depends(get_db_session)) -> ProcessVoiceUseCase:
    return ProcessVoiceUseCase(
        session=db,
        transcription=HttpWhisperClient(),
        generation=HttpGeminiClient(),
        quotas=SqlAlchemyQuotaRepository(db),
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
        generation=HttpGeminiClient(),
        quotas=SqlAlchemyQuotaRepository(db),
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
    text = use_case.execute(cmd)
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
    result = use_case.execute(cmd)
    chat = _chat_history(db)
    if result.recognized_text:
        chat.append(actor.id, role="user", text=result.recognized_text, input_source="voice")
    if result.assistant_response:
        chat.append(actor.id, role="assistant", text=result.assistant_response)
    db.commit()
    return result


@router.post("/text-generate", response_model=TextGenerateResponse)
def text_generate(
    body: TextGenerateRequest,
    actor: CurrentUser = Depends(get_current_user),
    use_case: GenerateTextUseCase = Depends(_text_use_case),
    db: Session = Depends(get_db_session),
) -> TextGenerateResponse:
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
    result = use_case.execute(cmd)
    if result.assistant_response:
        chat.append(actor.id, role="assistant", text=result.assistant_response)
    db.commit()
    return result
