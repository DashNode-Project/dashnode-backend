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
    project_ref = _clean_project_ref(_extract_project_ref(raw, open_project_name))
    sprint_ref = _extract_sprint_ref(raw)

    conv_index = _conversational_index(normalized, last_project_names)
    if conv_index is not None and _asks_members(normalized):
        return ParsedIntent(
            intent=IntentType.LIST_PROJECT_MEMBERS,
            conversational_index=conv_index,
        )

    if _asks_project_summary(normalized):
        return ParsedIntent(
            intent=IntentType.PROJECT_SUMMARY,
            project_ref=project_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
            conversational_index=_summary_conversational_index(normalized, last_project_names),
        )

    if _matches_projects(normalized):
        return ParsedIntent(intent=IntentType.LIST_PROJECTS)

    if _asks_count_stories(normalized):
        return ParsedIntent(
            intent=IntentType.COUNT_PROJECT_HUS,
            project_ref=project_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _asks_members(normalized) and _asks_all_projects_scope(normalized):
        return ParsedIntent(intent=IntentType.LIST_ALL_PROJECT_MEMBERS)

    if _asks_gemini_grounded(normalized):
        return ParsedIntent(
            intent=IntentType.GEMINI_GROUNDED,
            project_ref=project_ref,
            sprint_ref=sprint_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _asks_hu_analysis(normalized):
        return ParsedIntent(
            intent=IntentType.ANALYZE_USER_STORIES,
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

    if _is_bare_hu_query(normalized):
        return ParsedIntent(
            intent=IntentType.LIST_SPRINT_STORIES,
            project_ref=project_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _is_chitchat(normalized):
        return ParsedIntent(intent=IntentType.CHITCHAT)

    return ParsedIntent(intent=IntentType.UNKNOWN, project_ref=project_ref, sprint_ref=sprint_ref)


def _asks_project_summary(normalized: str) -> bool:
    return bool(
        re.search(
            r"\b(resumen|resume|resumir|resúmen|panorama|estado general)\b",
            normalized,
        )
    )


def _strip_leading_greeting(normalized: str) -> str:
    """Remove leading salutations so the functional tail can be classified."""
    remainder = normalized
    for _ in range(4):
        stripped = re.sub(
            r"^(?:hola|hey|buenas)(?:\s+gemini)?(?:\s+asistente)?(?:\s+dashnode)?[,.!?\s]+",
            "",
            remainder,
            count=1,
        )
        stripped = re.sub(
            r"^(?:buenos dias|buenas tardes|buenas noches)[,.!?\s]+",
            "",
            stripped,
            count=1,
        )
        if stripped == remainder:
            break
        remainder = stripped.strip()
    return remainder


def _has_functional_request(normalized: str) -> bool:
    """True when the utterance asks for DashNode data or a deterministic action."""
    if not normalized:
        return False
    for segment in (normalized, _strip_leading_greeting(normalized)):
        if not segment:
            continue
        if (
            _asks_project_summary(segment)
            or _matches_projects(segment)
            or _asks_count_stories(segment)
            or (_asks_members(segment) and _asks_all_projects_scope(segment))
            or _asks_gemini_grounded(segment)
            or _asks_hu_analysis(segment)
            or _asks_documentation(segment)
            or _asks_members(segment)
            or _asks_stories(segment)
            or _asks_sprints(segment)
            or _asks_tasks(segment)
            or _is_bare_hu_query(segment)
        ):
            return True
        if re.search(
            r"(dime|dame|muestrame|mostrar|lista|listar|necesito saber|quiero saber|"
            r"cuales son|cuales|que tiene|quienes integran|quien integra)",
            segment,
        ) and re.search(
            r"\b(hu|hus|historias?|miembros|integrantes|tareas|sprints?|proyecto|proyectos)\b",
            segment,
        ):
            return True
    return False


def _is_bare_hu_query(normalized: str) -> bool:
    return normalized in {
        "hu",
        "hus",
        "historias",
        "historias de usuario",
        "historia de usuario",
    }


def _is_chitchat(normalized: str) -> bool:
    if _has_functional_request(normalized):
        return False
    remainder = _strip_leading_greeting(normalized)
    if remainder and _has_functional_request(remainder):
        return False
    if re.search(
        r"\b(como estas|como vas|que tal|gracias|necesito ayuda)\b",
        normalized,
    ):
        return True
    if re.match(
        r"^(hola|hey|buenas)(?:\s+gemini)?(?:\s+asistente)?(?:\s+dashnode)?[!.?,\s]*$",
        normalized,
    ):
        return True
    if remainder and re.match(
        r"^(como estas|como vas|que tal|necesito ayuda)[!.?,\s]*$",
        remainder,
    ):
        return True
    return bool(
        re.match(
            r"^(buenos dias|buenas tardes|buenas noches)[!.?,\s]*$",
            normalized,
        )
    )


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
        re.search(
            r"(miembros|integrantes|equipo|quienes participan|quien forma parte|"
            r"quienes integran|quien integra|quienes forman)",
            normalized,
        )
    )


def _asks_all_projects_scope(normalized: str) -> bool:
    return bool(
        re.search(
            r"(cada proyecto|todos los proyectos|todos mis proyectos|en cada proyecto|"
            r"por proyecto|en todos|todos mis projectos)",
            normalized,
        )
    )


def _asks_hu_analysis(normalized: str) -> bool:
    has_hu = bool(re.search(r"\b(hu|hus|historias? de usuario|historias)\b", normalized))
    has_advice = bool(
        re.search(
            r"(mejorar|mejora|recomend|suger|analiz|optimiz|que falta|como puedo|qué falta)",
            normalized,
        )
    )
    return has_hu and has_advice


def _asks_gemini_grounded(normalized: str) -> bool:
    wants_gemini = bool(
        re.search(
            r"(preguntale a gemini|pregunta a gemini|consulta gemini|preguntar a gemini|"
            r"que diga gemini|que responda gemini)",
            normalized,
        )
    )
    if not wants_gemini:
        return False
    return bool(
        re.search(
            r"\b(hu|hus|historias?|miembros|integrantes|tareas|sprints?|proyecto)\b",
            normalized,
        )
    )


def _asks_sprints(normalized: str) -> bool:
    return "sprint" in normalized and not _asks_stories(normalized)


def _asks_stories(normalized: str) -> bool:
    if _asks_count_stories(normalized):
        return False
    if _asks_hu_analysis(normalized):
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


_EN_REF_STOPWORDS = frozenset(
    {
        "las",
        "los",
        "la",
        "el",
        "cada",
        "todos",
        "mis",
        "ese",
        "esa",
        "este",
        "esta",
        "les",
        "hus",
        "hu",
        "historias",
    }
)


def _clean_project_ref(ref: str | None) -> str | None:
    if ref is None:
        return None
    cleaned = ref.strip().strip("\"'“”")
    lowered = cleaned.lower()
    if lowered.startswith("de "):
        cleaned = cleaned[3:].strip()
    if lowered.startswith("del "):
        cleaned = cleaned[4:].strip()
    return cleaned or None


def _extract_project_ref(text: str, open_project_name: str | None) -> str | None:
    normalized = normalize_text(text)
    if _mentions_this_project(normalized) and open_project_name:
        return open_project_name
    quoted = re.findall(r"[\"“](.+?)[\"”]", text)
    if quoted:
        return str(quoted[0].strip())
    de_match = re.search(
        r"(?:proyecto|project)\s+de\s+([a-zA-Z0-9][a-zA-Z0-9 \-_]{1,50})",
        text,
        flags=re.IGNORECASE,
    )
    if de_match:
        return de_match.group(1).strip()
    hu_de_match = re.search(
        r"(?:hus|historias(?:\s+de\s+usuario)?)\s+(?:de|del)\s+"
        r"([a-zA-Z0-9][a-zA-Z0-9 \-_]{1,50})",
        text,
        flags=re.IGNORECASE,
    )
    if hu_de_match:
        return hu_de_match.group(1).strip()
    improve_de_match = re.search(
        r"(?:mejorar|mejora|recomend(?:ar|aciones)?|analiz(?:ar|a)?)\s+.*?\b(?:de|del)\s+"
        r"([a-zA-Z0-9][a-zA-Z0-9 \-_]{1,50})\s*[.!?]?$",
        text,
        flags=re.IGNORECASE,
    )
    if improve_de_match:
        return improve_de_match.group(1).strip()
    trailing_de_match = re.search(
        r"\bde\s+([a-zA-Z0-9][a-zA-Z0-9 \-_]{1,50})\s*[.!?]?$",
        text,
        flags=re.IGNORECASE,
    )
    if trailing_de_match:
        return trailing_de_match.group(1).strip()
    resume_short = re.search(
        r"\b(?:resume|resumen|resumir)\s+(?:el\s+)?(?:proyecto\s+)?"
        r"([a-zA-Z0-9][a-zA-Z0-9 \-_]{1,50})\s*[.!?]?$",
        text,
        flags=re.IGNORECASE,
    )
    if resume_short:
        return resume_short.group(1).strip()
    tiene_match = re.search(
        r"\b(?:tiene|tienen)\s+([a-zA-Z0-9][a-zA-Z0-9 \-_]{1,50})\s*[.!?]?$",
        text,
        flags=re.IGNORECASE,
    )
    if tiene_match:
        return tiene_match.group(1).strip()
    integran_match = re.search(
        r"\b(?:integran|integra)\s+([a-zA-Z0-9][a-zA-Z0-9 \-_]{1,50})\s*[.!?]?$",
        text,
        flags=re.IGNORECASE,
    )
    if integran_match:
        return integran_match.group(1).strip()
    resumen_match = re.search(
        r"resumen\s+(?:del\s+)?(?:proyecto\s+)?(?:de\s+)?([a-zA-Z0-9][a-zA-Z0-9 \-_]{1,50})",
        text,
        flags=re.IGNORECASE,
    )
    if resumen_match:
        return resumen_match.group(1).strip()
    match = re.search(
        r"(?:mi\s+)?(?:proyecto|project)\s+([a-zA-Z0-9][a-zA-Z0-9 \-_]{1,40}?)"
        r"(?:\s+ah[ií]|\s+alli|\s+all[ií]|$|[,.!?])",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    en_match = re.search(
        r"\ben\s+([a-zA-Z0-9][a-zA-Z0-9\-_]{2,40})\b",
        text,
        flags=re.IGNORECASE,
    )
    if en_match:
        candidate = en_match.group(1).strip()
        if normalize_text(candidate) not in _EN_REF_STOPWORDS:
            return candidate
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


def _summary_conversational_index(normalized: str, last_project_names: list[str]) -> int | None:
    if not last_project_names:
        return None
    if re.search(r"\b(proyecto anterior|el anterior|la anterior|ultimo proyecto)\b", normalized):
        return 0
    return _conversational_index(normalized, last_project_names)
