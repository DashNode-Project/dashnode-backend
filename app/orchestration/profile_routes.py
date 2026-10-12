"""Profile and avatar routes (HU_DN_01_21)."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.modules.auth.application.dtos import ProfileResponse, UpdateProfileCommand
from app.modules.auth.application.profile_use_cases import GetProfileUseCase, UpdateProfileUseCase
from app.modules.auth.infrastructure.avatar_storage import LocalAvatarStorage
from app.modules.auth.infrastructure.repositories import SqlAlchemyUserRepository
from app.orchestration.security import get_current_user
from app.shared.application.identity import CurrentUser
from app.shared.infrastructure.clock import SystemClock
from app.shared.infrastructure.database import SqlAlchemyUnitOfWork, get_db_session

router = APIRouter(prefix="/auth", tags=["auth"])
_clock = SystemClock()
_storage = LocalAvatarStorage()


@router.get("/profile", response_model=ProfileResponse)
def get_profile(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ProfileResponse:
    use_case = GetProfileUseCase(user_repo=SqlAlchemyUserRepository(session=db))
    return use_case.execute(user_id=current_user.id)


@router.patch("/profile", response_model=ProfileResponse)
async def update_profile(
    name: str = Form(default=""),
    avatar: UploadFile | None = File(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ProfileResponse:
    avatar_bytes: bytes | None = None
    if avatar is not None and avatar.filename:
        avatar_bytes = await avatar.read()
    use_case = UpdateProfileUseCase(
        user_repo=SqlAlchemyUserRepository(session=db),
        storage=_storage,
        clock=_clock,
        uow=SqlAlchemyUnitOfWork(session=db),
    )
    return use_case.execute(
        user_id=current_user.id,
        cmd=UpdateProfileCommand(name=name),
        avatar_bytes=avatar_bytes,
    )


@router.get("/profile/avatar")
def get_avatar(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> Response:
    user = SqlAlchemyUserRepository(session=db).get_by_id(current_user.id)
    if user is None or not user.avatar_key:
        return Response(status_code=404)
    try:
        content, media_type = _storage.read(user.avatar_key)
    except FileNotFoundError:
        return Response(status_code=404)
    return Response(content=content, media_type=media_type)
