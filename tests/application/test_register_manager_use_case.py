"""
HU_DN_01_02 - Registrar cuenta con rol Gerente (application layer).
Traceability: TK_DN_01_02_3, TK_DN_01_02_4, TK_DN_01_02_5.
"""

import pytest

from app.modules.auth.application.dtos import RegisterManagerCommand
from app.modules.auth.application.use_cases import RegisterManagerUseCase
from app.modules.auth.domain import messages
from app.modules.auth.domain.entities import UserRole
from app.modules.auth.domain.errors import (
    EmailAlreadyRegisteredError,
    RegistrationRoleNotAllowedError,
    RegistrationValidationError,
)
from tests.fakes import (
    T0,
    FakeClock,
    FakeIdGenerator,
    FakePasswordHasher,
    FakeUnitOfWork,
    FakeUserRepository,
    make_user,
)

VALID_PASSWORD = "Segura123"


def _build() -> tuple[RegisterManagerUseCase, FakeUserRepository, FakeUnitOfWork]:
    repo = FakeUserRepository()
    uow = FakeUnitOfWork()
    use_case = RegisterManagerUseCase(
        user_repo=repo,
        hasher=FakePasswordHasher(),
        id_gen=FakeIdGenerator("user-123"),
        clock=FakeClock(),
        uow=uow,
    )
    return use_case, repo, uow


def _cmd(**overrides: str | None) -> RegisterManagerCommand:
    data: dict[str, str | None] = {
        "name": "Ana Gómez",
        "email": "ana@empresa.com",
        "password": VALID_PASSWORD,
        "confirm_password": VALID_PASSWORD,
    }
    data.update(overrides)
    return RegisterManagerCommand(**data)


def test_registers_manager_with_hashed_password_and_literal_success_message() -> None:
    use_case, repo, uow = _build()

    result = use_case.execute(_cmd())

    assert (
        result.message
        == "Su cuenta de Gerente ha sido registrada correctamente. Puede iniciar sesión."
    )
    assert result.user.id == "user-123"
    assert result.user.role is UserRole.MANAGER
    assert result.user.is_active is True
    assert result.user.created_at == T0
    assert uow.committed is True
    stored = repo.get_by_id("user-123")
    assert stored is not None
    assert stored.hashed_password == f"hashed_{VALID_PASSWORD}"
    assert VALID_PASSWORD not in result.model_dump_json()


def test_normalizes_email_and_trims_name() -> None:
    use_case, repo, _ = _build()
    use_case.execute(_cmd(email="  Ana@Empresa.COM ", name="  Ana Gómez  "))
    stored = repo.get_by_email("ana@empresa.com")
    assert stored is not None
    assert stored.name == "Ana Gómez"


def test_accepts_explicit_manager_role_and_name_of_exactly_100_chars() -> None:
    use_case, _, _ = _build()
    result = use_case.execute(_cmd(role="manager", name="N" * 100))
    assert result.user.role is UserRole.MANAGER


@pytest.mark.parametrize("role", ["admin", "developer", "Admin", "gerente", ""])
def test_rejects_any_role_other_than_manager(role: str) -> None:
    use_case, repo, uow = _build()
    with pytest.raises(RegistrationRoleNotAllowedError) as caught:
        use_case.execute(_cmd(role=role))
    assert caught.value.message == "El registro público solo está disponible para el rol Gerente."
    assert repo.users_by_id == {}
    assert uow.committed is False


def test_only_name_blank_uses_name_required_message() -> None:
    use_case, _, _ = _build()
    with pytest.raises(RegistrationValidationError) as caught:
        use_case.execute(_cmd(name="   "))
    assert caught.value.code == "NAME_REQUIRED"
    assert caught.value.message == "El nombre completo es obligatorio."
    assert caught.value.fields == {"name": messages.NAME_REQUIRED}


