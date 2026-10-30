"""End-to-end assistant query pipeline (intent → resolve → query → answer)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.orm import Session

from app.modules.ai.application.assistant.assistant_metrics import AssistantRequestMetrics
from app.modules.ai.application.assistant.conversation_state import ConversationStateStore
from app.modules.ai.application.assistant.data_queries import AssistantDataService
from app.modules.ai.application.assistant.entity_resolver import (
    ProjectCandidate,
    SprintCandidate,
    find_project_name_in_utterance,
    resolve_project,
    resolve_sprint_by_ref,
)
from app.modules.ai.application.assistant.intent_models import (
    ClarificationNeeded,
    IntentType,
    ParsedIntent,
)
from app.modules.ai.application.assistant.intent_parser import parse_intent
from app.modules.ai.application.assistant.metrics_generation import MetricsGenerationPort
from app.modules.ai.application.assistant.text_normalize import normalize_text
from app.modules.ai.domain.errors import GeminiProcessingError, QuotaExhaustedError
from app.modules.ai.domain.ports import GenerationPort, QuotaPort

logger = logging.getLogger(__name__)

_PROJECT_INTENTS = frozenset(
    {
        IntentType.LIST_PROJECT_MEMBERS,
        IntentType.LIST_SPRINTS,
        IntentType.LIST_SPRINT_STORIES,
        IntentType.COUNT_PROJECT_HUS,
        IntentType.LIST_TASKS,
        IntentType.LIST_DOCUMENTATION,
        IntentType.PROJECT_FOCUS,
    }
)

_T = TypeVar("_T")


class AssistantOrchestrator:
    def __init__(self, session: Session, generation: GenerationPort, quotas: QuotaPort) -> None:
        self._session = session
        self._generation = generation
        self._quotas = quotas
        self._data = AssistantDataService(session)
        self._state = ConversationStateStore(session)

    def answer(
        self,
        text: str,
        user_id: str,
        role: str,
        optional_project_id: str | None,
    ) -> str:
        started = time.perf_counter()
        metrics = AssistantRequestMetrics()
        generation = MetricsGenerationPort(self._generation, metrics)
        try:
            response = self._answer_body(
                text,
                user_id,
                role,
                optional_project_id,
                metrics,
                generation,
            )
            metrics.path = metrics.path if metrics.path != "unknown" else "deterministic"
            return response
        finally:
            metrics.orchestrator_ms = (time.perf_counter() - started) * 1000
            metrics.total_ms = metrics.orchestrator_ms
            metrics.log(user_id=user_id)

    def _db_call(
        self, metrics: AssistantRequestMetrics, fn: Callable[..., _T], *args, **kwargs
    ) -> _T:
        metrics.start_postgres()
        try:
            return fn(*args, **kwargs)
        finally:
            metrics.stop_postgres()

    def _answer_body(
        self,
        text: str,
        user_id: str,
        role: str,
        optional_project_id: str | None,
        metrics: AssistantRequestMetrics,
        generation: MetricsGenerationPort,
    ) -> str:
        state = self._db_call(metrics, self._state.load, user_id)
        open_name = None
        if optional_project_id:
            try:
                self._db_call(
                    metrics, self._data.ensure_project_access, optional_project_id, user_id, role
                )
                open_name = self._db_call(metrics, self._data.project_name, optional_project_id)
            except (PermissionError, LookupError):
                open_name = None

        projects = self._db_call(metrics, self._data.accessible_projects, user_id, role)
        candidates = [ProjectCandidate(row.id, row.name) for row in projects]

        parse_started = time.perf_counter()
        intent = parse_intent(
            text,
            open_project_name=open_name,
            last_project_names=list(state.get("last_project_names", [])),
        )
        metrics.intent_parse_ms = (time.perf_counter() - parse_started) * 1000

        resolve_started = time.perf_counter()
        intent = self._enrich_intent(text, intent, candidates)
        metrics.entity_resolve_ms = (time.perf_counter() - resolve_started) * 1000
        metrics.path = intent.intent.value

        if intent.intent == IntentType.CHITCHAT:
            return (
                "Hola. Soy el asistente de DashNode. Puedo consultar sus proyectos, miembros, "
                "sprints, historias de usuario, tareas y documentación autorizados."
            )

        if intent.intent == IntentType.LIST_PROJECTS:
            if not projects:
                return "No tiene proyectos visibles en DashNode."
            lines = [f"Tienes {len(projects)} proyecto(s):"]
            for project in projects:
                hu, tasks, members = self._db_call(metrics, self._data.count_metrics, project.id)
                lines.append(f"- {project.name} ({hu} HUs, {tasks} tareas, {members} miembros)")
            self._db_call(
                metrics,
                self._state.save,
                user_id,
                {
                    "last_project_ids": [p.id for p in projects],
                    "last_project_names": [p.name for p in projects],
                },
            )
            return "\n".join(lines)

        if intent.intent == IntentType.UNKNOWN:
            metrics.path = "gemini_fallback"
            return self._fallback_llm(text, user_id, projects, generation)

        project_id = self._resolve_project_id(intent, optional_project_id, candidates, state)
        if project_id is None:
            raise ClarificationNeeded(
                "Indique el proyecto (nombre aproximado) o abra un proyecto y use «este proyecto»."
            )

        project_name = self._db_call(metrics, self._data.project_name, project_id)
        self._remember_project(user_id, state, project_id, project_name, metrics)

        if intent.intent == IntentType.PROJECT_FOCUS:
            return self._project_summary(project_id, project_name, metrics)

        if intent.intent == IntentType.LIST_PROJECT_MEMBERS:
            members = self._db_call(metrics, self._data.list_members, project_id, user_id, role)
            if not members:
                return f"El proyecto {project_name} no tiene miembros registrados."
            return f"Miembros de {project_name}:\n" + "\n".join(f"- {m}" for m in members)

        if intent.intent == IntentType.LIST_SPRINTS:
            sprints = self._db_call(metrics, self._data.list_sprints, project_id, user_id, role)
            if not sprints:
                return f"El proyecto {project_name} no tiene sprints registrados."
            return f"Sprints de {project_name}:\n" + "\n".join(f"- {s}" for s in sprints)

        if intent.intent == IntentType.COUNT_PROJECT_HUS:
            hu_count, _, _ = self._db_call(metrics, self._data.count_metrics, project_id)
            return f"El proyecto {project_name} tiene {hu_count} historia(s) de usuario."

        if intent.intent == IntentType.LIST_SPRINT_STORIES:
            sprint_id = self._resolve_sprint_id(intent, project_id, metrics)
            stories = self._db_call(
                metrics,
                self._data.list_stories,
                project_id,
                user_id,
                role,
                sprint_id=sprint_id,
            )
            if not stories:
                scope = "ese sprint" if sprint_id else project_name
                return f"No hay historias de usuario registradas para {scope}."
            header = f"Historias de usuario — {project_name}"
            if sprint_id:
                header += " (sprint filtrado)"
            return header + ":\n" + "\n".join(f"- {line}" for line in stories)

        if intent.intent == IntentType.LIST_TASKS:
            lines = self._db_call(
                metrics,
                self._data.list_tasks,
                project_id,
                user_id,
                role,
                task_filter=intent.task_filter.value,
            )
            if not lines:
                return f"No hay tareas que coincidan con el filtro solicitado en {project_name}."
            return f"Tareas en {project_name}:\n" + "\n".join(f"- {line}" for line in lines)

        if intent.intent == IntentType.LIST_DOCUMENTATION:
            docs = self._db_call(metrics, self._data.list_documentation, project_id, user_id, role)
            if not docs:
                return f"El proyecto {project_name} no tiene documentación visible para usted."
            return f"Documentación de {project_name}:\n" + "\n".join(f"- {d}" for d in docs)

        return (
            "Puedo ayudarle a consultar proyectos, miembros, sprints, HUs, tareas o documentación. "
            "Reformule su pregunta con más detalle."
        )

    def _enrich_intent(
        self,
        text: str,
        intent: ParsedIntent,
        candidates: list[ProjectCandidate],
    ) -> ParsedIntent:
        needs_project = intent.intent in _PROJECT_INTENTS or (
            intent.intent == IntentType.UNKNOWN and intent.project_ref
        )
        if needs_project and not intent.project_ref and intent.intent != IntentType.UNKNOWN:
            embedded = find_project_name_in_utterance(text, candidates)
            if embedded.ambiguous:
                names = ", ".join(item.name for item in embedded.ambiguous[:5])
                raise ClarificationNeeded(
                    f"Hay varios proyectos similares: {names}. ¿Cuál desea consultar?"
                )
            if embedded.value:
                return intent.model_copy(update={"project_ref": embedded.value.name})

        if intent.intent == IntentType.UNKNOWN:
            embedded = find_project_name_in_utterance(text, candidates)
            normalized = normalize_text(text)
            word_count = len(normalized.split())
            if embedded.value and word_count <= 3 and embedded.score >= 90:
                return ParsedIntent(
                    intent=IntentType.PROJECT_FOCUS,
                    project_ref=embedded.value.name,
                )
            if embedded.value and not embedded.ambiguous and word_count <= 6:
                return intent.model_copy(update={"project_ref": embedded.value.name})
        return intent

    def _project_summary(
        self, project_id: str, project_name: str, metrics: AssistantRequestMetrics
    ) -> str:
        hu, tasks, members = self._db_call(metrics, self._data.count_metrics, project_id)
        return (
            f"{project_name}: {hu} HUs, {tasks} tareas, {members} miembros. "
            "Puede preguntar por historias de usuario, tareas pendientes, miembros o sprints."
        )

    def _remember_project(
        self,
        user_id: str,
        state: dict,
        project_id: str,
        project_name: str,
        metrics: AssistantRequestMetrics,
    ) -> None:
        ids = list(state.get("last_project_ids", []))
        names = list(state.get("last_project_names", []))
        if project_id in ids:
            idx = ids.index(project_id)
            ids.pop(idx)
            names.pop(idx)
        ids.insert(0, project_id)
        names.insert(0, project_name)
        self._db_call(
            metrics,
            self._state.save,
            user_id,
            {"last_project_ids": ids[:10], "last_project_names": names[:10]},
        )

    def _resolve_project_id(
        self,
        intent: ParsedIntent,
        optional_project_id: str | None,
        candidates: list[ProjectCandidate],
        state: dict,
    ) -> str | None:
        if intent.conversational_index is not None:
            ids = list(state.get("last_project_ids", []))
            if intent.conversational_index < len(ids):
                return ids[intent.conversational_index]

        if intent.use_open_project and optional_project_id:
            return optional_project_id

        if intent.project_ref:
            resolved = resolve_project(intent.project_ref, candidates)
            if resolved.ambiguous:
                names = ", ".join(item.name for item in resolved.ambiguous[:5])
                raise ClarificationNeeded(
                    f"Hay varios proyectos similares: {names}. ¿Cuál desea consultar?"
                )
            if resolved.value:
                return resolved.value.id
            return None

        if intent.intent in _PROJECT_INTENTS and len(candidates) == 1:
            return candidates[0].id
        return None

    def _resolve_sprint_id(
        self, intent: ParsedIntent, project_id: str, metrics: AssistantRequestMetrics
    ) -> str | None:
        if not intent.sprint_ref:
            return None
        sprint_rows = self._db_call(metrics, self._data.sprint_candidates, project_id)
        candidates = [
            SprintCandidate(sid, name, project_id) for sid, name in sprint_rows
        ]
        resolved = resolve_sprint_by_ref(intent.sprint_ref, candidates)
        if resolved.ambiguous:
            names = ", ".join(item.name for item in resolved.ambiguous[:5])
            raise ClarificationNeeded(f"Hay varios sprints similares: {names}. ¿Cuál desea?")
        return resolved.value.id if resolved.value else None

    def _fallback_llm(
        self,
        text: str,
        user_id: str,
        projects: list,
        generation: MetricsGenerationPort,
    ) -> str:
        names = ", ".join(p.name for p in projects[:8]) or "ninguno"
        prompt = (
            "Asistente DashNode. Español, máximo 2 oraciones.\n"
            f"Proyectos visibles: {names}.\n"
            f"Pregunta: {text.strip()}\n"
            "Si falta contexto, pida detalle sobre proyectos, HUs, tareas o sprints."
        )
        try:
            self._quotas.check_and_consume("GEMINI")
            return generation.generate(prompt).strip()
        except QuotaExhaustedError:
            raise
        except GeminiProcessingError as exc:
            logger.warning(
                "assistant_gemini_fallback_failed user_id=%s reason=%s",
                user_id,
                str(exc),
            )
            return (
                "No pude procesar la consulta con IA en este momento. Intente preguntar, por "
                "ejemplo: «¿Cuáles son mis proyectos?» o «Lista las HUs del sprint 1»."
            )
