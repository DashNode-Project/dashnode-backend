"""Build Gemini prompts with optional RBAC-filtered project context (HU 96)."""

import re

from app.modules.ai.domain.ports import ProjectAiContext

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_SECRET_RE = re.compile(r"(sk-[a-zA-Z0-9_-]{10,}|password\s*[:=]\s*\S+)", re.IGNORECASE)


def sanitize_fragment(text: str) -> str:
    cleaned = _EMAIL_RE.sub("[correo omitido]", text)
    return _SECRET_RE.sub("[dato sensible omitido]", cleaned)


def build_assistant_prompt(context: ProjectAiContext, user_query: str) -> str:
    safe_query = sanitize_fragment(user_query.strip())
    parts: list[str] = []
    if context.project_name:
        parts.append("Contexto del Proyecto:")
        parts.append(f"Nombre: {sanitize_fragment(context.project_name)}")
        if context.project_description:
            parts.append(f"Descripción: {sanitize_fragment(context.project_description)}")
        if context.active_sprint_name:
            parts.append(f"Sprint Activo: {sanitize_fragment(context.active_sprint_name)}")
        if context.approved_doc_snippets:
            parts.append("Documentos Aprobados Relevantes:")
            for snippet in context.approved_doc_snippets[:5]:
                parts.append(f"- {sanitize_fragment(snippet)}")
    parts.append(f"Consulta del Usuario: {safe_query}")
    parts.append(
        "Responde en español, de forma concisa y útil, asistiendo al usuario "
        "con base en este contexto cuando aplique. "
        "No inventes credenciales ni datos de otros proyectos."
    )
    return "\n".join(parts)
