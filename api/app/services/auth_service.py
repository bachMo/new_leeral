import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.languages import Language, ensure_available
from app.core.logging import mask_phone
from app.core.phone import normalize_phone_number
from app.core.security import (
    AccessTokenClaims,
    TokenService,
    generate_numeric_code,
    generate_refresh_token,
)
from app.db.unit_of_work import UnitOfWork
from app.models import AuthSession, OtpCode, User
from app.models.enums import Platform
from app.repositories.conversations import ConversationRepository
from app.repositories.documents import DocumentRepository
from app.repositories.users import AuthSessionRepository, OtpRepository, UserRepository
from app.repositories.writings import WritingRepository
from app.services.otp_delivery import OtpDelivery
from app.workers.jobs import Job

logger = logging.getLogger("leeral.auth")


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class AuthResult:
    user: User
    tokens: TokenPair
    is_new_account: bool = False


@dataclass(frozen=True, slots=True)
class OtpChallenge:
    phone_number: str
    expires_in: int
    resend_in: int
    code_length: int


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    platform: Platform
    device_name: str | None = None
    push_token: str | None = None


class AuthService:
    def __init__(
        self,
        uow: UnitOfWork,
        settings: Settings,
        tokens: TokenService,
        otp_delivery: OtpDelivery,
    ) -> None:
        self._uow = uow
        self._settings = settings
        self._tokens = tokens
        self._otp_delivery = otp_delivery
        self._users = UserRepository(uow.session)
        self._otps = OtpRepository(uow.session)
        self._sessions = AuthSessionRepository(uow.session)

    async def start_guest(
        self, device_id: str, language: Language, device: DeviceInfo
    ) -> AuthResult:
        ensure_available(language)
        user = await self._users.by_device(device_id)
        if user is None:
            user = self._users.add(
                User(language=language, is_guest=True, guest_device_id=device_id)
            )
            await self._users.flush()
        else:
            user.language = language
            user.last_seen_at = utcnow()
        tokens = await self._open_session(user, device)
        await self._uow.commit()
        return AuthResult(user=user, tokens=tokens)

    async def request_otp(self, raw_phone_number: str) -> OtpChallenge:
        phone_number = normalize_phone_number(raw_phone_number, self._settings.default_phone_region)
        now = utcnow()
        latest = await self._otps.latest_for(phone_number)
        cooldown = timedelta(seconds=self._settings.otp_resend_cooldown_seconds)
        if latest is not None and latest.consumed_at is None and now - latest.created_at < cooldown:
            remaining = int((cooldown - (now - latest.created_at)).total_seconds()) + 1
            raise AppError(ErrorCode.OTP_RESEND_TOO_SOON, fields={"resend_in": remaining})

        code = self._new_code()
        ttl = timedelta(minutes=self._settings.otp_ttl_minutes)
        self._otps.add(
            OtpCode(
                phone_number=phone_number,
                code_hash=self._tokens.hash_secret(f"{phone_number}:{code}"),
                expires_at=now + ttl,
            )
        )
        await self._otp_delivery.deliver(phone_number, code)
        await self._uow.commit()
        logger.info("otp_sent", extra={"phone": mask_phone(phone_number)})
        return OtpChallenge(
            phone_number=phone_number,
            expires_in=int(ttl.total_seconds()),
            resend_in=self._settings.otp_resend_cooldown_seconds,
            code_length=self._settings.otp_length,
        )

    async def verify_otp(
        self,
        raw_phone_number: str,
        code: str,
        language: Language,
        device: DeviceInfo,
        guest: User | None,
    ) -> AuthResult:
        phone_number = normalize_phone_number(raw_phone_number, self._settings.default_phone_region)
        await self._consume_otp(phone_number, code)
        now = utcnow()
        account = await self._users.by_phone(phone_number)
        is_new_account = account is None or account.registered_at is None

        if account is not None:
            if guest is not None and guest.id != account.id:
                await self._absorb_guest(guest, account)
        elif guest is not None and guest.is_guest:
            account = guest
            account.phone_number = phone_number
            account.is_guest = False
            account.guest_device_id = None
            self._uow.defer(Job.PROMOTE_GUEST_FILES, user_id=str(account.id))
        else:
            account = self._users.add(
                User(language=ensure_available(language), phone_number=phone_number)
            )
            await self._users.flush()

        if account.registered_at is None:
            account.registered_at = now
        account.last_seen_at = now
        tokens = await self._open_session(account, device)
        await self._uow.commit()
        logger.info("otp_verified", extra={"user_id": str(account.id), "new": is_new_account})
        return AuthResult(user=account, tokens=tokens, is_new_account=is_new_account)

    async def refresh(self, refresh_token: str) -> AuthResult:
        session = await self._sessions.by_refresh_hash(self._tokens.hash_secret(refresh_token))
        now = utcnow()
        if session is None or session.revoked_at is not None or session.expires_at <= now:
            raise AppError(ErrorCode.UNAUTHENTICATED)
        user = await self._users.get(session.user_id)
        if user is None:
            raise AppError(ErrorCode.UNAUTHENTICATED)
        new_refresh_token = generate_refresh_token()
        session.refresh_token_hash = self._tokens.hash_secret(new_refresh_token)
        session.expires_at = now + self._tokens.refresh_ttl
        session.last_seen_at = now
        user.last_seen_at = now
        await self._uow.commit()
        return AuthResult(user=user, tokens=self._token_pair(user, session.id, new_refresh_token))

    async def logout(self, session_id: uuid.UUID) -> None:
        session = await self._sessions.get(session_id)
        if session is not None and session.revoked_at is None:
            session.revoked_at = utcnow()
        await self._uow.commit()

    def _new_code(self) -> str:
        if self._settings.otp_delivery == "demo":
            return self._settings.otp_demo_code.get_secret_value()
        return generate_numeric_code(self._settings.otp_length)

    async def _consume_otp(self, phone_number: str, code: str) -> None:
        otp = await self._otps.latest_for(phone_number)
        now = utcnow()
        if otp is None or otp.consumed_at is not None:
            raise AppError(ErrorCode.OTP_INVALID)
        if otp.expires_at <= now:
            raise AppError(ErrorCode.OTP_EXPIRED)
        if otp.attempts >= self._settings.otp_max_attempts:
            raise AppError(ErrorCode.OTP_TOO_MANY_ATTEMPTS)
        if not self._tokens.verify_secret(f"{phone_number}:{code.strip()}", otp.code_hash):
            otp.attempts += 1
            await self._uow.commit()
            raise AppError(
                ErrorCode.OTP_INVALID,
                fields={"remaining_attempts": self._settings.otp_max_attempts - otp.attempts},
            )
        otp.consumed_at = now

    async def _absorb_guest(self, guest: User, account: User) -> None:
        session = self._uow.session
        await DocumentRepository(session).reassign(guest.id, account.id)
        await ConversationRepository(session).reassign(guest.id, account.id)
        await WritingRepository(session).reassign(guest.id, account.id)
        await self._sessions.revoke_all_for(guest.id)
        await self._users.flush()
        await self._users.delete(guest)
        self._uow.defer(Job.PROMOTE_GUEST_FILES, user_id=str(account.id))

    async def _open_session(self, user: User, device: DeviceInfo) -> TokenPair:
        refresh_token = generate_refresh_token()
        session = self._sessions.add(
            AuthSession(
                id=uuid.uuid4(),
                user_id=user.id,
                refresh_token_hash=self._tokens.hash_secret(refresh_token),
                platform=device.platform,
                device_name=device.device_name,
                push_token=device.push_token,
                expires_at=utcnow() + self._tokens.refresh_ttl,
            )
        )
        await self._sessions.flush()
        return self._token_pair(user, session.id, refresh_token)

    def _token_pair(self, user: User, session_id: uuid.UUID, refresh_token: str) -> TokenPair:
        access_token = self._tokens.issue_access_token(
            AccessTokenClaims(user_id=user.id, session_id=session_id, is_guest=user.is_guest)
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(self._tokens.access_ttl.total_seconds()),
        )
