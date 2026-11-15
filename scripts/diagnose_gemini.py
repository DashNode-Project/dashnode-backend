"""Print Gemini API diagnostics (no secrets). Run: python scripts/diagnose_gemini.py"""

from __future__ import annotations

from app.config import settings
from app.modules.ai.infrastructure.gemini_client import (
    DEFAULT_GEMINI_MODEL,
    _normalize_model_id,
    resolve_gemini_api_key,
    validate_gemini_text_generation,
)


def main() -> None:
    raw = resolve_gemini_api_key()
    if not raw:
        print("GEMINI_API_KEY / API_GEMINI is empty")
        return
    print(f"key_prefix={raw[:3]}... len={len(raw)}")
    model = _normalize_model_id(settings.API_GEMINI_MODEL or DEFAULT_GEMINI_MODEL)
    print(f"model={model}")
    print("sdk=google-genai interactions.create")

    ok, detail, status = validate_gemini_text_generation()
    if ok:
        print(f"interactions.create -> {status} OK")
        print(f"  sample: {detail!r}")
        return
    print(f"interactions.create -> {status} FAIL ({detail})")
    if detail == "auth_401":
        print("  Fix: use a valid AI Studio API key (GEMINI_API_KEY).")
    elif detail == "forbidden_403":
        print("  Fix: enable Gemini API for the key / check project permissions.")
    elif detail == "not_found_404":
        print(f"  Fix: set API_GEMINI_MODEL to an available model (e.g. {DEFAULT_GEMINI_MODEL}).")
    elif detail == "quota":
        print("  Fix: wait for quota reset or upgrade billing.")


if __name__ == "__main__":
    main()
