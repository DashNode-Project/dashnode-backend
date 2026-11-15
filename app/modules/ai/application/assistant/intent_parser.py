"""Deterministic Spanish intent parsing (no LLM required for core queries)."""

from __future__ import annotations

import re

from app.modules.ai.application.assistant.intent_models import (
    IntentType,
    MeetingFilter,
    ParsedIntent,
    TaskFilter,
)
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

    if _asks_project_opinion(normalized):
        return ParsedIntent(
            intent=IntentType.PROJECT_ANALYSIS,
            project_ref=project_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _asks_explain_user_story_writing(normalized):
        return ParsedIntent(
            intent=IntentType.EXPLAIN_USER_STORY_WRITING,
            project_ref=project_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _asks_generate_user_story_examples(normalized):
        return ParsedIntent(
            intent=IntentType.GENERATE_USER_STORY_EXAMPLES,
            project_ref=project_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
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

    if _asks_hu_improve(normalized):
        return ParsedIntent(
            intent=IntentType.IMPROVE_USER_STORIES,
            project_ref=project_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _asks_hu_review(normalized):
        return ParsedIntent(
            intent=IntentType.REVIEW_USER_STORIES,
            project_ref=project_ref,
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _asks_analyze_document(normalized):
        return ParsedIntent(
            intent=IntentType.ANALYZE_DOCUMENT,
            project_ref=project_ref,
            document_ref=_extract_document_ref(raw),
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _asks_count_meetings(normalized):
        return ParsedIntent(
            intent=IntentType.COUNT_MEETINGS,
            project_ref=project_ref,
            meeting_filter=_meeting_filter(normalized),
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _asks_meetings(normalized):
        return ParsedIntent(
            intent=IntentType.LIST_MEETINGS,
            project_ref=project_ref,
            meeting_filter=_meeting_filter(normalized),
            use_open_project=project_ref is None and _mentions_this_project(normalized),
        )

    if _asks_documentation(normalized) and not _asks_analyze_document(normalized):
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
        return ParsedIntent(intent=IntentType.GREETING)

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


def has_functional_request(normalized: str) -> bool:
    return _has_functional_request(normalized)


def asks_hu_analysis(normalized: str) -> bool:
    return _asks_hu_analysis(normalized)


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
            or _asks_hu_review(segment)
            or _asks_hu_improve(segment)
            or _asks_explain_user_story_writing(segment)
            or _asks_generate_user_story_examples(segment)
            or _asks_project_opinion(segment)
            or _asks_analyze_document(segment)
            or _asks_documentation(segment)
            or _asks_members(segment)
            or _asks_stories(segment)
            or _asks_sprints(segment)
            or _asks_meetings(segment)
            or _asks_count_meetings(segment)
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
    return _asks_hu_review(normalized) or _asks_hu_improve(normalized)


def _asks_hu_review(normalized: str) -> bool:
    has_hu = bool(re.search(r"\b(hu|hus|historias? de usuario|historias)\b", normalized))
    has_review = bool(
        re.search(
            r"(redactad|evalu|revis|calidad|claridad|ambig|verificab|consistenc|estructur|"
            r"bien escrita|bien formulada|estan bien|están bien|si estan|si están|"
            r"como estan redactad|como están redactad|analiz.*historias)",
            normalized,
        )
    )
    return has_hu and has_review and not _asks_hu_improve(normalized)


def _asks_hu_improve(normalized: str) -> bool:
    has_hu = bool(re.search(r"\b(hu|hus|historias? de usuario|historias)\b", normalized))
    has_improve = bool(
        re.search(
            r"(mejorar|mejora|recomend|suger|optimiz|que falta|como puedo|que mejorar|"
            r"que mejorarias)",
            normalized,
        )
    )
    return has_hu and has_improve


def _asks_explain_user_story_writing(normalized: str) -> bool:
    if _asks_generate_user_story_examples(normalized):
        return False
    return bool(
        re.search(
            r"(como redact|como escrib|explic.*historia|formato de.*historia|"
            r"diferencia entre.*historia|que es una hu|que es una historia de usuario)",
            normalized,
        )
    )


def _asks_generate_user_story_examples(normalized: str) -> bool:
    return bool(
        re.search(
            r"(ejemplo|ejemplos|muestrame.*historia|dame.*historia)",
            normalized,
        )
        and re.search(r"\b(hu|hus|historias? de usuario|historias)\b", normalized)
        and not _asks_hu_review(normalized)
    )


def _asks_project_opinion(normalized: str) -> bool:
    if _asks_hu_analysis(normalized) or _asks_analyze_document(normalized):
        return False
    return bool(
        re.search(
            r"(que opinas|que piensas|que te parece|evalua el proyecto|analiza el proyecto|"
            r"vision general del proyecto)",
            normalized,
        )
    )


def _asks_analyze_document(normalized: str) -> bool:
    has_doc = bool(re.search(r"(documento|documentacion|doc)\b", normalized))
    has_action = bool(
        re.search(
            r"(analiza|resume|resumir|de que trata|que tecnolog|componentes|riesgos|"
            r"recomendaciones sobre)",
            normalized,
        )
    )
    return has_doc and has_action


def _asks_meetings(normalized: str) -> bool:
    return bool(re.search(r"\b(reunion|reuniones|meeting|meetings)\b", normalized))


def _asks_count_meetings(normalized: str) -> bool:
    return _asks_meetings(normalized) and bool(
        re.search(r"(cuant(a|o)s|numero de|cantidad de|cuenta)", normalized)
    )


def _meeting_filter(normalized: str) -> MeetingFilter:
    if re.search(r"cancelad", normalized):
        return MeetingFilter.CANCELLED
    if re.search(r"(finaliz|completad|terminad)", normalized):
        return MeetingFilter.COMPLETED
    if re.search(r"(confirm|confirmacion)", normalized):
        return MeetingFilter.PENDING_CONFIRMATION
    if re.search(r"(proxim|siguiente)", normalized):
        return MeetingFilter.UPCOMING
    if re.search(r"pendient", normalized):
        return MeetingFilter.USER_PENDING
    if re.search(r"\btodas\b", normalized):
        return MeetingFilter.ALL
    return MeetingFilter.UPCOMING


def _extract_document_ref(text: str) -> str | None:
    normalized = normalize_text(text)
    match = re.search(
        r"documento(?: de)?\s+([a-z0-9\s\-]{3,80})",
        normalized,
    )
    if match:
        return match.group(1).strip()
    return None


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
    if _asks_meetings(normalized):
        return False
    if re.search(r"\b(reunion|reuniones)\b", normalized):
        return False
    if re.search(r"\b(tarea|tareas|tasks)\b", normalized):
        return True
    if re.search(r"tengo pendiente", normalized):
        return True
    if re.search(r"\b(pendiente|pendientes|por hacer)\b", normalized):
        return bool(re.search(r"\b(tarea|tareas)\b", normalized))
    return False


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
    de_mi_proyecto = re.search(
        r"\bde\s+(?:mi\s+)?proyecto\s+([A-Za-z0-9][A-Za-z0-9 \-_]{1,50}?)"
        r"(?=\s+(?:est[aá]n|tiene|tienen|hay\b|de\s+las|de\s+los)|[,.!?]|$)",
        text,
        flags=re.IGNORECASE,
    )
    if de_mi_proyecto:
        return de_mi_proyecto.group(1).strip()
    hu_de_match = re.search(
        r"(?:hus|historias(?:\s+de\s+usuario)?)\s+(?:de|del)\s+(?!usuario\b)(?:mi\s+proyecto\s+)?"
        r"([A-Za-z0-9][A-Za-z0-9 \-_]{1,50}?)"
        r"(?=\s+(?:est[aá]n|tiene|tienen|hay\b|de\s+las)|[,.!?]|$)",
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
        r"(?:mi\s+)?(?:proyecto|project)\s+([A-Za-z0-9][A-Za-z0-9 \-_]{0,50}?)"
        r"(?=\s+(?:de\s+las|de\s+los|del?\s|\ben\b|est[aá]n|tiene|tienen|hay\b|"
        r"est[aá]n\s+bien|sin\s+|con\s+|ah[ií]|alli|all[ií])|[,.!?]|$)",
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
