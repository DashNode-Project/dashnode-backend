"""Unit tests for EP-11 Issues and Evidences domain logic and file validation.

@sad AD-09, AD-10
@origin [User Stories HU_DN_07_97 .. HU_DN_07_101]
"""

import struct

import pytest

from app.modules.fixes.application.file_validation import (
    MAX_IMAGE_SIZE,
    MAX_LOG_SIZE,
    MAX_VIDEO_SIZE,
    validate_and_sanitize_evidence_file,
)
from app.modules.fixes.domain.entities import (
    ConflictError,
    EvidenceType,
    Issue,
    IssueSeverity,
    IssueType,
    resolve_restorable_task_status,
)
from app.modules.fixes.domain.messages import (
    DESCRIPTION_TOO_LONG,
    FILE_TOO_LARGE,
    RESOLUTION_NOTE_REQUIRED,
    RESOLUTION_NOTE_TOO_LONG,
    SEVERITY_REQUIRED,
    TASK_TARGET_STATUS_INVALID,
    TITLE_REQUIRED,
    TITLE_TOO_LONG,
    TYPE_REQUIRED,
    UNSUPPORTED_FORMAT,
    VIDEO_TOO_LONG,
)
from app.modules.fixes.infrastructure.repositories import HmacSignedUrlGenerator


def test_issue_title_validation() -> None:
    # Empty title
    with pytest.raises(ValueError, match=TITLE_REQUIRED):
        Issue.validate_title("")
    with pytest.raises(ValueError, match=TITLE_REQUIRED):
        Issue.validate_title("   ")
    with pytest.raises(ValueError, match=TITLE_REQUIRED):
        Issue.validate_title(None)

    # Too long title (> 100)
    with pytest.raises(ValueError, match=TITLE_TOO_LONG):
        Issue.validate_title("x" * 101)

    # Valid title
    assert Issue.validate_title("Error en inicio de sesión") == "Error en inicio de sesión"


def test_issue_description_validation() -> None:
    assert Issue.validate_description(None) is None
    assert Issue.validate_description("   ") is None
    assert Issue.validate_description("Detalle del error") == "Detalle del error"

    # Too long (> 5000)
    with pytest.raises(ValueError, match=DESCRIPTION_TOO_LONG):
        Issue.validate_description("a" * 5001)


def test_issue_severity_validation() -> None:
    with pytest.raises(ValueError, match=SEVERITY_REQUIRED):
        IssueSeverity.from_string(None)
    with pytest.raises(ValueError, match=SEVERITY_REQUIRED):
        IssueSeverity.from_string("")
    with pytest.raises(ValueError, match=SEVERITY_REQUIRED):
        IssueSeverity.from_string("invalida")

    assert IssueSeverity.from_string("Baja") == IssueSeverity.LOW
    assert IssueSeverity.from_string("low") == IssueSeverity.LOW
    assert IssueSeverity.from_string("Media") == IssueSeverity.MEDIUM
    assert IssueSeverity.from_string("medium") == IssueSeverity.MEDIUM
    assert IssueSeverity.from_string("Alta") == IssueSeverity.HIGH
    assert IssueSeverity.from_string("high") == IssueSeverity.HIGH
    assert IssueSeverity.from_string("Crítica") == IssueSeverity.CRITICAL
    assert IssueSeverity.from_string("critical") == IssueSeverity.CRITICAL


def test_issue_type_validation() -> None:
    with pytest.raises(ValueError, match=TYPE_REQUIRED):
        IssueType.from_string(None)
    with pytest.raises(ValueError, match=TYPE_REQUIRED):
        IssueType.from_string("")
    with pytest.raises(ValueError, match=TYPE_REQUIRED):
        IssueType.from_string("desconocido")

    assert IssueType.from_string("Bug") == IssueType.BUG
    assert IssueType.from_string("bug") == IssueType.BUG
    assert IssueType.from_string("Regresión") == IssueType.REGRESSION
    assert IssueType.from_string("regression") == IssueType.REGRESSION
    assert IssueType.from_string("Rendimiento") == IssueType.PERFORMANCE
    assert IssueType.from_string("performance") == IssueType.PERFORMANCE
    assert IssueType.from_string("Seguridad") == IssueType.SECURITY
    assert IssueType.from_string("security") == IssueType.SECURITY
    assert IssueType.from_string("UX") == IssueType.UX
    assert IssueType.from_string("ux") == IssueType.UX


