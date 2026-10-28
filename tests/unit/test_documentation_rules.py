"""Unit tests for Documentation and Knowledge Base domain rules (EP-09)."""

from datetime import UTC, datetime

import pytest

from app.modules.documentation.application.dtos import validate_optional_url
from app.modules.documentation.domain import messages
from app.modules.documentation.domain.entities import (
    DocumentationApprovalStatus,
    DocumentationCategory,
    DocumentationEntry,
)


def _sample_entry(
    author_id: str = "dev-1",
    status: DocumentationApprovalStatus = DocumentationApprovalStatus.PENDING,
    is_deleted: bool = False,
    is_pinned: bool = False,
) -> DocumentationEntry:
    now = datetime.now(UTC)
    return DocumentationEntry(
        id="doc-1",
        project_id="proj-1",
        author_id=author_id,
        title="Guía de Arquitectura",
        category=DocumentationCategory.TECNICA,
        objective="Documentar directrices",
        tags="backend, api",
        content="Contenido técnico detallado",
        external_url="https://docs.dashnode.io",
        approval_status=status,
        is_pinned=is_pinned,
        is_deleted=is_deleted,
        created_at=now,
        updated_at=now,
    )


def test_documentation_can_view_rules() -> None:
    entry = _sample_entry(author_id="dev-1", status=DocumentationApprovalStatus.PENDING)

    # Admin and Manager can always view
    assert entry.can_view("other-mgr", "manager") is True
    assert entry.can_view("other-admin", "admin") is True

    # Author can view their own pending entry
    assert entry.can_view("dev-1", "developer") is True

    # Another developer cannot view pending entry
    assert entry.can_view("dev-2", "developer") is False

    # Once approved, all developers can view
    entry.approval_status = DocumentationApprovalStatus.APPROVED
    assert entry.can_view("dev-2", "developer") is True

    # Deleted entries cannot be viewed
    entry.is_deleted = True
    assert entry.can_view("other-mgr", "manager") is False
    assert entry.can_view("dev-1", "developer") is False


def test_documentation_can_edit_rules() -> None:
    entry = _sample_entry(author_id="dev-1", status=DocumentationApprovalStatus.PENDING)

    # Manager and Admin can edit
    assert entry.can_edit("mgr-1", "manager") is True
    assert entry.can_edit("adm-1", "admin") is True

    # Author can edit when PENDING or REJECTED
    assert entry.can_edit("dev-1", "developer") is True
    entry.approval_status = DocumentationApprovalStatus.REJECTED
    assert entry.can_edit("dev-1", "developer") is True

    # Another developer cannot edit
    assert entry.can_edit("dev-2", "developer") is False

    # Developer cannot edit once APPROVED
    entry.approval_status = DocumentationApprovalStatus.APPROVED
    assert entry.can_edit("dev-1", "developer") is False


def test_documentation_can_delete_rules() -> None:
    entry = _sample_entry()

    # Only Admin and Manager can delete
    assert entry.can_delete("manager") is True
    assert entry.can_delete("admin") is True
    assert entry.can_delete("developer") is False


def test_validate_optional_url() -> None:
    assert validate_optional_url(None) is None
    assert validate_optional_url("") is None
    assert validate_optional_url("   ") is None

    # Valid URLs
    assert validate_optional_url("https://dashnode.io") == "https://dashnode.io"
    assert validate_optional_url("http://localhost:8000/docs") == "http://localhost:8000/docs"

    # Invalid URLs raise ValueError with exact literal message
    with pytest.raises(ValueError, match=messages.INVALID_URL):
        validate_optional_url("invalid-url-without-scheme")

    with pytest.raises(ValueError, match=messages.INVALID_URL):
        validate_optional_url("ftp://unsupported-scheme.com")


def test_documentation_visibility_and_approval_workflow_rules() -> None:
    entry = _sample_entry(author_id="dev-1", status=DocumentationApprovalStatus.PENDING)

    # Visibility for developers when restricted (HU_DN_06_82)
    entry.approval_status = DocumentationApprovalStatus.APPROVED
    entry.is_visible_to_devs = True
    assert entry.can_view("dev-2", "developer") is True

    entry.is_visible_to_devs = False
    assert entry.can_view("dev-2", "developer") is False  # Restricted from other devs
    assert entry.can_view("dev-1", "developer") is True  # Author can still view
    assert entry.can_view("mgr-1", "manager") is True  # Manager can still view

    # Visibility management
    assert entry.can_manage_visibility("manager") is True
    assert entry.can_manage_visibility("admin") is True
    assert entry.can_manage_visibility("developer") is False

    # Approval rules (HU_DN_06_84 & RN-DOC-01)
    entry.approval_status = DocumentationApprovalStatus.PENDING
    assert entry.can_approve("mgr-1", "manager") is True
    assert entry.can_approve("adm-1", "admin") is True
    assert entry.can_approve("dev-1", "manager") is False  # Cannot approve own entry
    assert entry.can_approve("dev-2", "developer") is False

    # Rejection rules (HU_DN_06_85)
    assert entry.can_reject("manager") is True
    assert entry.can_reject("admin") is True
    assert entry.can_reject("developer") is False

    # Resubmission rules (HU_DN_06_86)
    assert entry.can_resubmit("dev-1") is False  # Not rejected yet
    entry.approval_status = DocumentationApprovalStatus.REJECTED
    assert entry.can_resubmit("dev-1") is True  # Author can resubmit rejected entry
    assert entry.can_resubmit("dev-2") is False  # Non-author cannot resubmit
