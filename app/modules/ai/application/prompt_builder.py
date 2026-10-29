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
    if context.workspace_summary:
        parts.append("Contexto del usuario en DashNode:")
        parts.append(sanitize_fragment(context.workspace_summary))
    if context.project_name:
        parts.append("Contexto del Proyecto:")
        parts.append(f"Nombre: {sanitize_fragment(context.project_name)}")
        if context.project_description:
            parts.append(f"Descripción: {sanitize_fragment(context.project_description)}")
        if context.active_sprint_name:
            parts.append(f"Sprint Activo: {sanitize_fragment(context.active_sprint_name)}")
        if context.project_metrics_summary:
            parts.append("Métricas y detalle del proyecto (datos de DashNode):")
            parts.append(sanitize_fragment(context.project_metrics_summary))
        if context.approved_doc_snippets:
            parts.append("Documentos Aprobados Relevantes:")
            for snippet in context.approved_doc_snippets[:5]:
                parts.append(f"- {sanitize_fragment(snippet)}")
    parts.append(f"Consulta del Usuario: {safe_query}")
    parts.append(
        "Responde en español en 1 a 4 oraciones cortas, claras y pertinentes. "
        "Usa únicamente los números, fechas y listados del contexto para preguntas sobre "
        "proyectos, HUs, tareas, miembros o sprints. "
        "Si el dato no está en el contexto, dilo explícitamente sin inventar cifras. "
        "No inventes credenciales ni datos de otros proyectos."
    )
    return "\n".join(parts)