def test_file_validation_polyglots_and_scripts() -> None:
    # Executable PE header
    with pytest.raises(ValueError, match=UNSUPPORTED_FORMAT):
        validate_and_sanitize_evidence_file("test.jpg", b"MZ\x90\x00somecode")

    # ELF header
    with pytest.raises(ValueError, match=UNSUPPORTED_FORMAT):
        validate_and_sanitize_evidence_file("test.png", b"\x7fELF\x01\x01\x01")

    # ZIP header
    with pytest.raises(ValueError, match=UNSUPPORTED_FORMAT):
        validate_and_sanitize_evidence_file("test.log", b"PK\x03\x04embedded")

    # Script tag in header
    with pytest.raises(ValueError, match=UNSUPPORTED_FORMAT):
        validate_and_sanitize_evidence_file("avatar.jpg", b"\xff\xd8\xff<script>alert(1)</script>")

    # PHP tag in header
    with pytest.raises(ValueError, match=UNSUPPORTED_FORMAT):
        validate_and_sanitize_evidence_file("avatar.jpg", b"\xff\xd8\xff<?php system('id'); ?>")


def test_file_validation_size_limits() -> None:
    # Image > 5MB
    large_jpg = b"\xff\xd8\xff\xe0" + b"\x00" * (MAX_IMAGE_SIZE + 10)
    with pytest.raises(ValueError, match=FILE_TOO_LARGE):
        validate_and_sanitize_evidence_file("img.jpg", large_jpg)

    # Video > 25MB
    large_mp4 = b"\x00\x00\x00\x14ftypmp42" + b"\x00" * (MAX_VIDEO_SIZE + 10)
    with pytest.raises(ValueError, match=FILE_TOO_LARGE):
        validate_and_sanitize_evidence_file("video.mp4", large_mp4)

    # Log > 1MB
    large_log = b"Log line\n" * (MAX_LOG_SIZE // 8 + 10)
    with pytest.raises(ValueError, match=FILE_TOO_LARGE):
        validate_and_sanitize_evidence_file("trace.log", large_log)


def test_file_validation_jpeg_exif_stripping() -> None:
    # Construct a valid minimal JPEG with an APP1 (EXIF) segment
    # SOI (\xff\xd8), APP1 (\xff\xe1, len 10, EXIF data), SOS (\xff\xda), image data, EOI (\xff\xd9)
    app1_marker = b"\xff\xe1" + struct.pack(">H", 10) + b"Exif\x00\x00\x01\x02"
    raw_jpeg = b"\xff\xd8" + app1_marker + b"\xff\xda\x00\x02\x12\x34\xff\xd9"

    validated = validate_and_sanitize_evidence_file("screenshot.jpg", raw_jpeg)
    assert validated.file_type == EvidenceType.IMAGE
    assert validated.mime_type == "image/jpeg"
    assert validated.extension == ".jpg"
    assert b"Exif" not in validated.sanitized_bytes
    assert validated.sanitized_bytes.startswith(b"\xff\xd8")


def test_file_validation_png_metadata_stripping() -> None:
    # Construct minimal PNG with tEXt metadata chunk
    png_header = b"\x89PNG\r\n\x1a\n"
    # IHDR chunk
    ihdr_content = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_chunk = struct.pack(">I", len(ihdr_content)) + b"IHDR" + ihdr_content + b"\x00\x00\x00\x00"
    # tEXt chunk
    text_content = b"Comment\x00Some camera info"
    text_chunk = struct.pack(">I", len(text_content)) + b"tEXt" + text_content + b"\x00\x00\x00\x00"
    # IEND chunk
    iend_chunk = struct.pack(">I", 0) + b"IEND" + b"\x00\x00\x00\x00"

    raw_png = png_header + ihdr_chunk + text_chunk + iend_chunk
    validated = validate_and_sanitize_evidence_file("capture.png", raw_png)
    assert validated.file_type == EvidenceType.IMAGE
    assert validated.mime_type == "image/png"
    assert b"Some camera info" not in validated.sanitized_bytes
    assert b"IHDR" in validated.sanitized_bytes


def test_file_validation_video_duration_check() -> None:
    # Minimal MP4 with moov -> mvhd box indicating 75 seconds (timescale=1000, duration=75000)
    timescale = 1000
    duration = 75000  # 75s > 60s!
    mvhd_payload = (
        b"\x00" * 12 + struct.pack(">I", timescale) + struct.pack(">I", duration) + b"\x00" * 40
    )
    mvhd_box = struct.pack(">I", len(mvhd_payload) + 8) + b"mvhd" + mvhd_payload
    moov_box = struct.pack(">I", len(mvhd_box) + 8) + b"moov" + mvhd_box
    ftyp_box = struct.pack(">I", 16) + b"ftypisom\x00\x00\x02\x00"

    too_long_mp4 = ftyp_box + moov_box
    with pytest.raises(ValueError, match=VIDEO_TOO_LONG):
        validate_and_sanitize_evidence_file("demo.mp4", too_long_mp4)

    # Valid duration 15s
    duration_valid = 15000  # 15s <= 60s
    mvhd_payload_ok = (
        b"\x00" * 12
        + struct.pack(">I", timescale)
        + struct.pack(">I", duration_valid)
        + b"\x00" * 40
    )
    mvhd_box_ok = struct.pack(">I", len(mvhd_payload_ok) + 8) + b"mvhd" + mvhd_payload_ok
    moov_box_ok = struct.pack(">I", len(mvhd_box_ok) + 8) + b"moov" + mvhd_box_ok

    valid_mp4 = ftyp_box + moov_box_ok
    validated = validate_and_sanitize_evidence_file("demo.mp4", valid_mp4)
    assert validated.file_type == EvidenceType.VIDEO
    assert validated.duration_seconds == 15.0


def test_signed_url_generator() -> None:
    gen = HmacSignedUrlGenerator(secret_key="my-secret-key-1234567890123456")
    url = gen.generate(
        project_id="proj1", issue_id="iss1", evidence_id="ev1", expires_in_seconds=300
    )
    assert "/api/v1/projects/proj1/issues/iss1/evidences/ev1/content" in url
    assert "signature=" in url
    assert "expires=" in url

    # Parse signature and expires from url
    parts = url.split("?")[-1].split("&")
    params = dict(p.split("=") for p in parts)
    sig = params["signature"]
    exp = int(params["expires"])

    assert gen.verify("ev1", exp, sig) is True
    assert gen.verify("ev1", exp, "tampered_sig") is False
    assert gen.verify("other_ev", exp, sig) is False
    assert gen.verify("ev1", exp + 10, sig) is False


def test_resolution_note_validation() -> None:
    with pytest.raises(ValueError, match=RESOLUTION_NOTE_REQUIRED):
        Issue.validate_resolution_note(None)
    with pytest.raises(ValueError, match=RESOLUTION_NOTE_REQUIRED):
        Issue.validate_resolution_note("")
    with pytest.raises(ValueError, match=RESOLUTION_NOTE_REQUIRED):
        Issue.validate_resolution_note("   ")
    with pytest.raises(ValueError, match=RESOLUTION_NOTE_TOO_LONG):
        Issue.validate_resolution_note("z" * 2001)

    assert Issue.validate_resolution_note("  Parche aplicado correctamente  ") == (
        "Parche aplicado correctamente"
    )
    assert len(Issue.validate_resolution_note("z" * 2000)) == 2000


def test_resolve_restorable_task_status() -> None:
    for status in ("TODO", "IN_PROGRESS", "CODE_REVIEW", "TESTING", "DONE"):
        assert resolve_restorable_task_status(status, "TODO") == status
        assert resolve_restorable_task_status(f" {status.lower()} ", None) == status

    with pytest.raises(ValueError, match=TASK_TARGET_STATUS_INVALID):
        resolve_restorable_task_status("CORRECTION", "IN_PROGRESS")
    with pytest.raises(ValueError, match=TASK_TARGET_STATUS_INVALID):
        resolve_restorable_task_status("BLOCKED", "TODO")

    assert resolve_restorable_task_status(None, "CODE_REVIEW") == "CODE_REVIEW"
    assert resolve_restorable_task_status(" ", "DONE") == "DONE"
    assert resolve_restorable_task_status(None, None) == "IN_PROGRESS"
    assert resolve_restorable_task_status(None, "CORRECTION") == "IN_PROGRESS"
    assert resolve_restorable_task_status(None, "INVALID") == "IN_PROGRESS"


def test_conflict_error_subclass() -> None:
    err = ConflictError("conflict")
    assert isinstance(err, Exception)
