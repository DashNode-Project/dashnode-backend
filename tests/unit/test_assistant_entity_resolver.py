from app.modules.ai.application.assistant.entity_resolver import (
    ProjectCandidate,
    find_project_name_in_utterance,
    resolve_project,
)


def test_fuzzy_project_name() -> None:
    candidates = [ProjectCandidate("1", "DashNode Initial Project")]
    result = resolve_project("dash node", candidates, threshold=70)
    assert result.value is not None
    assert result.value.id == "1"


def test_find_project_in_sentence() -> None:
    candidates = [
        ProjectCandidate("1", "VozNotAI"),
        ProjectCandidate("2", "DashNode Initial Project"),
    ]
    result = find_project_name_in_utterance("Cuántas HUs tiene VozNotAI", candidates)
    assert result.value is not None
    assert result.value.name == "VozNotAI"


def test_ambiguous_projects() -> None:
    candidates = [
        ProjectCandidate("1", "DashNode Alpha"),
        ProjectCandidate("2", "DashNode Beta"),
    ]
    result = resolve_project("dashnode", candidates, threshold=60)
    assert result.value is None
    assert len(result.ambiguous) >= 2
