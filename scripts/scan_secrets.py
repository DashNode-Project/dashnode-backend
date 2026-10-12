#!/usr/bin/env python3
"""Lightweight secret scanner used by the pre-commit hook and CI.

Usage:
    python scripts/scan_secrets.py            # scan staged files (pre-commit)
    python scripts/scan_secrets.py --all      # scan every tracked file (CI)

It never prints the matched value, only file, line and rule name.
Standard library only.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = "scripts/scan_secrets.py"

FORBIDDEN_PATHS = re.compile(r"(^|/)(\.env(\.(?!example$)[^/]+)?|[^/]+\.(pem|key|p12|pfx))$")

STRONG_RULES: dict[str, re.Pattern[str]] = {
    "private key block": re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    "AWS access key id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "JSON Web Token": re.compile(
        r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
    ),
}

URL_CREDENTIALS = re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@'\"]+:([^@\s'\"]+)@", re.IGNORECASE)
ASSIGNMENT = re.compile(
    r"""(?ix)
    \b[\w.-]*(password|passwd|secret|api[_-]?key|token|private[_-]?key)[\w.-]*
    \s*[:=]\s*
    ["']([^"'\s]{8,})["']
    """
)

PLACEHOLDER_HINTS = (
    "change_me",
    "changeme",
    "example",
    "placeholder",
    "your_",
    "<",
    "{",  # interpolation: ${VAR}, {value}, {{ template }}
    "%s",
    "xxx",
    "***",
    "dummy",
    "os.environ",
    "secrets.",
    "settings.",
    "getenv",
)

# Test code legitimately contains throwaway literals; only the strong rules and
# credentialed URLs apply there.
RELAXED_PREFIXES = ("tests/",)
SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".pdf", ".lock")


def _git(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(hint in lowered for hint in PLACEHOLDER_HINTS)


def scan_text(path: str, text: str) -> list[str]:
    findings: list[str] = []
    relaxed = path.startswith(RELAXED_PREFIXES)
    for number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in STRONG_RULES.items():
            if pattern.search(line):
                findings.append(f"{path}:{number}: {rule}")
        for match in URL_CREDENTIALS.finditer(line):
            if not _is_placeholder(match.group(1)):
                findings.append(f"{path}:{number}: credentials embedded in URL")
        if relaxed:
            continue
        for match in ASSIGNMENT.finditer(line):
            if not _is_placeholder(match.group(2)):
                findings.append(f"{path}:{number}: hardcoded secret-like assignment")
    return findings


def scan_paths(paths: list[str], reader=None) -> list[str]:  # type: ignore[no-untyped-def]
    findings: list[str] = []
    for path in paths:
        if path == SELF or path.endswith(SKIP_SUFFIXES):
            continue
        if FORBIDDEN_PATHS.search(path):
            findings.append(f"{path}: file type must never be versioned")
            continue
        try:
            text = reader(path) if reader else (ROOT / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        findings.extend(scan_text(path, text))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--all", action="store_true", help="scan all tracked files")
    args = parser.parse_args()

    if args.all:
        paths = _git("ls-files")
        findings = scan_paths(paths)
    else:
        paths = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR")

        def staged(path: str) -> str:
            return subprocess.run(
                ["git", "show", f":{path}"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
            ).stdout

        findings = scan_paths(paths, reader=staged)

    if findings:
        print("Potential secrets detected (values hidden):", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        print("Move real values to .env (git-ignored) or use a placeholder.", file=sys.stderr)
        return 1
    print(f"Secret scan clean ({len(paths)} files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
