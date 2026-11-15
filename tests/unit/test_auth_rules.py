"""
Property-based tests for the credential rules (HU_DN_01_02, HU_DN_01_03).
"""

import string

from hypothesis import given
from hypothesis import strategies as st

from app.modules.auth.domain.rules import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    is_valid_email,
    is_valid_password,
    normalize_email,
)

_LABEL = st.text(alphabet=string.ascii_lowercase + string.digits + "-", min_size=1, max_size=12)


@given(
    local=st.text(alphabet=string.ascii_letters + string.digits + "._%+-", min_size=1, max_size=30),
    labels=st.lists(_LABEL, min_size=2, max_size=4),
)
def test_well_formed_addresses_are_valid(local: str, labels: list[str]) -> None:
    assert is_valid_email(f"{local}@{'.'.join(labels)}")


@given(st.text(max_size=60).filter(lambda value: "@" not in value))
def test_addresses_without_at_sign_are_invalid(value: str) -> None:
    assert not is_valid_email(value)


@given(st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=10))
def test_domain_without_dot_is_invalid(domain: str) -> None:
    assert not is_valid_email(f"user@{domain}")


@given(st.text(max_size=80))
def test_email_never_contains_whitespace_when_valid(value: str) -> None:
    if is_valid_email(value):
        assert not any(char.isspace() for char in value)


@given(st.text(max_size=300))
def test_normalize_email_is_idempotent_and_lowercase(value: str) -> None:
    once = normalize_email(value)
    assert normalize_email(once) == once
    assert once == once.lower()


@given(st.text(max_size=PASSWORD_MIN_LENGTH - 1))
def test_short_passwords_are_invalid(value: str) -> None:
    assert not is_valid_password(value)


@given(
    st.text(
        alphabet=string.ascii_letters + string.digits,
        min_size=PASSWORD_MAX_LENGTH + 1,
        max_size=120,
    )
)
def test_long_passwords_are_invalid(value: str) -> None:
    assert not is_valid_password(value)


@given(
    st.text(
        alphabet=string.ascii_letters, min_size=PASSWORD_MIN_LENGTH, max_size=PASSWORD_MAX_LENGTH
    )
)
def test_passwords_without_digit_are_invalid(value: str) -> None:
    assert not is_valid_password(value)


@given(st.text(alphabet=string.digits, min_size=PASSWORD_MIN_LENGTH, max_size=PASSWORD_MAX_LENGTH))
def test_passwords_without_letter_are_invalid(value: str) -> None:
    assert not is_valid_password(value)


@given(
    letters=st.text(alphabet=string.ascii_letters, min_size=4, max_size=30),
    digits=st.text(alphabet=string.digits, min_size=4, max_size=30),
)
def test_letters_plus_digits_within_bounds_are_valid(letters: str, digits: str) -> None:
    assert is_valid_password(letters + digits)
