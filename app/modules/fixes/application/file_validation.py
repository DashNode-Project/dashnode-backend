"""Binary inspection, EXIF stripping, polyglot rejection, and video duration validation.

@sad AD-09, RNF-SEG-10
@origin [User Story HU_DN_07_98 Criteria 2, 3, 4, 6]
"""

import hashlib
import struct
from typing import NamedTuple

from app.modules.fixes.domain.entities import EvidenceType
from app.modules.fixes.domain.messages import (
    FILE_TOO_LARGE,
    UNSUPPORTED_FORMAT,
    VIDEO_TOO_LONG,
)

MAX_IMAGE_SIZE = 5 * 1024 * 1024       # 5 MB
MAX_VIDEO_SIZE = 25 * 1024 * 1024     # 25 MB
MAX_LOG_SIZE = 1 * 1024 * 1024         # 1 MB
MAX_VIDEO_DURATION_SECONDS = 60.0


class ValidatedFile(NamedTuple):
    sanitized_bytes: bytes
    file_type: EvidenceType
    mime_type: str
    extension: str
    sha256_hash: str
    duration_seconds: float | None


def _check_polyglots_and_scripts(data: bytes) -> None:
    """Rejects disguised executables, archives, and embedded scripts (polyglots)."""
    # Check for executable or archive headers
    if data.startswith(b"MZ") or data.startswith(b"\x7fELF") or data.startswith(b"PK\x03\x04"):
        raise ValueError(UNSUPPORTED_FORMAT)

    # Search for embedded HTML/PHP/JS scripts in binary payload
    lowered = data[:4096].lower()
    suspicious_tags = (
        b"<script",
        b"<?php",
        b"<%eval",
        b"<html",
        b"<svg",
        b"onload=",
        b"onerror=",
    )
    for tag in suspicious_tags:
        if tag in lowered:
            raise ValueError(UNSUPPORTED_FORMAT)


def _strip_jpeg_exif(data: bytes) -> bytes:
    """Removes APP1 (EXIF) markers from JPEG without altering image stream."""
    if not (data.startswith(b"\xff\xd8")):
        return data

    result = bytearray(b"\xff\xd8")
    offset = 2
    length = len(data)

    while offset < length:
        if offset + 1 >= length:
            break
        marker_prefix, marker_type = data[offset], data[offset + 1]
        if marker_prefix != 0xFF:
            # Reached raw scan data
            result.extend(data[offset:])
            break
        offset += 2

        # Standalone markers (SOI, EOI, RSTn)
        if marker_type in (0xD8, 0xD9, 0x01) or (0xD0 <= marker_type <= 0xD7):
            result.extend([0xFF, marker_type])
            continue

        if offset + 2 > length:
            break
        seg_len = struct.unpack(">H", data[offset : offset + 2])[0]
        seg_data = data[offset + 2 : offset + seg_len]

        # 0xE1 is APP1 (EXIF / XMP) - Skip it to strip metadata!
        if marker_type != 0xE1:
            result.extend([0xFF, marker_type])
            result.extend(struct.pack(">H", seg_len))
            result.extend(seg_data)

        offset += seg_len
        # SOS (Start of Scan) marks the beginning of entropy-coded image data
        if marker_type == 0xDA:
            result.extend(data[offset:])
            break

    return bytes(result)


