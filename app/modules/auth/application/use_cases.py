"""
Use cases for authentication and user management.
@sad AD-09, 4.1.1
@origin [SAD-Propuesto]
"""

from app.modules.auth.application.dtos import (
    LoginCommand,
    RegisterUserCommand,
    TokenResponse,
    UserDTO,
)
from app.modules.auth.domain.entities import User
from app.modules.auth.domain.ports import TokenService, UserRepository
from app.shared.application.ports import Clock, IdGenerator, PasswordHasher, UnitOfWork


class RegisterUserUseCase:
    """Handles new user registration."""

    def __init__(
        self,
        user_repo: UserRepository,
        hasher: PasswordHasher,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._user_repo = user_repo
        self._hasher = hasher
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow

    def execute(self, cmd: RegisterUserCommand) -> UserDTO:
        existing = self._user_repo.get_by_email(str(cmd.email))
        if existing is not None:
            raise ValueError(f"El correo '{cmd.email}' ya se encuentra registrado.")

        now = self._clock.now()
        hashed = self._hasher.hash(cmd.password)
        new_id = self._id_gen.generate()

        user = User(
            id=new_id,
            email=str(cmd.email),
            hashed_password=hashed,
            name=cmd.name,
            role=cmd.role,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        with self._uow:
            self._user_repo.save(user)
            self._uow.commit()

        return UserDTO(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        )


class LoginUseCase:
    """Handles user authentication and JWT generation."""

    def __init__(
        self,
        user_repo: UserRepository,
        hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        self._user_repo = user_repo
        self._hasher = hasher
        self._token_service = token_service

    def execute(self, cmd: LoginCommand) -> TokenResponse:
        user = self._user_repo.get_by_email(str(cmd.email))
        if user is None:
            raise ValueError("Credenciales inválidas.")

        if not self._hasher.verify(cmd.password, user.hashed_password):
            raise ValueError("Credenciales inválidas.")

        if not user.can_authenticate():
            raise ValueError("La cuenta de usuario está desactivada.")

        token = self._token_service.create_access_token(
            user_id=user.id,
            role=user.role.value,
            email=user.email,
            name=user.name,
        )
        return TokenResponse(access_token=token, token_type="bearer")  # noqa: S106


class GetCurrentUserUseCase:
    """Retrieves profile for an authenticated user."""

    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    def execute(self, user_id: str) -> UserDTO:
        user = self._user_repo.get_by_id(user_id)
        if user is None:
            raise ValueError("Usuario no encontrado.")

        return UserDTO(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
        )
