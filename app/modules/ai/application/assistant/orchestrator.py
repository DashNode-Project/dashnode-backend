"""End-to-end assistant query pipeline (intent → resolve → query → answer)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.ai.application.assistant.conversation_state import ConversationStateStore
from app.modules.ai.application.assistant.data_queries import AssistantDataService
from app.modules.ai.application.assistant.entity_resolver import (
    ProjectCandidate,
    SprintCandidate,
    resolve_project,
    resolve_sprint_by_ref,
)
from app.modules.ai.application.assistant.intent_models import (
    ClarificationNeeded,
    IntentType,
    ParsedIntent,
    TaskFilter,
)
from app.modules.ai.application.assistant.intent_parser import parse_intent
from app.modules.ai.domain.ports import GenerationPort, QuotaPort
from app.modules.ai.domain.errors import GeminiProcessingError, QuotaExhaustedError


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
        state = self._state.load(user_id)
        open_name = None
        if optional_project_id:
            try:
                self._data.ensure_project_access(optional_project_id, user_id, role)
                open_name = self._data.project_name(optional_project_id)
            except (PermissionError, LookupError):
                open_name = None

        intent = parse_intent(
            text,
            open_project_name=open_name,
            last_project_names=list(state.get("last_project_names", [])),
        )
        projects = self._data.accessible_projects(user_id, role)
        candidates = [ProjectCandidate(row.id, row.name) for row in projects]

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
                hu, tasks, members = self._data.count_metrics(project.id)
                lines.append(f"- {project.name} ({hu} HUs, {tasks} tareas, {members} miembros)")
            self._state.save(
                user_id,
                {
                    "last_project_ids": [p.id for p in projects],
                    "last_project_names": [p.name for p in projects],
                },
            )
            return "\n".join(lines)

        project_id = self._resolve_project_id(intent, optional_project_id, candidates, state)
        if project_id is None:
            raise ClarificationNeeded(
                "Indique el proyecto (nombre aproximado) o abra un proyecto y use «este proyecto»."
            )

        project_name = self._data.project_name(project_id)

        if intent.intent == IntentType.LIST_PROJECT_MEMBERS:
            members = self._data.list_members(project_id, user_id, role)
            if not members:
                return f"El proyecto {project_name} no tiene miembros registrados."
            return f"Miembros de {project_name}:\n" + "\n".join(f"- {m}" for m in members)

        if intent.intent == IntentType.LIST_SPRINTS:
            sprints = self._data.list_sprints(project_id, user_id, role)
            if not sprints:
                return f"El proyecto {project_name} no tiene sprints registrados."
            return f"Sprints de {project_name}:\n" + "\n".join(f"- {s}" for s in sprints)

        if intent.intent == IntentType.LIST_SPRINT_STORIES:
            sprint_id = self._resolve_sprint_id(intent, project_id)
            stories = self._data.list_stories(
                project_id, user_id, role, sprint_id=sprint_id
            )
            if not stories:
                scope = "ese sprint" if sprint_id else project_name
                return f"No hay historias de usuario registradas para {scope}."
            header = f"Historias de usuario — {project_name}"
            if sprint_id:
                header += f" (sprint filtrado)"
            return header + ":\n" + "\n".join(f"- {line}" for line in stories)

        if intent.intent == IntentType.LIST_TASKS:
            lines = self._data.list_tasks(
                project_id,
                user_id,
                role,
                task_filter=intent.task_filter.value,
            )
            if not lines:
                return f"No hay tareas que coincidan con el filtro solicitado en {project_name}."
            return f"Tareas en {project_name}:\n" + "\n".join(f"- {line}" for line in lines)

        if intent.intent == IntentType.LIST_DOCUMENTATION:
            docs = self._data.list_documentation(project_id, user_id, role)
            if not docs:
                return f"El proyecto {project_name} no tiene documentación visible para usted."
            return f"Documentación de {project_name}:\n" + "\n".join(f"- {d}" for d in docs)

        if intent.intent == IntentType.UNKNOWN:
            return self._fallback_llm(text, user_id, role, optional_project_id, projects)

        return (
            "Puedo ayudarle a consultar proyectos, miembros, sprints, HUs, tareas o documentación. "
            "Reformule su pregunta con más detalle."
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

        if len(candidates) == 1:
            return candidates[0].id
        return None

    def _resolve_sprint_id(self, intent: ParsedIntent, project_id: str) -> str | None:
        if not intent.sprint_ref:
            return None
        sprint_rows = self._data.sprint_candidates(project_id)
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
        role: str,
        optional_project_id: str | None,
        projects: list,
    ) -> str:
        summary_lines = [f"- {p.name}" for p in projects[:10]]
        prompt = (
            "Eres el asistente de DashNode. Responde en español en 1-3 oraciones.\n"
            f"Proyectos visibles del usuario:\n{chr(10).join(summary_lines) or '(ninguno)'}\n"
            f"Consulta: {text.strip()}\n"
            "Si no puedes responder con certeza, pide una pregunta más específica sobre "
            "proyectos, HUs, tareas, sprints, miembros o documentación."
        )
        try:
            self._quotas.check_and_consume("GEMINI")
            return self._generation.generate(prompt).strip()
        except QuotaExhaustedError:
            raise
        except GeminiProcessingError:
            return (
                "No pude procesar la consulta con IA en este momento. Intente preguntar, por "
                "ejemplo: «¿Cuáles son mis proyectos?» o «Lista las HUs del sprint 1»."
            )
