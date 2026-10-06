import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.languages import Language
from app.db.base import Entity, TextEnum
from app.models.enums import Platform


class User(Entity):
    __tablename__ = "users"

    phone_number: Mapped[str | None] = mapped_column(unique=True)
    first_name: Mapped[str | None]
    whatsapp_name: Mapped[str | None]
    language: Mapped[Language] = mapped_column(TextEnum(Language))
    is_guest: Mapped[bool] = mapped_column(default=False)
    guest_device_id: Mapped[str | None] = mapped_column(unique=True)
    registered_at: Mapped[datetime | None]
    terms_accepted_at: Mapped[datetime | None]
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())

    @property
    def has_completed_profile(self) -> bool:
        return bool(self.first_name) and self.terms_accepted_at is not None


class OtpCode(Entity):
    __tablename__ = "otp_codes"
    __table_args__ = (Index("ix_otp_codes_phone_created", "phone_number", "created_at"),)

    phone_number: Mapped[str]
    code_hash: Mapped[str]
    attempts: Mapped[int] = mapped_column(default=0)
    expires_at: Mapped[datetime]
    consumed_at: Mapped[datetime | None]


class AuthSession(Entity):
    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    refresh_token_hash: Mapped[str] = mapped_column(unique=True)
    platform: Mapped[Platform] = mapped_column(TextEnum(Platform))
    device_name: Mapped[str | None]
    push_token: Mapped[str | None]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
