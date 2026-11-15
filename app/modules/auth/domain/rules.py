"""
Pure validation rules for credentials and profile data (HU_DN_01_02).
@sad 4.1.1
@origin [HU-Spec]
"""

import re

NAME_MAX_LENGTH = 100
EMAIL_MAX_LENGTH = 254
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 64

# xxx@xxx.xxx : a local part, an '@' and a domain with at least one dot; no spaces.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


def normalize_email(email: str) -> str:
    """Canonical form used for storage and lookups (case-insensitive uniqueness)."""
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    return len(email) <= EMAIL_MAX_LENGTH and _EMAIL_PATTERN.fullmatch(email) is not None


def is_valid_password(password: str) -> bool:
    """8-64 characters with at least one letter and one digit."""
    return (
        PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH
        and any(char.isalpha() for char in password)
        and any(char.isdigit() for char in password)
    )
