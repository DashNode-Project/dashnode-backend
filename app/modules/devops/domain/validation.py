"""Domain validation for DevOps practices payloads."""

from __future__ import annotations

from urllib.parse import urlparse

from app.modules.devops.domain import messages
from app.modules.devops.domain.entities import (
    EnvironmentSpec,
    PipelineStageSpec,
    ProjectDevOpsProfile,
)
from app.shared.domain.errors import AppError, ErrorKind


def _require_http_url(value: str | None) -> None:
    if value is None or value.strip() == "":
        return
    parsed = urlparse(value.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise AppError(
            "INVALID_REPOSITORY_URL", messages.INVALID_REPOSITORY_URL, ErrorKind.VALIDATION
        )


def validate_stage_specs(stages: list[PipelineStageSpec]) -> None:
    if not stages:
        return
    orders = [stage.order for stage in stages]
    if any(order < 1 for order in orders):
        raise AppError(
            "INVALID_PIPELINE_ORDER", messages.INVALID_PIPELINE_ORDER, ErrorKind.VALIDATION
        )
    if len(set(orders)) != len(orders):
        raise AppError(
            "DUPLICATE_PIPELINE_ORDER", messages.DUPLICATE_PIPELINE_ORDER, ErrorKind.VALIDATION
        )


def validate_environment_specs(envs: list[EnvironmentSpec]) -> None:
    if not envs:
        return
    names = [env.name.strip().lower() for env in envs]
    if any(not name for name in names):
        raise AppError(
            "EMPTY_ENVIRONMENT_NAME", messages.EMPTY_ENVIRONMENT_NAME, ErrorKind.VALIDATION
        )
    if len(set(names)) != len(names):
        raise AppError(
            "DUPLICATE_ENVIRONMENT_NAME", messages.DUPLICATE_ENVIRONMENT_NAME, ErrorKind.VALIDATION
        )
    for env in envs:
        if env.url:
            parsed = urlparse(env.url.strip())
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise AppError(
                    "INVALID_ENVIRONMENT_URL",
                    messages.INVALID_ENVIRONMENT_URL,
                    ErrorKind.VALIDATION,
                )


def validate_profile(profile: ProjectDevOpsProfile) -> None:
    _require_http_url(profile.repository_url)
    validate_stage_specs(profile.pipeline_stages)
    validate_environment_specs(profile.environments)


def require_change_summary(summary: str) -> str:
    cleaned = summary.strip()
    if not cleaned:
        raise AppError(
            "CHANGE_SUMMARY_REQUIRED", messages.CHANGE_SUMMARY_REQUIRED, ErrorKind.VALIDATION
        )
    if len(cleaned) > 255:
        raise AppError(
            "CHANGE_SUMMARY_TOO_LONG", messages.CHANGE_SUMMARY_TOO_LONG, ErrorKind.VALIDATION
        )
    return cleaned
