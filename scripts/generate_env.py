#!/usr/bin/env python3
"""Generate a local `.env` from `.env.example` with freshly generated random secrets.

Usage:
    python scripts/generate_env.py            # create .env (refuses to overwrite)
    python scripts/generate_env.py --force    # regenerate (rotates every secret)

Only variable NAMES are printed, never their values. The generated file is git-ignored.
Standard library only, so it runs before any dependency is installed.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import secrets
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.example"
TARGET = ROOT / ".env"

PLACEHOLDER_DB = "CHANGE_ME_DB_PASSWORD"
SEED_PLACEHOLDERS = {
    "CHANGE_ME_SEED_ADMIN_PASSWORD",
    "CHANGE_ME_SEED_MANAGER_PASSWORD",
    "CHANGE_ME_SEED_DEVELOPER_PASSWORD",
    "CHANGE_ME_SEED_DISABLED_PASSWORD",
}


def _user_password() -> str:
    """Random password that satisfies the product policy (letters + digits, 8-64)."""
    return secrets.token_urlsafe(15) + "aZ7"


def build_env() -> tuple[str, list[str]]:
    content = EXAMPLE.read_text(encoding="utf-8")
    generated: list[str] = []

    db_password = secrets.token_urlsafe(24)  # URL-safe alphabet: safe inside DATABASE_URL
    if PLACEHOLDER_DB in content:
        content = content.replace(PLACEHOLDER_DB, db_password)
        generated.append("POSTGRES_PASSWORD / DATABASE_URL")

    for placeholder in sorted(SEED_PLACEHOLDERS):
        if placeholder in content:
            content = content.replace(placeholder, _user_password())
            generated.append(
                placeholder.replace("CHANGE_ME_", "").replace("_PASSWORD", "") + "_PASSWORD"
            )
    return content, generated


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--force", action="store_true", help="overwrite an existing .env")
    args = parser.parse_args()

    if not EXAMPLE.exists():
        print(f"Missing template: {EXAMPLE.name}", file=sys.stderr)
        return 1
    if TARGET.exists() and not args.force:
        print(".env already exists; use --force to regenerate (this rotates all secrets).")
        return 0

    content, generated = build_env()
    TARGET.write_text(content, encoding="utf-8", newline="\n")
    with contextlib.suppress(OSError):  # best effort on filesystems without POSIX permissions
        os.chmod(TARGET, stat.S_IRUSR | stat.S_IWUSR)

    print("Created .env (git-ignored). Random values generated for:")
    for name in generated:
        print(f"  - {name}")
    print("Review SMTP_* and FRONTEND_BASE_URL before using mail features.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
