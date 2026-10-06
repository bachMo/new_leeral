import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError, ErrorCode

ACCESS_TOKEN_TYPE = "access"


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID
    is_guest: bool


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret.get_secret_value()
        self._algorithm = settings.jwt_algorithm
        self._access_ttl = timedelta(minutes=settings.access_token_ttl_minutes)
        self._refresh_ttl = timedelta(days=settings.refresh_token_ttl_days)
        if len(self._secret) < 32:
            raise RuntimeError("JWT_SECRET must be at least 32 characters long")

    @property
    def access_ttl(self) -> timedelta:
        return self._access_ttl

    @property
    def refresh_ttl(self) -> timedelta:
        return self._refresh_ttl

    def issue_access_token(self, claims: AccessTokenClaims, now: datetime | None = None) -> str:
        issued_at = now or utcnow()
        payload = {
            "sub": str(claims.user_id),
            "sid": str(claims.session_id),
            "gst": claims.is_guest,
            "typ": ACCESS_TOKEN_TYPE,
            "iat": issued_at,
            "exp": issued_at + self._access_ttl,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as exc:
            raise AppError(ErrorCode.TOKEN_EXPIRED) from exc
        except jwt.PyJWTError as exc:
            raise AppError(ErrorCode.UNAUTHENTICATED) from exc
        if payload.get("typ") != ACCESS_TOKEN_TYPE:
            raise AppError(ErrorCode.UNAUTHENTICATED)
        try:
            return AccessTokenClaims(
                user_id=uuid.UUID(payload["sub"]),
                session_id=uuid.UUID(payload["sid"]),
                is_guest=bool(payload.get("gst", False)),
            )
        except (KeyError, ValueError) as exc:
            raise AppError(ErrorCode.UNAUTHENTICATED) from exc

    def hash_secret(self, value: str) -> str:
        return hmac.new(self._secret.encode(), value.encode(), hashlib.sha256).hexdigest()

    def verify_secret(self, value: str, expected_hash: str) -> bool:
        return hmac.compare_digest(self.hash_secret(value), expected_hash)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def generate_numeric_code(length: int) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def generate_public_token() -> str:
    return secrets.token_urlsafe(24)