def test_multiple_blank_fields_use_required_fields_message() -> None:
    use_case, _, _ = _build()
    with pytest.raises(RegistrationValidationError) as caught:
        use_case.execute(_cmd(name="", email="", confirm_password=""))
    assert caught.value.code == "REQUIRED_FIELDS"
    assert caught.value.message == "Todos los campos obligatorios deben ser diligenciados."
    assert set(caught.value.fields) == {"name", "email", "confirm_password"}


@pytest.mark.parametrize(
    "email", ["sin-arroba", "a@b", "a@@b.co", "a b@c.co", "@x.co", "a@.co", "a@b..co"]
)
def test_invalid_email_format(email: str) -> None:
    use_case, repo, _ = _build()
    with pytest.raises(RegistrationValidationError) as caught:
        use_case.execute(_cmd(email=email))
    assert caught.value.message == "El correo electrónico ingresado no tiene un formato válido."
    assert caught.value.fields == {"email": messages.EMAIL_INVALID}
    assert repo.users_by_id == {}


@pytest.mark.parametrize(
    "password",
    ["Corta1", "soloLetrasAqui", "123456789", "a1" * 33],  # <8, no digit, no letter, >64
)
def test_weak_password(password: str) -> None:
    use_case, repo, _ = _build()
    with pytest.raises(RegistrationValidationError) as caught:
        use_case.execute(_cmd(password=password, confirm_password=password))
    assert caught.value.message == "La contraseña no cumple los requisitos mínimos de seguridad."
    assert "password" in caught.value.fields
    assert repo.users_by_id == {}


def test_password_boundaries_are_inclusive() -> None:
    use_case, _, _ = _build()
    for index, password in enumerate(["Abcdef12", "a1" * 32]):  # 8 and 64 characters
        use_case.execute(
            _cmd(email=f"u{index}@empresa.com", password=password, confirm_password=password)
        )


def test_password_mismatch() -> None:
    use_case, repo, _ = _build()
    with pytest.raises(RegistrationValidationError) as caught:
        use_case.execute(_cmd(confirm_password="Otra12345"))
    assert caught.value.message == "Las contraseñas no coinciden."
    assert caught.value.fields == {"confirm_password": messages.PASSWORD_MISMATCH}
    assert repo.users_by_id == {}


def test_name_longer_than_100_characters_is_rejected() -> None:
    use_case, _, _ = _build()
    with pytest.raises(RegistrationValidationError) as caught:
        use_case.execute(_cmd(name="N" * 101))
    assert caught.value.code == "NAME_TOO_LONG"


def test_reports_every_invalid_field_with_first_error_as_message() -> None:
    use_case, _, _ = _build()
    with pytest.raises(RegistrationValidationError) as caught:
        use_case.execute(_cmd(email="malo", password="corta", confirm_password="corta"))
    assert caught.value.message == messages.EMAIL_INVALID
    assert set(caught.value.fields) == {"email", "password"}


def test_duplicate_email_is_rejected_case_insensitively() -> None:
    use_case, repo, uow = _build()
    repo.save(make_user(email="ana@empresa.com"))
    with pytest.raises(EmailAlreadyRegisteredError) as caught:
        use_case.execute(_cmd(email="ANA@empresa.com"))
    assert caught.value.message == "Ya existe una cuenta registrada con este correo electrónico."
    assert caught.value.code == "EMAIL_ALREADY_REGISTERED"
    assert uow.committed is False


def test_race_on_unique_index_surfaces_as_duplicate_and_rolls_back() -> None:
    use_case, repo, uow = _build()

    original_get = repo.get_by_email
    repo.get_by_email = lambda email: None  # type: ignore[method-assign]  # lookup misses
    repo.users_by_email["ana@empresa.com"] = make_user(user_id="other", email="ana@empresa.com")
    with pytest.raises(EmailAlreadyRegisteredError):
        use_case.execute(_cmd())
    repo.get_by_email = original_get  # type: ignore[method-assign]
    assert uow.rolled_back is True
    assert uow.committed is False
