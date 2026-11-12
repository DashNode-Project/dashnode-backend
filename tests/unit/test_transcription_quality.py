from app.modules.ai.application.transcription_quality import is_low_quality_transcription


def test_rejects_amara_hallucination() -> None:
    assert is_low_quality_transcription("Subtítulos realizados por la comunidad de Amara.org")


def test_rejects_paz_justicia_loop() -> None:
    assert is_low_quality_transcription("¡Paz! ¡Justicia! ¡Paz! ¡Justicia! ¡Paz!")


def test_rejects_gracias_para_ti_hallucination() -> None:
    assert is_low_quality_transcription("Sí. Gracias, para ti.")


def test_accepts_normal_spanish() -> None:
    assert not is_low_quality_transcription("¿Cuántos proyectos tengo?")
