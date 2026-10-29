"""AI assistant HTTP routes (EP-10)."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.modules.ai.application.dtos import (
    TextGenerateRequest,
    TextGenerateResponse,
    VoiceProcessResponse,
)
from app.modules.ai.application.use_cases import (
    GenerateTextUseCase,
    ProcessVoiceUseCase,
    TextGenerateCommand,
    VoiceProcessCommand,
)
from app.modules.ai.infrastructure.gemini_client import HttpGeminiClient
from app.modules.ai.infrastructure.quota_repository import SqlAlchemyQuotaRepository
from app.modules.ai.infrastructure.whisper_client import HttpWhisperClient
from app.orchestration.ai_context import SqlAlchemyProjectContextBuilder
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.database import get_db_session

router = APIRouter(prefix="/ai", tags=["ai"])


def _voice_use_case(db: Session = Depends(get_db_session)) -> ProcessVoiceUseCase:
    return ProcessVoiceUseCase(
        transcription=HttpWhisperClient(),
        generation=HttpGeminiClient(),
        quotas=SqlAlchemyQuotaRepository(db),
        project_context=SqlAlchemyProjectContextBuilder(db),
        min_bytes=settings.AI_VOICE_MIN_BYTES,
        max_bytes=settings.AI_VOICE_MAX_BYTES,
        max_seconds=float(settings.AI_VOICE_MAX_SECONDS),
    )


def _text_use_case(db: Session = Depends(get_db_session)) -> GenerateTextUseCase:
    return GenerateTextUseCase(
        generation=HttpGeminiClient(),
        quotas=SqlAlchemyQuotaRepository(db),
        project_context=SqlAlchemyProjectContextBuilder(db),
    )


@router.post("/voice-process", response_model=VoiceProcessResponse)
async def voice_process(
    audio: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    duration_seconds: float | None = Form(default=None),
    actor: CurrentUser = Depends(get_current_user),
    use_case: ProcessVoiceUseCase = Depends(_voice_use_case),
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
    return use_case.execute(cmd)


@router.post("/text-generate", response_model=TextGenerateResponse)
def text_generate(
    body: TextGenerateRequest,
    actor: CurrentUser = Depends(get_current_user),
    use_case: GenerateTextUseCase = Depends(_text_use_case),
) -> TextGenerateResponse:
    cmd = TextGenerateCommand(
        text=body.text,
        project_id=body.project_id,
        user_id=actor.id,
        user_role=actor.role,
    )
    return use_case.execute(cmd)
