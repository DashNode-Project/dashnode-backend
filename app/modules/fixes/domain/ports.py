"""Ports (protocols/interfaces) for EP-11 Issues and Evidences.

@sad AD-09, BR-2
@origin [User Stories HU_DN_07_97 .. HU_DN_07_101]
"""

from typing import Protocol

from app.modules.fixes.domain.entities import (
    Evidence,
    Issue,
    IssueSeverity,
    IssueStatus,
    IssueType,
)


class IssueRepository(Protocol):
    def save(self, issue: Issue) -> None: ...

    def get_by_id(self, issue_id: str) -> Issue | None: ...

    def get_by_idempotency_key(self, project_id: str, key: str) -> Issue | None: ...

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


class UserDisplayLookupPort(Protocol):
    def get_user_display(self, user_id: str) -> tuple[str, str | None] | None: ...


class IssueNotificationPort(Protocol):
    def notify_issue_created(
        self,
        project_id: str,
        issue_id: str,
        title: str,
        reporter_id: str,
    ) -> None: ...
