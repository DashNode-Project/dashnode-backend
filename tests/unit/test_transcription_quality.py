from app.modules.ai.application.transcription_quality import is_low_quality_transcription


def test_rejects_amara_hallucination() -> None:
    assert is_low_quality_transcription("Subtítulos realizados por la comunidad de Amara.org")


def test_accepts_normal_spanish() -> None:
    assert not is_low_quality_transcription("¿Cuántos proyectos tengo?")
