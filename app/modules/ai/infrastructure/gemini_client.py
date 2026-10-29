"""Google Gemini text generation client (free tier)."""

import httpx

from app.config import settings
from app.modules.ai.application.use_cases import GeminiProcessingError


class HttpGeminiClient:
    def generate(self, prompt: str) -> str:
        api_key = settings.API_GEMINI
        if api_key is None or not api_key.get_secret_value().strip():
            raise GeminiProcessingError("missing_api_key")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.0-flash:generateContent"
        )
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1024},
        }
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key.get_secret_value()}
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise GeminiProcessingError("network") from exc
        if response.status_code == 429:
            raise GeminiProcessingError("quota")
        if response.status_code >= 400:
            raise GeminiProcessingError(f"http_{response.status_code}")
        payload = response.json()
        try:
            parts = payload["candidates"][0]["content"]["parts"]
            texts = [part["text"] for part in parts if isinstance(part.get("text"), str)]
        except (KeyError, IndexError, TypeError) as exc:
            raise GeminiProcessingError("invalid_payload") from exc
        if not texts:
            raise GeminiProcessingError("empty")
        return "\n".join(texts)
