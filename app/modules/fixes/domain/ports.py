"""Ports (protocols/interfaces) for EP-11 Issues and Evidences.

@sad AD-09, BR-2
@origin [User Stories HU_DN_07_97 .. HU_DN_07_105]
"""

from datetime import datetime
from typing import Protocol

from app.modules.fixes.domain.entities import (
    Evidence,
    Issue,
    IssueSeverity,
    IssueStatus,
    IssueType,
    TaskSnapshot,
)


class IssueRepository(Protocol):
    def save(self, issue: Issue) -> None: ...

    def update_with_optimistic_lock(self, issue: Issue, expected_version: int) -> bool: ...

    def get_by_id(self, issue_id: str) -> Issue | None: ...

    def get_by_idempotency_key(self, project_id: str, key: str) -> Issue | None: ...

    def count_other_open_issues_for_task(
        self, task_id: str, exclude_issue_id: str | None = None
    ) -> int: ...

    def list_by_project(
        self,
        project_id: str,
        status: IssueStatus | None = None,
        severity: IssueSeverity | None = None,
        issue_type: IssueType | None = None,
        cursor: str | None = None,
        limit: int = 25,
    ) -> tuple[list[Issue], str | None, int]: ...

    def count_evidences_for_issues(self, issue_ids: list[str]) -> dict[str, int]: ...


class EvidenceRepository(Protocol):
    def save(self, evidence: Evidence) -> None: ...

    def get_by_id(self, evidence_id: str) -> Evidence | None: ...

    def list_by_issue(self, issue_id: str) -> list[Evidence]: ...

    def find_by_fix_and_hash(self, fix_id: str, sha256_hash: str) -> Evidence | None: ...

    def delete(self, evidence_id: str) -> None: ...


class EvidenceFileStorage(Protocol):
    def save_file(self, file_id: str, data: bytes, extension: str) -> str: ...

    def read_file(self, storage_path: str) -> bytes: ...

    def delete_file(self, storage_path: str) -> None: ...


class SignedUrlGenerator(Protocol):
    def generate(
        self,
        project_id: str,
        issue_id: str,
        evidence_id: str,
        expires_in_seconds: int = 300,
    ) -> str: ...

    def verify(
        self,
        evidence_id: str,
        expires_timestamp: int,
        signature: str,
    ) -> bool: ...


class ProjectLookupPort(Protocol):
    def is_active_member(self, project_id: str, user_id: str) -> bool: ...

    def is_active_developer_member(self, project_id: str, user_id: str) -> bool: ...


class UserDisplayLookupPort(Protocol):
    def get_user_display(self, user_id: str) -> tuple[str, str | None] | None: ...


class FixTaskCoordinatorPort(Protocol):
    def get_task_snapshot(self, project_id: str, task_id: str) -> TaskSnapshot | None: ...

    def get_task_snapshots_map(self, task_ids: list[str]) -> dict[str, TaskSnapshot]: ...

    def lock_task_for_update(self, project_id: str, task_id: str) -> TaskSnapshot | None: ...

    def transition_task_to_correction(
        self,
        *,
        task: TaskSnapshot,
        actor_id: str,
        history_id: str,
        when: datetime,
    ) -> TaskSnapshot: ...

    def restore_task_from_correction(
        self,
        *,
        task: TaskSnapshot,
        target_status: str,
        actor_id: str,
        history_id: str,
        when: datetime,
    ) -> TaskSnapshot: ...


class OutboxPort(Protocol):
    def enqueue_event(
        self,
        *,
        event_id: str,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: dict[str, object],
        created_at: datetime,
    ) -> None: ...


class IssueNotificationPort(Protocol):
    def notify_issue_created(
        self,
        project_id: str,
        issue_id: str,
        title: str,
        reporter_id: str,
    ) -> None: ...

    def notify_issue_assigned_in_tx(
        self,
        *,
        project_id: str,
        issue_id: str,
        title: str,
        assignee_id: str | None,
        actor_id: str,
        when: datetime,
    ) -> None: ...

    def notify_issue_resolved_in_tx(
        self,
        *,
        project_id: str,
        issue_id: str,
        title: str,
        reporter_id: str,
        assignee_id: str | None,
        actor_id: str,
        when: datetime,
    ) -> None: ...

    def notify_task_fix_reported_in_tx(
        self,
        *,
        project_id: str,
        issue_id: str,
        task_id: str,
        task_name: str,
        title: str,
        reporter_id: str,
        when: datetime,
    ) -> None: ...
