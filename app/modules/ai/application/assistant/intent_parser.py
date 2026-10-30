"""Deterministic Spanish intent parsing (no LLM required for core queries)."""

from __future__ import annotations

import re

from app.modules.ai.application.assistant.intent_models import IntentType, ParsedIntent, TaskFilter
from app.modules.ai.application.assistant.text_normalize import normalize_text


def parse_intent(
    text: str,
    *,
    open_project_name: str | None,
    last_project_names: list[str],
) -> ParsedIntent:
    raw = text.strip()
    normalized = normalize_text(raw)

    conv_index = _conversational_index(normalized, last_project_names)
    if conv_index is not None and _asks_members(normalized):
        return ParsedIntent(
            intent=IntentType.LIST_PROJECT_MEMBERS,
            conversational_index=conv_index,
        )

    if _is_chitchat(normalized):
        return ParsedIntent(intent=IntentType.CHITCHAT)

    if _matches_projects(normalized):
        return ParsedIntent(intent=IntentType.LIST_PROJECTS)

    project_ref = _extract_project_ref(raw, open_project_name)
    sprint_ref = _extract_sprint_ref(raw)

    if _asks_count_stories(normalized):
        return ParsedIntent(
            intent=IntentType.COUNT_PROJECT_HUS,
            project_ref=project_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _asks_documentation(normalized):
        return ParsedIntent(
            intent=IntentType.LIST_DOCUMENTATION,
            project_ref=project_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _asks_members(normalized):
        return ParsedIntent(
            intent=IntentType.LIST_PROJECT_MEMBERS,
            project_ref=project_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
            conversational_index=conv_index,
        )

    if _asks_stories(normalized):
        return ParsedIntent(
            intent=IntentType.LIST_SPRINT_STORIES,
            project_ref=project_ref,
            sprint_ref=sprint_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _asks_sprints(normalized):
        return ParsedIntent(
            intent=IntentType.LIST_SPRINTS,
            project_ref=project_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _asks_tasks(normalized):
        return ParsedIntent(
            intent=IntentType.LIST_TASKS,
            project_ref=project_ref,
            sprint_ref=sprint_ref,
            task_filter=_task_filter(normalized),
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    return ParsedIntent(intent=IntentType.UNKNOWN, project_ref=project_ref, sprint_ref=sprint_ref)


def _is_chitchat(normalized: str) -> bool:
    if len(normalized) < 40 and re.search(
        r"\b(hola|buenos dias|buenas tardes|como estas|qué tal|que tal|gracias)\b", normalized
    ):
        return True
    return bool(re.match(r"^(hola|hey|buenas)( assistente| dashnode)?[!.?]*$", normalized))


def _matches_projects(normalized: str) -> bool:
    if re.match(
        r"^(que\s+)?proyectos(\s+(disponibles|tengo|estoy|hay))?[!.?]*$",
        normalized,
    ):
        return True
    if normalized in {
        "proyectos",
        "mis proyectos",
        "proyectos disponibles",
        "que proyectos",
        "que proyectos tengo",
    }:
        return True
    return bool(
        re.search(
            r"(mis proyectos|cuales son mis proyectos|que proyectos tengo|lista.*proyectos|"
            r"cuantos proyectos|nombres de mis proyectos|proyectos estoy|"
            r"que proyectos tengo disponibles|proyectos tengo disponibles|"
            r"proyectos disponibles|que tengo disponible)",
            normalized,
        )
    )


def _asks_members(normalized: str) -> bool:
    return bool(
        re.search(r"(miembros|integrantes|equipo|quienes participan|quien forma parte)", normalized)
    )


def _asks_sprints(normalized: str) -> bool:
    return "sprint" in normalized and not _asks_stories(normalized)


def _asks_stories(normalized: str) -> bool:
    if _asks_count_stories(normalized):
        return False
    return bool(
        re.search(
            r"\b(hu|hus|historias? de usuario|historias de usuario|historias)\b",
            normalized,
        )
    )


def _asks_count_stories(normalized: str) -> bool:
    return bool(
        re.search(
            r"(cuant(a|o)s|numero de|cantidad de|cuenta).*(hu|hus|historias? de usuario|historias)",
            normalized,
        )
        or re.search(
            r"(hu|hus|historias).*(cuant(a|o)s|numero|cantidad)",
            normalized,
        )
    )


def _asks_tasks(normalized: str) -> bool:
    return bool(
        re.search(
            r"\b(tarea|tareas|tasks|pendiente|pendientes|por hacer|tengo pendiente)\b",
            normalized,
        )
    )


def _asks_documentation(normalized: str) -> bool:
    return bool(re.search(r"(documentacion|documentos?|docs)\b", normalized))


def _mentions_this_project(normalized: str) -> bool:
    return bool(re.search(r"(este proyecto|mi proyecto|proyecto actual)", normalized))


def _task_filter(normalized: str) -> TaskFilter:
    if re.search(r"(corregir|correccion|por corregir)", normalized):
        return TaskFilter.CORRECTION
    if "bloquead" in normalized:
        return TaskFilter.BLOCKED
    if re.search(r"(sin asignar|no asignad)", normalized):
        return TaskFilter.UNASSIGNED
    if re.search(r"(asignadas? a mi|mis tareas)", normalized):
        return TaskFilter.ASSIGNED_TO_ME
    if re.search(r"(pendiente|por hacer|todo|abiertas?|tengo pendiente)", normalized):
        return TaskFilter.PENDING
    return TaskFilter.ALL


def _extract_sprint_ref(text: str) -> str | None:
    normalized = normalize_text(text)
    match = re.search(r"sprint\s*(\d+)", normalized)
    if match:
        return match.group(1)
    ordinals = {
        "primero": "1",
        "primer": "1",
        "segundo": "2",
        "tercer": "3",
        "tercero": "3",
        "cuarto": "4",
    }
    for word, num in ordinals.items():
        if word in normalized and "sprint" in normalized:
            return num
    return None


def _extract_project_ref(text: str, open_project_name: str | None) -> str | None:
    normalized = normalize_text(text)
    if _mentions_this_project(normalized) and open_project_name:
        return open_project_name
    quoted = re.findall(r"[\"“](.+?)[\"”]", text)
    if quoted:
        return quoted[0].strip()
    match = re.search(
        r"(?:mi\s+)?(?:proyecto|project)\s+([a-zA-Z0-9][a-zA-Z0-9 \-_]{1,40}?)"
        r"(?:\s+ah[ií]|\s+alli|\s+all[ií]|$|[,.!?])",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    en_match = re.search(
        r"\ben\s+([a-zA-Z0-9][a-zA-Z0-9 \-_]{2,50})\b",
        text,
        flags=re.IGNORECASE,
    )
    if en_match:
        return en_match.group(1).strip()
    for token in ("dashnode", "dash node", "mundo pinturas"):
        if token in normalized:
            return token
    return None


def _conversational_index(normalized: str, last_project_names: list[str]) -> int | None:
    if not last_project_names:
        return None
    if re.search(r"\b(el primero|la primera|primer proyecto|primero)\b", normalized):
        return 0
    if re.search(r"\b(el segundo|la segunda|segundo)\b", normalized):
        return 1 if len(last_project_names) > 1 else None
    if re.search(r"\b(ese proyecto|esa proyecto|el mismo)\b", normalized):
        return 0
    return None