def _strip_png_exif(data: bytes) -> bytes:
    """Removes ancillary metadata chunks (tEXt, zTXt, iTXt, eXIf) from PNG."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data

    result = bytearray(b"\x89PNG\r\n\x1a\n")
    offset = 8
    length = len(data)
    skip_chunks = {b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"dSIG"}

    while offset + 8 <= length:
        chunk_len = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        total_chunk_len = 12 + chunk_len
        if offset + total_chunk_len > length:
            break
        chunk_bytes = data[offset : offset + total_chunk_len]

        if chunk_type not in skip_chunks:
            result.extend(chunk_bytes)

        offset += total_chunk_len
        if chunk_type == b"IEND":
            break

    return bytes(result)


def _extract_mp4_duration(data: bytes) -> float | None:
    """Extracts duration in seconds by parsing the MP4 mvhd box."""
    offset = 0
    length = len(data)

    def scan_boxes(start: int, end: int) -> float | None:
        pos = start
        while pos + 8 <= end:
            box_size = struct.unpack(">I", data[pos : pos + 4])[0]
            box_type = data[pos + 4 : pos + 8]
            if box_size == 1 and pos + 16 <= end:
                box_size = struct.unpack(">Q", data[pos + 8 : pos + 16])[0]
                content_start = pos + 16
            else:
                content_start = pos + 8
            if box_size == 0 or pos + box_size > end:
                box_size = end - pos

            if box_type == b"moov":
                res = scan_boxes(content_start, pos + box_size)
                if res is not None:
                    return res
            elif box_type == b"mvhd":
                mvhd_data = data[content_start : pos + box_size]
                if len(mvhd_data) >= 20:
                    version = mvhd_data[0]
                    if version == 0 and len(mvhd_data) >= 20:
                        timescale = struct.unpack(">I", mvhd_data[12:16])[0]
                        duration = struct.unpack(">I", mvhd_data[16:20])[0]
                        if timescale > 0:
                            return float(duration) / float(timescale)
                    elif version == 1 and len(mvhd_data) >= 28:
                        timescale = struct.unpack(">I", mvhd_data[20:24])[0]
                        duration = struct.unpack(">Q", mvhd_data[24:32])[0]
                        if timescale > 0:
                            return float(duration) / float(timescale)
            pos += box_size
        return None

    return scan_boxes(offset, length)


def _extract_webm_duration(data: bytes) -> float | None:
    """Extracts duration from WebM Segment Information element."""
    # Look for Duration element ID 0x4489 in first 32KB
    idx = data[:32768].find(b"\x44\x89")
    if idx != -1 and idx + 6 <= len(data):
        size_byte = data[idx + 2]
        if size_byte == 0x84 and idx + 7 <= len(data):  # 4-byte float
            val = struct.unpack(">f", data[idx + 3 : idx + 7])[0]
            return float(val) / 1000.0 if val > 1000.0 else float(val)
        if size_byte == 0x88 and idx + 11 <= len(data):  # 8-byte float
            val = struct.unpack(">d", data[idx + 3 : idx + 11])[0]
            return float(val) / 1000.0 if val > 1000.0 else float(val)
    return None


def validate_and_sanitize_evidence_file(
    original_filename: str,
    raw_data: bytes,
) -> ValidatedFile:
    """Performs strict binary validation, size checks, EXIF stripping, and polyglot detection."""
    if not raw_data:
        raise ValueError(UNSUPPORTED_FORMAT)

    file_size = len(raw_data)
    _check_polyglots_and_scripts(raw_data)

    # 1. Check JPEG
    if raw_data.startswith(b"\xff\xd8\xff"):
        if file_size > MAX_IMAGE_SIZE:
            raise ValueError(FILE_TOO_LARGE)
        sanitized = _strip_jpeg_exif(raw_data)
        sha256 = hashlib.sha256(sanitized).hexdigest()
        return ValidatedFile(
            sanitized_bytes=sanitized,
            file_type=EvidenceType.IMAGE,
            mime_type="image/jpeg",
            extension=".jpg",
            sha256_hash=sha256,
            duration_seconds=None,
        )

    # 2. Check PNG
    if raw_data.startswith(b"\x89PNG\r\n\x1a\n"):
        if file_size > MAX_IMAGE_SIZE:
            raise ValueError(FILE_TOO_LARGE)
        sanitized = _strip_png_exif(raw_data)
        sha256 = hashlib.sha256(sanitized).hexdigest()
        return ValidatedFile(
            sanitized_bytes=sanitized,
            file_type=EvidenceType.IMAGE,
            mime_type="image/png",
            extension=".png",
            sha256_hash=sha256,
            duration_seconds=None,
        )

    # 3. Check WEBP
    if raw_data.startswith(b"RIFF") and len(raw_data) >= 12 and raw_data[8:12] == b"WEBP":
        if file_size > MAX_IMAGE_SIZE:
            raise ValueError(FILE_TOO_LARGE)
        sha256 = hashlib.sha256(raw_data).hexdigest()
        return ValidatedFile(
            sanitized_bytes=raw_data,
            file_type=EvidenceType.IMAGE,
            mime_type="image/webp",
            extension=".webp",
            sha256_hash=sha256,
            duration_seconds=None,
        )

    # 4. Check MP4
    if len(raw_data) >= 12 and raw_data[4:8] == b"ftyp":
        if file_size > MAX_VIDEO_SIZE:
            raise ValueError(FILE_TOO_LARGE)
        duration = _extract_mp4_duration(raw_data)
        if duration is not None and duration > MAX_VIDEO_DURATION_SECONDS:
            raise ValueError(VIDEO_TOO_LONG)
        sha256 = hashlib.sha256(raw_data).hexdigest()
        return ValidatedFile(
            sanitized_bytes=raw_data,
            file_type=EvidenceType.VIDEO,
            mime_type="video/mp4",
            extension=".mp4",
            sha256_hash=sha256,
            duration_seconds=duration,
        )

    # 5. Check WEBM
    if raw_data.startswith(b"\x1a\x45\xdf\xa3"):
        if file_size > MAX_VIDEO_SIZE:
            raise ValueError(FILE_TOO_LARGE)
        duration = _extract_webm_duration(raw_data)
        if duration is not None and duration > MAX_VIDEO_DURATION_SECONDS:
            raise ValueError(VIDEO_TOO_LONG)
        sha256 = hashlib.sha256(raw_data).hexdigest()
        return ValidatedFile(
            sanitized_bytes=raw_data,
            file_type=EvidenceType.VIDEO,
            mime_type="video/webm",
            extension=".webm",
            sha256_hash=sha256,
            duration_seconds=duration,
        )

    # 6. Check Text / Log File (.log, .txt only)
    lower_name = original_filename.lower()
    if lower_name.endswith((".log", ".txt")):
        if file_size > MAX_LOG_SIZE:
            raise ValueError(FILE_TOO_LARGE)
        if b"\x00" not in raw_data:
            try:
                raw_data.decode("utf-8")
                sha256 = hashlib.sha256(raw_data).hexdigest()
                ext = ".log" if lower_name.endswith(".log") else ".txt"
                return ValidatedFile(
                    sanitized_bytes=raw_data,
                    file_type=EvidenceType.LOG,
                    mime_type="text/plain",
                    extension=ext,
                    sha256_hash=sha256,
                    duration_seconds=None,
                )
            except UnicodeDecodeError:
                pass

    # Any other binary/unrecognized format is rejected
    raise ValueError(UNSUPPORTED_FORMAT)
