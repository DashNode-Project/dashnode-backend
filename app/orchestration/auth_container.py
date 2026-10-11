"""
Composition root for Auth module use cases.
@sad AD-09, HC-08
@origin [SAD-Propuesto]
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.modules.auth.application.use_cases import (
    GetCurrentUserUseCase,
    LoginUseCase,
    RegisterUserUseCase,
)
from app.modules.auth.infrastructure.repositories import SqlAlchemyUserRepository
from app.modules.auth.infrastructure.token_service import JwtTokenService
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork
from app.shared.infrastructure.database import get_db_session as get_db
from app.shared.infrastructure.hasher import Argon2PasswordHasher
from app.shared.infrastructure.id_generator import UuidGenerator

clock = SystemClock()
id_generator = UuidGenerator()
password_hasher = Argon2PasswordHasher()
token_service = JwtTokenService(clock=clock)


def get_register_user_use_case(
    db: Session = Depends(get_db),
) -> RegisterUserUseCase:
    user_repo = SqlAlchemyUserRepository(session=db)
    uow = SqlAlchemyUnitOfWork(session=db)
    return RegisterUserUseCase(
        user_repo=user_repo,
        hasher=password_hasher,
        id_gen=id_generator,
        clock=clock,
        uow=uow,
    )


def get_login_use_case(
    db: Session = Depends(get_db),
) -> LoginUseCase:
    user_repo = SqlAlchemyUserRepository(session=db)
    return LoginUseCase(
        user_repo=user_repo,
        hasher=password_hasher,
        token_service=token_service,
    )


def get_current_user_use_case(
    db: Session = Depends(get_db),
) -> GetCurrentUserUseCase:
    user_repo = SqlAlchemyUserRepository(session=db)
    return GetCurrentUserUseCase(user_repo=user_repo)
