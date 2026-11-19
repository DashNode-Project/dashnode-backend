"""DevOps practices hub domain entities (EP-16)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class PipelineStageSpec:
    order: int
    name: str
    tool: str
    commands: str
    trigger_event: str
    is_required: bool
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "name": self.name,
            "tool": self.tool,
            "commands": self.commands,
            "trigger_event": self.trigger_event,
            "is_required": self.is_required,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PipelineStageSpec:
        return cls(
            order=int(raw["order"]),
            name=str(raw["name"]),
            tool=str(raw["tool"]),
            commands=str(raw["commands"]),
            trigger_event=str(raw["trigger_event"]),
            is_required=bool(raw["is_required"]),
            notes=str(raw["notes"]) if raw.get("notes") is not None else None,
        )


@dataclass(frozen=True, slots=True)
class EnvironmentSpec:
    name: str
    url: str | None
    branch: str
    deploy_strategy: str
    requires_approval: bool
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "branch": self.branch,
            "deploy_strategy": self.deploy_strategy,
            "requires_approval": self.requires_approval,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> EnvironmentSpec:
        url = raw.get("url")
        return cls(
            name=str(raw["name"]),
            url=str(url) if url not in (None, "") else None,
            branch=str(raw["branch"]),
            deploy_strategy=str(raw["deploy_strategy"]),
            requires_approval=bool(raw["requires_approval"]),
            notes=str(raw["notes"]) if raw.get("notes") is not None else None,
        )


@dataclass(slots=True)
class ProjectDevOpsProfile:
    id: str | None
    project_id: str
    repository_url: str | None
    ci_cd_provider: str | None
    branching_strategy: str | None
    branching_rules_md: str | None
    pipeline_stages: list[PipelineStageSpec] = field(default_factory=list)
    environments: list[EnvironmentSpec] = field(default_factory=list)
    quality_gates_md: str | None = None
    deployment_runbook_md: str | None = None
    rollback_observability_md: str | None = None
    updated_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "repository_url": self.repository_url,
            "ci_cd_provider": self.ci_cd_provider,
            "branching_strategy": self.branching_strategy,
            "branching_rules_md": self.branching_rules_md,
            "pipeline_stages": [stage.to_dict() for stage in self.pipeline_stages],
            "environments": [env.to_dict() for env in self.environments],
            "quality_gates_md": self.quality_gates_md,
            "deployment_runbook_md": self.deployment_runbook_md,
            "rollback_observability_md": self.rollback_observability_md,
        }

    def content_equals(self, other: ProjectDevOpsProfile) -> bool:
        return self.snapshot() == other.snapshot()


@dataclass(frozen=True, slots=True)
class DevOpsRevision:
    id: str
    profile_id: str
    project_id: str
    changed_by: str | None
    change_summary: str
    snapshot: dict[str, Any]
    created_at: datetime
