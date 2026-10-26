"""
Use cases around server-side sessions: login (HU_DN_01_03) and session validation
(shared by HU_DN_01_04 / HU_DN_01_05).
@sad AD-09, 4.1.1
@origin [HU-Spec]
"""

from app.modules.auth.application.dtos import (
    LoginCommand,
    LoginResult,
    LogoutResponse,
    SecurityPolicy,
    SessionInfo,
)
from app.modules.auth.application.mappers import to_user_dto
from app.modules.auth.domain import messages
from app.modules.auth.domain.entities import LoginAttempt, UserSession
from app.modules.auth.domain.errors import (
    AccountDisabledError,
    InvalidCredentialsError,
    LoginAttemptsExceededError,
    LoginValidationError,
    NotAuthenticatedError,
    SessionExpiredError,
)
from app.modules.auth.domain.ports import (
    LoginAttemptRepository,
    SessionRepository,
    SessionTokenService,
    UserRepository,
)
from app.modules.auth.domain.rules import is_valid_email, normalize_email
from app.shared.application.ports import Clock, IdGenerator, PasswordHasher, UnitOfWork
from app.shared.domain.errors import AppError, ErrorKind


class LoginUseCase:
    """Authenticate credentials and open a server-side session (HU_DN_01_03).

    Order of checks (each one maps to a literal story message):
      1. blank / malformed input            -> 400, never counted as an attempt
      2. attempt ledger (max N per window)  -> 429, the correct password is NOT checked
      3. unknown e-mail or wrong password   -> 401 (indistinguishable, constant work)
      4. correct password but disabled user -> 403
      5. success                            -> new session, ledger reset
    """

    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
        attempt_repo: LoginAttemptRepository,
        hasher: PasswordHasher,
        tokens: SessionTokenService,
        id_gen: IdGenerator,
        clock: Clock,
        uow: UnitOfWork,
        policy: SecurityPolicy,
    ) -> None:
        self._users = user_repo
        self._sessions = session_repo
        self._attempts = attempt_repo
        self._hasher = hasher
        self._tokens = tokens
        self._id_gen = id_gen
        self._clock = clock
        self._uow = uow
        self._policy = policy

    @staticmethod
    def _validate(email: str, password: str) -> None:
        if not email or not password.strip():
            fields = {
                name: messages.REQUIRED_FIELDS
                for name, value in (("email", email), ("password", password.strip()))
                if not value
            }
            raise LoginValidationError("REQUIRED_FIELDS", messages.REQUIRED_FIELDS, fields)
        if not is_valid_email(email):
            raise LoginValidationError(
                "EMAIL_INVALID", messages.EMAIL_INVALID, {"email": messages.EMAIL_INVALID}
            )

    def _reserve_attempt(self, email: str) -> None:
        """Record the attempt BEFORE verifying so concurrent bursts cannot exceed the limit."""
        now = self._clock.now()
        window_start = now - self._policy.attempt_window
        attempt = LoginAttempt(id=self._id_gen.generate(), email=email, attempted_at=now)
        with self._uow:
            self._attempts.purge_before(window_start)
            self._attempts.add(attempt)
            self._uow.commit()
            if self._attempts.count_since(email, window_start) > self._policy.max_failed_attempts:
                # Rejected attempts are not recorded, so the lock is not extended by them.
                self._attempts.delete(attempt.id)
                self._uow.commit()
                raise LoginAttemptsExceededError

    def execute(self, cmd: LoginCommand) -> LoginResult:
        email = normalize_email(cmd.email)
        self._validate(email, cmd.password)
        self._reserve_attempt(email)

        user = self._users.get_by_email(email)
        if user is None:
            self._hasher.verify_dummy(cmd.password)  # equalise timing with a real check
            raise InvalidCredentialsError
        if not self._hasher.verify(cmd.password, user.hashed_password):
            raise InvalidCredentialsError
        if user.invitation_status == "pending":
            raise AppError("INVITATION_PENDING", messages.INVITATION_PENDING, ErrorKind.FORBIDDEN)
        if user.invitation_status == "rejected":
            raise AppError(
                "INVITATION_REJECTED", messages.INVITATION_REJECTED_LOGIN, ErrorKind.FORBIDDEN
            )
        if not user.can_authenticate():
            with self._uow:
                self._attempts.clear_for(email)  # credentials were right: not a guess
                self._uow.commit()
            raise AccountDisabledError

        now = self._clock.now()
        mark_invite_accepted = (
            user.invited_by_user_id is not None and user.invitation_accepted_at is None
        )
        if mark_invite_accepted:
            user.invitation_accepted_at = now
            user.updated_at = now
        token = self._tokens.new_token()
        session = UserSession(
            id=self._id_gen.generate(),
            user_id=user.id,
            token_hash=self._tokens.digest(token),
            created_at=now,
            expires_at=now + self._policy.session_ttl,
        )
        with self._uow:
            self._attempts.clear_for(email)
            # Sessions older than their cookie retention can never be presented again.
            self._sessions.purge_expired_before(now - self._policy.session_retention)
            if mark_invite_accepted:
                self._users.update(user)
            self._sessions.add(session)
            self._uow.commit()

        return LoginResult(
            session=SessionInfo(user=to_user_dto(user), expires_at=session.expires_at),
            token=token,
        )


class AuthenticateSessionUseCase:
    """Resolve the session behind a cookie token or raise the matching error.

    Used by every protected endpoint and by the "who am I" endpoint of HU_DN_01_05.
    """

    def __init__(
        self,
        user_repo: UserRepository,
        session_repo: SessionRepository,
        tokens: SessionTokenService,
        clock: Clock,
    ) -> None:
        self._users = user_repo
        self._sessions = session_repo
        self._tokens = tokens
        self._clock = clock

    def execute(self, token: str | None) -> SessionInfo:
        if not token:
            raise NotAuthenticatedError
        session = self._sessions.get_by_token_hash(self._tokens.digest(token))
        if session is None or session.is_revoked():
            raise NotAuthenticatedError
        if session.is_expired(self._clock.now()):
            raise SessionExpiredError
        user = self._users.get_by_id(session.user_id)
        if user is None:
            raise NotAuthenticatedError
        if not user.can_authenticate():
            raise AccountDisabledError
        return SessionInfo(user=to_user_dto(user), expires_at=session.expires_at)


class LogoutUseCase:
    """Invalidate the server-side session behind the cookie (HU_DN_01_04).

    Idempotent: an unknown, expired or already revoked session still ends with the
    client being logged out, so the UI can always clear its state and go to login.
    """

    def __init__(
        self,
        session_repo: SessionRepository,
        tokens: SessionTokenService,
        clock: Clock,
        uow: UnitOfWork,
    ) -> None:
        self._sessions = session_repo
        self._tokens = tokens
        self._clock = clock
        self._uow = uow

    def execute(self, token: str | None) -> LogoutResponse:
        if token:
            session = self._sessions.get_by_token_hash(self._tokens.digest(token))
            if session is not None and not session.is_revoked():
                session.revoke(self._clock.now())
                with self._uow:
                    self._sessions.update(session)
                    self._uow.commit()
        return LogoutResponse(message=messages.LOGOUT_SUCCESS)
