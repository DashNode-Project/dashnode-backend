"""DevOps practices use cases (EP-16 hub)."""

from __future__ import annotations

from datetime import datetime

from app.modules.auth.domain.ports import UserRepository
from app.modules.devops.application.dtos import (
    DevOpsProfileResponse,
    DevOpsRevisionDTO,
    DevOpsRevisionListResponse,
    EnvironmentDTO,
    PipelineStageDTO,
    UpsertDevOpsProfileRequest,
    UserRefDTO,
)
from app.modules.devops.domain import messages
from app.modules.devops.domain.entities import (
    DevOpsRevision,
    EnvironmentSpec,
    PipelineStageSpec,
    ProjectDevOpsProfile,
)
from app.modules.devops.domain.ports import DevOpsProfileRepository
from app.modules.devops.domain.validation import (
    require_change_summary,
    validate_profile,
)
from app.modules.projects.domain.ports import ProjectRepository
from app.shared.application.identity import CurrentUser
from app.shared.application.ports import Clock, IdGenerator, UnitOfWork
from app.shared.domain.authorization import AccessDeniedError
from app.shared.domain.errors import AppError, ErrorKind


def _can_edit(role: str) -> bool:
    return role in ("admin", "manager")


def _ensure_member(projects: ProjectRepository, project_id: str, actor: CurrentUser) -> None:
    if projects.get_by_id(project_id) is None:
        raise AppError("NOT_FOUND", messages.NOT_FOUND_PROJECT, ErrorKind.NOT_FOUND)
    if not projects.user_can_access(project_id, actor.id, actor.role):
        raise AccessDeniedError()


def _ensure_editor(projects: ProjectRepository, project_id: str, actor: CurrentUser) -> None:
    _ensure_member(projects, project_id, actor)
    if not _can_edit(actor.role):
        raise AccessDeniedError()


def _to_dto_stages(stages: list[PipelineStageSpec]) -> list[PipelineStageDTO]:
    return [PipelineStageDTO.model_validate(stage.to_dict()) for stage in stages]


def _to_dto_envs(envs: list[EnvironmentSpec]) -> list[EnvironmentDTO]:
    return [EnvironmentDTO.model_validate(env.to_dict()) for env in envs]


def _empty_profile(project_id: str, *, can_edit: bool) -> DevOpsProfileResponse:
    return DevOpsProfileResponse(
        project_id=project_id,
        is_configured=False,
        can_edit=can_edit,
    )


def _profile_to_response(
    profile: ProjectDevOpsProfile,
    *,
    can_edit: bool,
    users: UserRepository,
) -> DevOpsProfileResponse:
    updated_by = None
    if profile.updated_by:
        user = users.get_by_id(profile.updated_by)
        if user is not None:
            updated_by = UserRefDTO(id=user.id, name=user.name)
    return DevOpsProfileResponse(
        project_id=profile.project_id,
        is_configured=True,
        can_edit=can_edit,
        repository_url=profile.repository_url,
        ci_cd_provider=profile.ci_cd_provider,
        branching_strategy=profile.branching_strategy,
        branching_rules_md=profile.branching_rules_md,
        pipeline_stages=_to_dto_stages(profile.pipeline_stages),
        environments=_to_dto_envs(profile.environments),
        quality_gates_md=profile.quality_gates_md,
        deployment_runbook_md=profile.deployment_runbook_md,
        rollback_observability_md=profile.rollback_observability_md,
        updated_by=updated_by,
        updated_at=profile.updated_at,
    )


def _request_to_profile(
    project_id: str,
    payload: UpsertDevOpsProfileRequest,
    *,
    profile_id: str | None,
    updated_by: str,
    now: datetime,
) -> ProjectDevOpsProfile:
    return ProjectDevOpsProfile(
        id=profile_id,
        project_id=project_id,
        repository_url=payload.repository_url,
        ci_cd_provider=payload.ci_cd_provider,
        branching_strategy=payload.branching_strategy,
        branching_rules_md=payload.branching_rules_md,
        pipeline_stages=[
            PipelineStageSpec.from_dict(s.model_dump()) for s in payload.pipeline_stages
        ],
        environments=[EnvironmentSpec.from_dict(e.model_dump()) for e in payload.environments],
        quality_gates_md=payload.quality_gates_md,
        deployment_runbook_md=payload.deployment_runbook_md,
        rollback_observability_md=payload.rollback_observability_md,
        updated_by=updated_by,
        created_at=now,
        updated_at=now,
    )


