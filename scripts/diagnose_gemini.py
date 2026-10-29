"""Print Gemini API diagnostics (no secrets). Run: python scripts/diagnose_gemini.py"""

from __future__ import annotations

from app.config import settings
from app.modules.ai.infrastructure.gemini_client import (
    DEFAULT_GEMINI_MODEL,
    _auth_headers,
    _normalize_model_id,
    validate_gemini_text_generation,
)


def main() -> None:
    raw = settings.API_GEMINI.get_secret_value().strip() if settings.API_GEMINI else ""
    if not raw:
        print("API_GEMINI is empty")
        return
    print(f"key_prefix={raw[:3]}... len={len(raw)}")
    model = _normalize_model_id(settings.API_GEMINI_MODEL or DEFAULT_GEMINI_MODEL)
    print(f"model={model}")
    headers = _auth_headers(raw)
    if "Authorization" in headers:
        print("auth_mode=INVALID (Bearer must not be used)")
    else:
        print("auth_mode=x-goog-api-key")

    ok, detail, status = validate_gemini_text_generation()
    if ok:
        print(f"generateContent -> {status} OK")
        print(f"  sample: {detail!r}")
        return
    print(f"generateContent -> {status} FAIL ({detail})")
    if detail == "auth_401":
        print("  Fix: use a valid AI Studio API key with header x-goog-api-key.")
    elif detail == "forbidden_403":
        print("  Fix: enable Gemini API for the key / check project permissions.")
    elif detail == "not_found_404":
        print(f"  Fix: set API_GEMINI_MODEL to an available model (e.g. {DEFAULT_GEMINI_MODEL}).")


if __name__ == "__main__":
    main()
