"""OpenAI Whisper transcription client (free tier, in-memory only)."""

import httpx

from app.config import settings
from app.modules.ai.application.use_cases import WhisperProcessingError

_WHISPER_PROMPT = (
    "Consulta en español sobre proyectos DashNode, historias de usuario, tareas, sprints y miembros."
)


class HttpWhisperClient:
    def transcribe(self, audio_bytes: bytes, content_type: str) -> str:
        api_key = settings.API_TRANSCRIPTION_WHISPER
        if api_key is None or not api_key.get_secret_value().strip():
            raise WhisperProcessingError("missing_api_key")
        filename = "voice.webm" if "webm" in content_type else "voice.wav"
        files = {"file": (filename, audio_bytes, content_type or "audio/webm")}
        data = {
            "model": "whisper-1",
            "language": "es",
            "response_format": "verbose_json",
            "temperature": "0",
            "prompt": _WHISPER_PROMPT,
        }
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
        segments = payload.get("segments")
        if isinstance(segments, list) and segments:
            probs = [
                float(segment["no_speech_prob"])
                for segment in segments
                if isinstance(segment, dict) and segment.get("no_speech_prob") is not None
            ]
            if probs and sum(probs) / len(probs) > 0.55:
                raise WhisperProcessingError("no_speech")
        return text