class GetProjectDevOpsProfileUseCase:
    def __init__(
        self,
        *,
        profiles: DevOpsProfileRepository,
        projects: ProjectRepository,
        users: UserRepository,
    ) -> None:
        self._profiles = profiles
        self._projects = projects
        self._users = users

    def execute(self, project_id: str, actor: CurrentUser) -> DevOpsProfileResponse:
        _ensure_member(self._projects, project_id, actor)
        can_edit = _can_edit(actor.role)
        stored = self._profiles.get_by_project_id(project_id)
        if stored is None:
            return _empty_profile(project_id, can_edit=can_edit)
        return _profile_to_response(stored, can_edit=can_edit, users=self._users)


class UpsertProjectDevOpsProfileUseCase:
    def __init__(
        self,
        *,
        profiles: DevOpsProfileRepository,
        projects: ProjectRepository,
        users: UserRepository,
        clock: Clock,
        id_gen: IdGenerator,
        uow: UnitOfWork,
    ) -> None:
        self._profiles = profiles
        self._projects = projects
        self._users = users
        self._clock = clock
        self._id_gen = id_gen
        self._uow = uow

    def execute(
        self,
        project_id: str,
        payload: UpsertDevOpsProfileRequest,
        actor: CurrentUser,
    ) -> DevOpsProfileResponse:
        _ensure_editor(self._projects, project_id, actor)
        summary = require_change_summary(payload.change_summary)
        now = self._clock.now()
        existing = self._profiles.get_by_project_id(project_id)
        profile_id = existing.id if existing and existing.id else self._id_gen.generate()
        incoming = _request_to_profile(
            project_id,
            payload,
            profile_id=profile_id,
            updated_by=actor.id,
            now=now,
        )
        validate_profile(incoming)
        if existing is not None and existing.content_equals(incoming):
            raise AppError("NO_CHANGES", messages.NO_CHANGES, ErrorKind.CONFLICT)
        if existing is not None:
            incoming.created_at = existing.created_at
        self._profiles.save(incoming)
        revision = DevOpsRevision(
            id=self._id_gen.generate(),
            profile_id=profile_id,
            project_id=project_id,
            changed_by=actor.id,
            change_summary=summary,
            snapshot=incoming.snapshot(),
            created_at=now,
        )
        self._profiles.add_revision(revision)
        self._uow.commit()
        stored = self._profiles.get_by_project_id(project_id)
        assert stored is not None
        return _profile_to_response(stored, can_edit=True, users=self._users)


class ListProjectDevOpsRevisionsUseCase:
    def __init__(
        self,
        *,
        profiles: DevOpsProfileRepository,
        projects: ProjectRepository,
        users: UserRepository,
    ) -> None:
        self._profiles = profiles
        self._projects = projects
        self._users = users

    def execute(
        self,
        project_id: str,
        actor: CurrentUser,
        *,
        limit: int = 25,
        offset: int = 0,
    ) -> DevOpsRevisionListResponse:
        _ensure_member(self._projects, project_id, actor)
        lim = min(max(limit, 1), 100)
        off = max(offset, 0)
        rows = self._profiles.list_revisions(project_id, limit=lim, offset=off)
        items: list[DevOpsRevisionDTO] = []
        for row in rows:
            changed_by = None
            if row.changed_by:
                user = self._users.get_by_id(row.changed_by)
                if user is not None:
                    changed_by = UserRefDTO(id=user.id, name=user.name)
            items.append(
                DevOpsRevisionDTO(
                    id=row.id,
                    change_summary=row.change_summary,
                    changed_by=changed_by,
                    created_at=row.created_at,
                    snapshot=row.snapshot,
                )
            )
        return DevOpsRevisionListResponse(items=items, limit=lim, offset=off)
