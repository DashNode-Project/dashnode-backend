"""OpenAI Whisper transcription client (free tier, in-memory only)."""

import httpx

from app.config import settings
from app.modules.ai.application.use_cases import WhisperProcessingError


class HttpWhisperClient:
    def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
        api_key = settings.API_TRANSCRIPTION_WHISPER
        if api_key is None or not api_key.get_secret_value().strip():
            raise WhisperProcessingError("missing_api_key")
        filename = "voice.webm" if "webm" in content_type else "voice.wav"
        files = {"file": (filename, audio_bytes, content_type or "audio/webm")}
        data = {"model": "whisper-1", "language": "es"}
        headers = {"Authorization": f"Bearer {api_key.get_secret_value()}"}
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers=headers,
                    data=data,
                    files=files,
                )
        except httpx.HTTPError as exc:
            raise WhisperProcessingError("network") from exc
        if response.status_code == 429:
            raise WhisperProcessingError("quota")
        if response.status_code >= 400:
            raise WhisperProcessingError(f"http_{response.status_code}")
        payload = response.json()
        text = payload.get("text")
        if not isinstance(text, str):
            raise WhisperProcessingError("invalid_payload")
        return text
