"""Unit tests for AI prompt building and sanitization (HU 96)."""

from app.modules.ai.application.prompt_builder import build_assistant_prompt, sanitize_fragment
from app.modules.ai.domain.ports import ProjectAiContext


def test_sanitize_fragment_removes_emails_and_secrets() -> None:
    raw = "Contact admin@secret.com with sk-abcdefghijklmnop"
    cleaned = sanitize_fragment(raw)
    assert "admin@secret.com" not in cleaned
    assert "sk-" not in cleaned


def test_build_assistant_prompt_includes_project_context() -> None:
    ctx = ProjectAiContext(
        project_name="DashNode",
        project_description="Plataforma",
        active_sprint_name="Sprint 6",
        approved_doc_snippets=("Doc: fragmento",),
        project_metrics_summary="Resumen numérico: 3 HUs, 5 tareas, 2 miembros.",
    )
    prompt = build_assistant_prompt(ctx, "Estado del sprint")
    assert "DashNode" in prompt
    assert "Sprint 6" in prompt
    assert "3 HUs" in prompt
    assert "Estado del sprint" in prompt


def test_build_assistant_prompt_without_project() -> None:
    ctx = ProjectAiContext(
        None,
        None,
        None,
        (),
        workspace_summary="Proyectos accesibles para el usuario: 2.",
    )
    prompt = build_assistant_prompt(ctx, "Hola")
    assert "Consulta del Usuario: Hola" in prompt
    assert "Contexto del Proyecto" not in prompt
    assert "Proyectos accesibles" in prompt
