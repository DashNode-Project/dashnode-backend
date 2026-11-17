"""Aggregations and registry reads for EP-13 IAM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC

from sqlalchemy import and_, func, or_, select, true
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.modules.ai_metrics.application.interaction_registry import (
    SOURCE_METRICS_QUERY,
    STATUS_SUCCESS,
)
from app.modules.ai_metrics.application.period import MetricsPeriod, parse_metrics_period
from app.modules.ai_metrics.domain import messages as iam_msg
from app.modules.ai_metrics.infrastructure.models import (
    AiInteractionModel,
    AiInteractionStepModel,
    AiRatingModel,
    AiRegistryAccessLogModel,
)
from app.modules.auth.infrastructure.models import UserModel
from app.modules.projects.infrastructure.models import ProjectModel
from app.shared.application.identity import CurrentUser
from app.shared.domain.errors import AppError, ErrorKind
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.id_generator import UuidGenerator

SCOPE_GLOBAL = "global"
SCOPE_MANAGED = "managed_projects"

USAGE_SOURCES_EXCLUDED = frozenset({SOURCE_METRICS_QUERY})


@dataclass(frozen=True, slots=True)
class MetricsScope:
    label: str
    project_ids: frozenset[str] | None


def _normalize_role(role: str) -> str:
    value = role.strip().lower()
    if value in {"administrator", "admin"}:
        return "admin"
    if value in {"gerente", "manager"}:
        return "manager"
    if value in {"desarrollador", "developer"}:
        return "developer"
    return value


def _require_metrics_reader(actor: CurrentUser) -> str:
    role = _normalize_role(actor.role)
    if role == "developer":
        raise AppError(
            "AI_METRICS_FORBIDDEN",
            iam_msg.AI_METRICS_DEVELOPER_FORBIDDEN,
            ErrorKind.FORBIDDEN,
        )
    if role not in {"admin", "manager"}:
        raise AppError(
            "AI_METRICS_FORBIDDEN",
            iam_msg.AI_METRICS_DEVELOPER_FORBIDDEN,
            ErrorKind.FORBIDDEN,
        )
    return role


class AiMetricsService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._clock = SystemClock()
        self._ids = UuidGenerator()

    def resolve_scope(self, actor: CurrentUser) -> MetricsScope:
        role = _require_metrics_reader(actor)
        if role == "admin":
            return MetricsScope(label=SCOPE_GLOBAL, project_ids=None)
        managed = self._session.scalars(
            select(ProjectModel.id).where(
                ProjectModel.manager_id == actor.id,
                ProjectModel.deleted_at.is_(None),
            )
        ).all()
        return MetricsScope(label=SCOPE_MANAGED, project_ids=frozenset(managed))

    def _scope_filter(self, scope: MetricsScope) -> ColumnElement[bool]:
        if scope.project_ids is None:
            return true()
        if not scope.project_ids:
            return AiInteractionModel.project_id.in_(())
        return or_(
            AiInteractionModel.project_id.in_(scope.project_ids),
            AiInteractionModel.project_id.is_(None),
        )

    def _usage_filter(self) -> ColumnElement[bool]:
        return and_(
            AiInteractionModel.counts_as_usage.is_(True),
            AiInteractionModel.source.notin_(tuple(USAGE_SOURCES_EXCLUDED)),
        )

    def _log_access(
        self,
        actor: CurrentUser,
        action: str,
        scope: MetricsScope,
        period: MetricsPeriod,
        project_id: str | None,
    ) -> None:
        now = self._clock.now().astimezone(UTC)
        self._session.add(
            AiRegistryAccessLogModel(
                id=self._ids.generate(),
                accessor_user_id=actor.id,
                action=action,
                scope=scope.label,
                period_key=period.key,
                project_id=project_id,
                created_at=now,
            )
        )

    def get_summary(
        self,
        actor: CurrentUser,
        *,
        period: str | None,
        from_iso: str | None,
        to_iso: str | None,
        project_id: str | None,
    ) -> dict[str, object]:
        scope = self.resolve_scope(actor)
        window = parse_metrics_period(
            period, from_iso=from_iso, to_iso=to_iso, now=self._clock.now()
        )
        self._log_access(actor, "VIEW_SUMMARY", scope, window, project_id)

        filters = [
            AiInteractionModel.created_at >= window.start,
            AiInteractionModel.created_at <= window.end,
            self._scope_filter(scope),
        ]
        if project_id:
            filters.append(AiInteractionModel.project_id == project_id)

        base = select(AiInteractionModel).where(and_(*filters))
        rows = self._session.scalars(base).all()

        usage_rows = [
            r for r in rows if r.counts_as_usage and r.source not in USAGE_SOURCES_EXCLUDED
        ]
        success_rows = [r for r in usage_rows if r.status == STATUS_SUCCESS]

        total_interactions = len(usage_rows)
        success_count = len(success_rows)
        error_count = len(usage_rows) - success_count
        total_tokens = sum(r.input_tokens + r.output_tokens for r in usage_rows)
        latencies = [r.total_latency_ms for r in usage_rows if r.total_latency_ms > 0]
        avg_latency = int(sum(latencies) / len(latencies)) if latencies else 0

        return {
            "scope": scope.label,
            "period": {
                "key": window.key,
                "from": window.start.isoformat(),
                "to": window.end.isoformat(),
            },
            "summary": {
                "total_interactions": total_interactions,
                "success_count": success_count,
                "error_count": error_count,
                "total_tokens": total_tokens,
                "average_latency_ms": avg_latency,
            },
        }

    def get_by_user(
        self,
        actor: CurrentUser,
        *,
        period: str | None,
        from_iso: str | None,
        to_iso: str | None,
        project_id: str | None,
    ) -> dict[str, object]:
        scope = self.resolve_scope(actor)
        window = parse_metrics_period(
            period, from_iso=from_iso, to_iso=to_iso, now=self._clock.now()
        )
        self._log_access(actor, "VIEW_BY_USER", scope, window, project_id)

        filters = [
            AiInteractionModel.created_at >= window.start,
            AiInteractionModel.created_at <= window.end,
            self._scope_filter(scope),
            self._usage_filter(),
        ]
        if project_id:
            filters.append(AiInteractionModel.project_id == project_id)

        stmt = (
            select(
                AiInteractionModel.user_id,
                func.count(AiInteractionModel.id),
                func.coalesce(func.sum(AiInteractionModel.input_tokens), 0),
                func.coalesce(func.sum(AiInteractionModel.output_tokens), 0),
                func.coalesce(func.avg(AiInteractionModel.total_latency_ms), 0),
            )
            .where(and_(*filters))
            .group_by(AiInteractionModel.user_id)
            .order_by(func.count(AiInteractionModel.id).desc())
        )
        grouped = self._session.execute(stmt).all()
        user_ids = [row[0] for row in grouped]
        names: dict[str, str] = {}
        if user_ids:
            for user in self._session.scalars(select(UserModel).where(UserModel.id.in_(user_ids))):
                names[user.id] = user.name

        items = [
            {
                "user_id": row[0],
                "user_name": names.get(row[0], "Usuario"),
                "interaction_count": int(row[1]),
                "input_tokens": int(row[2]),
                "output_tokens": int(row[3]),
                "average_latency_ms": int(float(row[4] or 0)),
            }
            for row in grouped
        ]

        return {
            "scope": scope.label,
            "period": {
                "key": window.key,
                "from": window.start.isoformat(),
                "to": window.end.isoformat(),
            },
            "items": items,
        }

    def list_interactions(
        self,
        actor: CurrentUser,
        *,
        period: str | None,
        from_iso: str | None,
        to_iso: str | None,
        project_id: str | None,
        source: str | None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, object]:
        scope = self.resolve_scope(actor)
        window = parse_metrics_period(
            period, from_iso=from_iso, to_iso=to_iso, now=self._clock.now()
        )
        self._log_access(actor, "LIST", scope, window, project_id)

        filters = [
            AiInteractionModel.created_at >= window.start,
            AiInteractionModel.created_at <= window.end,
            self._scope_filter(scope),
        ]
        if project_id:
            filters.append(AiInteractionModel.project_id == project_id)
        if source:
            filters.append(AiInteractionModel.source == source.upper())

        stmt = (
            select(AiInteractionModel)
            .where(and_(*filters))
            .order_by(AiInteractionModel.created_at.desc())
            .offset(max(0, offset))
            .limit(min(200, max(1, limit)))
        )
        rows = self._session.scalars(stmt).all()
        return {
            "scope": scope.label,
            "period": {
                "key": window.key,
                "from": window.start.isoformat(),
                "to": window.end.isoformat(),
            },
            "items": [_interaction_brief(row) for row in rows],
        }

    def get_interaction_detail(self, actor: CurrentUser, interaction_id: str) -> dict[str, object]:
        scope = self.resolve_scope(actor)
        row = self._session.get(AiInteractionModel, interaction_id)
        if row is None:
            raise AppError(
                "AI_INTERACTION_NOT_FOUND",
                iam_msg.AI_METRICS_INTERACTION_NOT_FOUND,
                ErrorKind.NOT_FOUND,
            )
        if (
            scope.project_ids is not None
            and row.project_id
            and row.project_id not in scope.project_ids
        ):
            raise AppError(
                "AI_METRICS_FORBIDDEN",
                iam_msg.AI_METRICS_INTERACTION_OUT_OF_SCOPE,
                ErrorKind.FORBIDDEN,
            )

        window = MetricsPeriod(
            key="detail",
            start=row.created_at.astimezone(UTC),
            end=self._clock.now().astimezone(UTC),
        )
        self._log_access(actor, "DETAIL", scope, window, row.project_id)

        steps = self._session.scalars(
            select(AiInteractionStepModel)
            .where(AiInteractionStepModel.interaction_id == interaction_id)
            .order_by(AiInteractionStepModel.step_order)
        ).all()
        rating = self._session.scalar(
            select(AiRatingModel).where(AiRatingModel.interaction_id == interaction_id)
        )
        user = self._session.get(UserModel, row.user_id)
        return {
            "scope": scope.label,
            "interaction": {
                **_interaction_brief(row),
                "request_text": row.request_text,
                "response_text": row.response_text,
                "user_name": user.name if user else "Usuario",
                "steps": [
                    {
                        "step_order": s.step_order,
                        "step_type": s.step_type,
                        "status": s.status,
                        "model_id": s.model_id,
                        "input_tokens": s.input_tokens,
                        "output_tokens": s.output_tokens,
                        "audio_duration_ms": s.audio_duration_ms,
                        "latency_ms": s.latency_ms,
                    }
                    for s in steps
                ],
                "rating": (
                    {
                        "score": rating.score,
                        "comment": rating.comment,
                        "rated_by": rating.rated_by,
                    }
                    if rating
                    else None
                ),
            },
        }

    def upsert_rating(
        self,
        actor: CurrentUser,
        interaction_id: str,
        *,
        score: int,
        comment: str | None,
    ) -> dict[str, str]:
        if score < 1 or score > 5:
            raise AppError(
                "INVALID_RATING",
                iam_msg.AI_METRICS_RATING_INVALID_SCORE,
                ErrorKind.VALIDATION,
            )
        row = self._session.get(AiInteractionModel, interaction_id)
        if row is None:
            raise AppError(
                "AI_INTERACTION_NOT_FOUND",
                iam_msg.AI_METRICS_INTERACTION_NOT_FOUND,
                ErrorKind.NOT_FOUND,
            )
        if row.user_id != actor.id:
            raise AppError(
                "AI_RATING_FORBIDDEN",
                iam_msg.AI_METRICS_RATING_OWN_ONLY,
                ErrorKind.FORBIDDEN,
            )

        now = self._clock.now().astimezone(UTC)
        existing = self._session.scalar(
            select(AiRatingModel).where(AiRatingModel.interaction_id == interaction_id)
        )
        if existing is None:
            self._session.add(
                AiRatingModel(
                    id=self._ids.generate(),
                    interaction_id=interaction_id,
                    rated_by=actor.id,
                    score=score,
                    comment=comment,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            # v1: PG trigger immutability deferred — repository allows a single upsert path.
            existing.score = score
            existing.comment = comment
            existing.updated_at = now

        return {"message": iam_msg.AI_METRICS_RATING_SAVED}


def _interaction_brief(row: AiInteractionModel) -> dict[str, object]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "project_id": row.project_id,
        "source": row.source,
        "status": row.status,
        "model_id": row.model_id,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "total_latency_ms": row.total_latency_ms,
        "audio_duration_ms": row.audio_duration_ms,
        "counts_as_usage": row.counts_as_usage,
        "error_code": row.error_code,
        "created_at": row.created_at.isoformat(),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


def format_metrics_chat_answer(payload: dict[str, object]) -> str:
    """Deterministic Spanish answer for METRICS_QUERY assistant path."""
    if "summary" in payload:
        summary = payload["summary"]
        assert isinstance(summary, dict)
        period = payload.get("period")
        period_key = period.get("key", "") if isinstance(period, dict) else ""
        return (
            f"Resumen de métricas de IA ({period_key}): "
            f"{summary.get('total_interactions', 0)} interacciones contables, "
            f"{summary.get('total_tokens', 0)} tokens, "
            f"latencia media {summary.get('average_latency_ms', 0)} ms."
        )
    if "items" in payload and payload.get("scope"):
        items = payload["items"]
        if isinstance(items, list) and items and "user_name" in items[0]:
            lines = ["Interacciones de IA por usuario:"]
            for item in items[:10]:
                assert isinstance(item, dict)
                token_total = int(item.get("input_tokens", 0)) + int(item.get("output_tokens", 0))
                lines.append(
                    f"- {item.get('user_name')}: {item.get('interaction_count')} "
                    f"({token_total} tokens)"
                )
            return "\n".join(lines)
        if isinstance(items, list):
            return f"Se encontraron {len(items)} interacciones en el registro consultado."
    return "Consulta de métricas de IA procesada."
