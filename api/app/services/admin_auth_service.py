import uuid
from dataclasses import dataclass
from datetime import timedelta

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.passwords import DUMMY_HASH, verify_password
from app.core.security import AdminTokenClaims, TokenService, generate_refresh_token
from app.db.unit_of_work import UnitOfWork
from app.models import AdminSession, AdminUser
from app.repositories.admin import AdminSessionRepository, AdminUserRepository

USER_AGENT_MAX_LENGTH = 300


@dataclass(frozen=True, slots=True)
class AdminTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    admin: AdminUser


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AdminAuthService:
    def __init__(self, uow: UnitOfWork, settings: Settings, tokens: TokenService) -> None:
        self._uow = uow
        self._settings = settings
        self._tokens = tokens
        self._admins = AdminUserRepository(uow.session)
        self._sessions = AdminSessionRepository(uow.session)

    async def login(self, email: str, password: str, user_agent: str | None) -> AdminTokens:
        admin = await self._admins.by_email(normalize_email(email))
        now = utcnow()
        if admin is None or not admin.is_active:
            verify_password(password, DUMMY_HASH)
            raise AppError(ErrorCode.INVALID_CREDENTIALS)
        if admin.locked_until is not None and admin.locked_until > now:
            raise AppError(ErrorCode.ACCOUNT_LOCKED)
        if not verify_password(password, admin.password_hash):
            admin.failed_attempts += 1
            if admin.failed_attempts >= self._settings.admin_max_failed_logins:
                admin.failed_attempts = 0
                admin.locked_until = now + timedelta(minutes=self._settings.admin_lockout_minutes)
            await self._uow.commit()
            raise AppError(ErrorCode.INVALID_CREDENTIALS)
        admin.failed_attempts = 0
        admin.locked_until = None
        admin.last_login_at = now
        refresh_token = generate_refresh_token()
        session = self._sessions.add(
            AdminSession(
                id=uuid.uuid4(),
                admin_id=admin.id,
                refresh_token_hash=self._tokens.hash_secret(refresh_token),
                user_agent=(user_agent or "")[:USER_AGENT_MAX_LENGTH] or None,
                expires_at=now + self._tokens.admin_refresh_ttl,
                last_seen_at=now,
            )
        )
        await self._uow.commit()
        return self._issue(admin, session, refresh_token)

    async def refresh(self, refresh_token: str) -> AdminTokens:
        session = await self._sessions.by_refresh_hash(self._tokens.hash_secret(refresh_token))
        now = utcnow()
        if session is None or session.revoked_at is not None or session.expires_at <= now:
            raise AppError(ErrorCode.UNAUTHENTICATED)
        admin = await self._admins.get(session.admin_id)
        if admin is None or not admin.is_active:
            raise AppError(ErrorCode.UNAUTHENTICATED)
        rotated = generate_refresh_token()
        session.refresh_token_hash = self._tokens.hash_secret(rotated)
        session.expires_at = now + self._tokens.admin_refresh_ttl
        session.last_seen_at = now
        await self._uow.commit()
        return self._issue(admin, session, rotated)

    async def logout(self, session_id: uuid.UUID) -> None:
        session = await self._sessions.get(session_id)
        if session is not None and session.revoked_at is None:
            session.revoked_at = utcnow()
            await self._uow.commit()

    async def authenticate(self, claims: AdminTokenClaims) -> AdminUser:
        session = await self._sessions.get(claims.session_id)
        if (
            session is None
            or session.admin_id != claims.admin_id
            or session.revoked_at is not None
            or session.expires_at <= utcnow()
        ):
            raise AppError(ErrorCode.UNAUTHENTICATED)
        admin = await self._admins.get(claims.admin_id)
        if admin is None or not admin.is_active:
            raise AppError(ErrorCode.UNAUTHENTICATED)
        return admin

    def _issue(self, admin: AdminUser, session: AdminSession, refresh_token: str) -> AdminTokens:
        access = self._tokens.issue_admin_token(
            AdminTokenClaims(admin_id=admin.id, session_id=session.id)
        )
        return AdminTokens(
            access_token=access,
            refresh_token=refresh_token,
            expires_in=int(self._tokens.admin_access_ttl.total_seconds()),
            admin=admin,
        )
