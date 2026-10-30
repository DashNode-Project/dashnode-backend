"""End-to-end assistant query pipeline (intent → resolve → query → answer)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.modules.ai.application.assistant.assistant_metrics import AssistantRequestMetrics
from app.modules.ai.application.assistant.conversation_state import ConversationStateStore
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
from app.modules.ai.application.assistant.intent_parser import (
    asks_hu_analysis,
    has_functional_request,
    parse_intent,
)
from app.modules.ai.application.assistant.metrics_generation import MetricsGenerationPort
from app.modules.ai.application.assistant.text_normalize import normalize_text
from app.modules.ai.application.prompt_builder import (
    build_assistant_prompt,
    build_document_analysis_prompt,
    build_hu_analysis_prompt,
    build_hu_improvement_prompt,
    build_project_analysis_prompt,
    build_user_story_education_prompt,
    build_user_story_examples_prompt,
)
from app.modules.ai.domain.errors import GeminiProcessingError, QuotaExhaustedError
from app.modules.ai.domain.ports import AssistantDataPort, GenerationPort, QuotaPort
from app.shared.infrastructure.ai_request_trace import log_ai_stage

logger = logging.getLogger(__name__)

_PROJECT_INTENTS = frozenset(
    {
        IntentType.LIST_PROJECT_MEMBERS,
        IntentType.LIST_SPRINTS,
        IntentType.LIST_SPRINT_STORIES,
        IntentType.COUNT_PROJECT_HUS,
        IntentType.LIST_TASKS,
        IntentType.LIST_DOCUMENTATION,
        IntentType.LIST_MEETINGS,
        IntentType.COUNT_MEETINGS,
        IntentType.PROJECT_FOCUS,
        IntentType.PROJECT_SUMMARY,
        IntentType.ANALYZE_USER_STORIES,
        IntentType.REVIEW_USER_STORIES,
        IntentType.IMPROVE_USER_STORIES,
        IntentType.GENERATE_USER_STORY_EXAMPLES,
        IntentType.PROJECT_ANALYSIS,
        IntentType.ANALYZE_DOCUMENT,
        IntentType.GEMINI_GROUNDED,
    }
)

_OPTIONAL_PROJECT_INTENTS = frozenset(
    {
        IntentType.LIST_MEETINGS,
        IntentType.COUNT_MEETINGS,
        IntentType.GENERATE_USER_STORY_EXAMPLES,
    }
)

_LLM_PROJECT_INTENTS = frozenset(
    {
        IntentType.ANALYZE_USER_STORIES,
        IntentType.REVIEW_USER_STORIES,
        IntentType.IMPROVE_USER_STORIES,
        IntentType.PROJECT_ANALYSIS,
        IntentType.ANALYZE_DOCUMENT,
        IntentType.GENERATE_USER_STORY_EXAMPLES,
        IntentType.GEMINI_GROUNDED,
    }
)


class AssistantOrchestrator:
    def __init__(
        self,
        session: Session,
        generation: GenerationPort,
        quotas: QuotaPort,
        data: AssistantDataPort,
    ) -> None:
        self._session = session
        self._generation = generation
        self._quotas = quotas
        self._data = data
        self._state = ConversationStateStore(session)

    def answer(
        self,
        text: str,
        user_id: str,
        role: str,
        optional_project_id: str | None,
    ) -> str:
        log_ai_stage("orchestrator_enter", user_id=user_id)
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
        except SQLAlchemyError:
            logger.exception("assistant_db_error user_id=%s", user_id)
            return (
                "No pude recuperar la información del proyecto en este momento. "
                "Intente de nuevo más tarde."
            )
        except PermissionError:
            return "No tiene permiso para acceder a ese proyecto."
        except LookupError:
            return "El proyecto indicado no existe o ya no está disponible."
        finally:
            metrics.orchestrator_ms = (time.perf_counter() - started) * 1000
            metrics.total_ms = metrics.orchestrator_ms
            metrics.log(user_id=user_id)

    def _db_call(
        self,
        metrics: AssistantRequestMetrics,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
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
        log_ai_stage("intent_parsed", intent=intent.intent.value)

        if intent.intent in {IntentType.CHITCHAT, IntentType.GREETING}:
            return (
                "Hola. Soy el asistente de DashNode. Puedo consultar sus proyectos, miembros, "
                "sprints, historias de usuario, tareas, reuniones y documentación autorizados."
            )

        if intent.intent == IntentType.EXPLAIN_USER_STORY_WRITING:
            metrics.path = "gemini_education"
            return self._llm_user_story_education(text, generation, metrics, domain_hint=None)

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

        if intent.intent == IntentType.LIST_ALL_PROJECT_MEMBERS:
            if not projects:
                return "No tiene proyectos visibles en DashNode."
            blocks: list[str] = ["Miembros por proyecto:"]
            for project in projects:
                members = self._db_call(metrics, self._data.list_members, project.id, user_id, role)
                if members:
                    blocks.append(f"\n{project.name}:\n" + "\n".join(f"- {m}" for m in members))
                else:
                    blocks.append(f"\n{project.name}: sin miembros registrados.")
            return "\n".join(blocks)

        if intent.intent == IntentType.UNKNOWN:
            if intent.project_ref:
                project_id = self._resolve_project_id(
                    intent, optional_project_id, candidates, state
                )
                if project_id is not None:
                    metrics.path = "gemini_grounded"
                    return self._gemini_with_project_context(
                        text,
                        user_id,
                        role,
                        project_id,
                        generation,
                        metrics,
                        intent=intent.intent,
                    )
            metrics.path = "gemini_fallback"
            log_ai_stage("orchestrator_gemini_fallback_enter")
            return self._fallback_llm(text, user_id, projects, generation)

        project_id = self._resolve_project_id(intent, optional_project_id, candidates, state)
        if project_id is None and intent.intent not in _OPTIONAL_PROJECT_INTENTS:
            raise ClarificationNeeded(self._clarify_project_message(intent, candidates))

        if intent.intent in _LLM_PROJECT_INTENTS and project_id is not None:
            metrics.path = "gemini_grounded"
            return self._gemini_with_project_context(
                text,
                user_id,
                role,
                project_id,
                generation,
                metrics,
                intent=intent.intent,
                document_ref=intent.document_ref,
            )

        if intent.intent == IntentType.GENERATE_USER_STORY_EXAMPLES:
            metrics.path = "gemini_examples"
            if project_id is None:
                return self._llm_user_story_examples(
                    text, user_id, role, None, generation, metrics
                )
            return self._gemini_with_project_context(
                text,
                user_id,
                role,
                project_id,
                generation,
                metrics,
                intent=intent.intent,
                document_ref=None,
            )

        if intent.intent == IntentType.LIST_MEETINGS:
            lines = self._db_call(
                metrics,
                self._data.list_meetings,
                user_id,
                role,
                project_id=project_id,
                meeting_filter=intent.meeting_filter.value,
            )
            scope = (
                self._db_call(metrics, self._data.project_name, project_id)
                if project_id
                else "sus proyectos y participación"
            )
            if not lines:
                return f"No se encontraron reuniones que coincidan con el filtro en {scope}."
            header = f"Reuniones ({scope}):"
            return header + "\n" + "\n".join(f"- {line}" for line in lines)

        if intent.intent == IntentType.COUNT_MEETINGS:
            count = self._db_call(
                metrics,
                self._data.count_meetings,
                user_id,
                role,
                project_id=project_id,
                meeting_filter=intent.meeting_filter.value,
            )
            scope = (
                self._db_call(metrics, self._data.project_name, project_id)
                if project_id
                else "su ámbito visible"
            )
            return f"Hay {count} reunión(es) que coinciden con el filtro en {scope}."

        if project_id is None:
            raise ClarificationNeeded(self._clarify_project_message(intent, candidates))

        project_name = self._db_call(metrics, self._data.project_name, project_id)
        self._remember_project(user_id, state, project_id, project_name, metrics)

        if intent.intent == IntentType.PROJECT_SUMMARY:
            return self._project_summary_detailed(project_id, project_name, user_id, role, metrics)

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
                hu_count, _, _ = self._db_call(metrics, self._data.count_metrics, project_id)
                scope = "ese sprint" if sprint_id else project_name
                if hu_count > 0 and sprint_id:
                    return (
                        f"No hay historias de usuario en el sprint indicado para {project_name}, "
                        f"pero el proyecto tiene {hu_count} HU(s) en total."
                    )
                if hu_count > 0:
                    return (
                        f"No pude listar historias de usuario para {scope}, pero la base de datos "
                        f"registra {hu_count} HU(s). Intente de nuevo o reformule la consulta."
                    )
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
        if intent.intent in _LLM_PROJECT_INTENTS:
            needs_project = intent.intent not in _OPTIONAL_PROJECT_INTENTS
        if needs_project and not intent.project_ref and intent.intent != IntentType.UNKNOWN:
            embedded = find_project_name_in_utterance(text, candidates)
            if embedded.ambiguous:
                names = ", ".join(item.name for item in embedded.ambiguous[:5])
                raise ClarificationNeeded(
                    f"Hay varios proyectos similares: {names}. ¿Cuál desea consultar?"
                )
            if embedded.value:
                return intent.model_copy(update={"project_ref": embedded.value.name})

        normalized = normalize_text(text)
        if intent.intent == IntentType.UNKNOWN:
            embedded = find_project_name_in_utterance(text, candidates)
            word_count = len(normalized.split())
            if embedded.value and word_count <= 3 and embedded.score >= 90:
                return ParsedIntent(
                    intent=IntentType.PROJECT_FOCUS,
                    project_ref=embedded.value.name,
                )
            if embedded.value and not embedded.ambiguous and has_functional_request(normalized):
                if asks_hu_analysis(normalized):
                    intent_kind = (
                        IntentType.IMPROVE_USER_STORIES
                        if "mejor" in normalized
                        else IntentType.REVIEW_USER_STORIES
                    )
                    return ParsedIntent(
                        intent=intent_kind,
                        project_ref=embedded.value.name,
                    )
                return ParsedIntent(
                    intent=IntentType.GEMINI_GROUNDED,
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

    def _project_summary_detailed(
        self,
        project_id: str,
        project_name: str,
        user_id: str,
        role: str,
        metrics: AssistantRequestMetrics,
    ) -> str:
        summary = self._db_call(metrics, self._data.project_summary, project_id, user_id, role)
        lines = [f"Resumen de {summary.name}:"]
        if summary.description:
            lines.append(f"- Descripción: {summary.description}")
        lines.append(f"- Estado: {summary.status}")
        lines.append(f"- Miembros: {summary.member_count}")
        lines.append(f"- Historias de usuario: {summary.hu_count}")
        lines.append(f"- Tareas: {summary.task_count}")
        lines.append(f"- Sprints registrados: {summary.sprint_count}")
        return "\n".join(lines)

    def _remember_project(
        self,
        user_id: str,
        state: dict[str, Any],
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
        state: dict[str, Any],
    ) -> str | None:
        if intent.conversational_index is not None:
            ids = list(state.get("last_project_ids", []))
            if intent.conversational_index < len(ids):
                project_id = ids[intent.conversational_index]
                return str(project_id)

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
        candidates = [SprintCandidate(sid, name, project_id) for sid, name in sprint_rows]
        resolved = resolve_sprint_by_ref(intent.sprint_ref, candidates)
        if resolved.ambiguous:
            names = ", ".join(item.name for item in resolved.ambiguous[:5])
            raise ClarificationNeeded(f"Hay varios sprints similares: {names}. ¿Cuál desea?")
        return resolved.value.id if resolved.value else None

    def _clarify_project_message(
        self, intent: ParsedIntent, candidates: list[ProjectCandidate]
    ) -> str:
        names = ", ".join(item.name for item in candidates[:6])
        if intent.intent in {
            IntentType.ANALYZE_USER_STORIES,
            IntentType.REVIEW_USER_STORIES,
            IntentType.IMPROVE_USER_STORIES,
        }:
            return (
                "Indique sobre qué proyecto desea trabajar las historias de usuario "
                f"(por ejemplo: {names})."
            )
        if intent.intent == IntentType.ANALYZE_DOCUMENT:
            return (
                "Indique el proyecto al que pertenece el documento que desea analizar "
                f"(por ejemplo: {names})."
            )
        if intent.intent == IntentType.GEMINI_GROUNDED:
            return (
                "Indique el proyecto sobre el que desea consultar con Gemini "
                f"(por ejemplo: {names})."
            )
        return "Indique el proyecto (nombre aproximado) o abra un proyecto y use «este proyecto»."

    def _gemini_with_project_context(
        self,
        text: str,
        user_id: str,
        role: str,
        project_id: str,
        generation: MetricsGenerationPort,
        metrics: AssistantRequestMetrics,
        *,
        intent: IntentType = IntentType.GEMINI_GROUNDED,
        document_ref: str | None = None,
    ) -> str:
        context = self._db_call(
            metrics, self._data.build_project_ai_context, project_id, user_id, role
        )
        if context.project_name is None:
            return (
                "No tiene acceso al proyecto solicitado o no existe. "
                "Verifique el nombre e intente de nuevo."
            )
        if intent in {
            IntentType.ANALYZE_USER_STORIES,
            IntentType.REVIEW_USER_STORIES,
            IntentType.IMPROVE_USER_STORIES,
        }:
            story_details = self._db_call(
                metrics, self._data.story_analysis_detail, project_id, user_id, role
            )
            if not story_details.strip():
                hu_count, _, _ = self._db_call(metrics, self._data.count_metrics, project_id)
                if hu_count == 0:
                    return (
                        f"No hay historias de usuario registradas en {context.project_name}. "
                        "No puedo evaluar redacción sin HUs en la base de datos."
                    )
                return (
                    f"No pude cargar el detalle de las historias de {context.project_name}. "
                    "Intente de nuevo más tarde."
                )
            if intent == IntentType.IMPROVE_USER_STORIES:
                prompt = build_hu_improvement_prompt(context, text, story_details)
            else:
                prompt = build_hu_analysis_prompt(context, text, story_details)
        elif intent == IntentType.PROJECT_ANALYSIS:
            prompt = build_project_analysis_prompt(context, text)
        elif intent == IntentType.ANALYZE_DOCUMENT:
            title, body, _has_body = self._db_call(
                metrics,
                self._data.document_for_analysis,
                project_id,
                user_id,
                role,
                title_hint=document_ref,
                user_query=text,
            )
            if not title:
                return str(body)
            prompt = build_document_analysis_prompt(
                context, text, document_title=title, document_body=body
            )
        elif intent == IntentType.GENERATE_USER_STORY_EXAMPLES:
            stories = self._db_call(
                metrics,
                self._data.list_stories,
                project_id,
                user_id,
                role,
                sprint_id=None,
            )
            titles = tuple(line.split(" — ", 1)[0] for line in stories[:20])
            domain = context.project_description or context.project_name or ""
            prompt = build_user_story_examples_prompt(
                text, domain_hint=domain, existing_titles=titles
            )
        else:
            prompt = build_assistant_prompt(context, text)
        log_ai_stage("orchestrator_gemini_grounded_enter", project=context.project_name)
        try:
            self._quotas.check_and_consume("GEMINI")
            answer = generation.generate(prompt).strip()
            log_ai_stage("orchestrator_gemini_grounded_ok", chars=len(answer))
            return answer
        except QuotaExhaustedError:
            raise
        except GeminiProcessingError as exc:
            reason = str(exc)
            logger.warning(
                "assistant_gemini_grounded_failed user_id=%s reason=%s",
                user_id,
                reason,
            )
            log_ai_stage("orchestrator_gemini_grounded_failed", reason=reason)
            if reason == "timeout":
                return (
                    "El servicio de IA tardó demasiado. Puede pedir un listado directo, por "
                    "ejemplo: «Lista las HUs de VozNotAI»."
                )
            if reason in {"auth_401", "forbidden_403", "missing_api_key"}:
                return (
                    "El asistente de IA no está configurado correctamente en el servidor. "
                    "Contacte al administrador."
                )
            if reason == "quota":
                raise QuotaExhaustedError("GEMINI") from exc
            if reason in {"all_models_failed", "all_models_cooled_down"}:
                return (
                    "El asistente de DashNode no puede procesar la consulta con IA en este "
                    "momento porque los modelos no están disponibles. Intente más tarde o use "
                    "una consulta directa (por ejemplo, listar HUs de un proyecto)."
                )
            return (
                "No pude procesar la consulta con IA en este momento. Intente una consulta "
                "directa sobre proyectos, HUs o tareas."
            )

    def _llm_user_story_education(
        self,
        text: str,
        generation: MetricsGenerationPort,
        metrics: AssistantRequestMetrics,
        *,
        domain_hint: str | None,
    ) -> str:
        prompt = build_user_story_education_prompt(text, domain_hint=domain_hint)
        try:
            self._quotas.check_and_consume("GEMINI")
            return str(generation.generate(prompt).strip())
        except QuotaExhaustedError:
            raise
        except GeminiProcessingError:
            return (
                "No pude generar la explicación con IA en este momento. "
                "Una HU suele seguir: «Como [actor], quiero [necesidad], para [valor]»."
            )

    def _llm_user_story_examples(
        self,
        text: str,
        user_id: str,
        role: str,
        project_id: str | None,
        generation: MetricsGenerationPort,
        metrics: AssistantRequestMetrics,
    ) -> str:
        domain: str | None = None
        titles: tuple[str, ...] = ()
        if project_id:
            context = self._db_call(
                metrics, self._data.build_project_ai_context, project_id, user_id, role
            )
            domain = context.project_description or context.project_name
            stories = self._db_call(
                metrics,
                self._data.list_stories,
                project_id,
                user_id,
                role,
                sprint_id=None,
            )
            titles = tuple(line.split(" — ", 1)[0] for line in stories[:20])
        prompt = build_user_story_examples_prompt(text, domain_hint=domain, existing_titles=titles)
        try:
            self._quotas.check_and_consume("GEMINI")
            return str(generation.generate(prompt).strip())
        except QuotaExhaustedError:
            raise
        except GeminiProcessingError:
            return (
                "No pude generar ejemplos con IA ahora. "
                "Marque cualquier ejemplo como propuesta educativa, no como HU real."
            )

    def _fallback_llm(
        self,
        text: str,
        user_id: str,
        projects: list[Any],
        generation: MetricsGenerationPort,
    ) -> str:
        names = ", ".join(p.name for p in projects[:8]) or "ninguno"
        prompt = (
            "Eres el asistente de DashNode (no digas que eres Gemini). "
            "Español, máximo 3 oraciones.\n"
            f"Proyectos visibles: {names}.\n"
            f"Pregunta: {text.strip()}\n"
            "Si falta contexto o proyecto, pídelo al usuario. No inventes HUs ni métricas."
        )
        try:
            self._quotas.check_and_consume("GEMINI")
            answer = generation.generate(prompt).strip()
            log_ai_stage("orchestrator_gemini_fallback_ok", chars=len(answer))
            return answer
        except QuotaExhaustedError:
            raise
        except GeminiProcessingError as exc:
            reason = str(exc)
            logger.warning(
                "assistant_gemini_fallback_failed user_id=%s reason=%s",
                user_id,
                reason,
            )
            log_ai_stage("orchestrator_gemini_fallback_failed", reason=reason)
            if reason == "timeout":
                return (
                    "El servicio de IA tardó demasiado en responder. Reformule la pregunta o "
                    "intente una consulta directa como «¿Cuáles son mis proyectos?»."
                )
            if reason in {"auth_401", "forbidden_403", "missing_api_key"}:
                return (
                    "El asistente de IA no está configurado correctamente en el servidor. "
                    "Contacte al administrador."
                )
            if reason == "quota":
                raise QuotaExhaustedError("GEMINI") from exc
            return (
                "No pude procesar la consulta con IA en este momento. Intente preguntar, por "
                "ejemplo: «¿Cuáles son mis proyectos?» o «Lista las HUs del sprint 1»."
            )
