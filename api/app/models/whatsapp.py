import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.languages import Language
from app.db.base import Entity, TextEnum
from app.models.enums import (
    WhatsAppDirection,
    WhatsAppMessageStatus,
    WhatsAppMessageType,
    WhatsAppSessionState,
)


class WhatsAppChannel(Entity):
    __tablename__ = "whatsapp_channels"

    phone_number_id: Mapped[str] = mapped_column(unique=True)
    display_number: Mapped[str]
    language: Mapped[Language | None] = mapped_column(TextEnum(Language))
    is_active: Mapped[bool] = mapped_column(default=True)


class WhatsAppMessage(Entity):
    __tablename__ = "whatsapp_messages"
    __table_args__ = (
        Index("ix_whatsapp_messages_user_created", "user_id", "created_at"),
        Index("ix_whatsapp_messages_phone_created", "wa_phone", "created_at"),
        Index("ix_whatsapp_messages_thread_updated", "channel_id", "wa_phone", "updated_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    wa_phone: Mapped[str]
    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("whatsapp_channels.id", ondelete="RESTRICT")
    )
    direction: Mapped[WhatsAppDirection] = mapped_column(TextEnum(WhatsAppDirection))
    wa_message_id: Mapped[str] = mapped_column(unique=True)
    type: Mapped[WhatsAppMessageType] = mapped_column(TextEnum(WhatsAppMessageType))
    template_name: Mapped[str | None]
    body_text: Mapped[str | None]
    wa_media_id: Mapped[str | None]
    media_key: Mapped[str | None]
    status: Mapped[WhatsAppMessageStatus] = mapped_column(TextEnum(WhatsAppMessageStatus))
    error: Mapped[str | None]
    media_mime: Mapped[str | None]
    meta: Mapped[dict[str, Any] | None]
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admin_users.id", ondelete="SET NULL")
    )


class WhatsAppThread(Entity):
    __tablename__ = "whatsapp_threads"
    __table_args__ = (UniqueConstraint("channel_id", "wa_phone"),)

    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("whatsapp_channels.id", ondelete="RESTRICT")
    )
    wa_phone: Mapped[str]
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    bot_paused: Mapped[bool] = mapped_column(default=False)
    bot_paused_until: Mapped[datetime | None]
    last_read_at: Mapped[datetime | None]


class WhatsAppSession(Entity):
    __tablename__ = "whatsapp_sessions"
    __table_args__ = (UniqueConstraint("user_id", "channel_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("whatsapp_channels.id", ondelete="RESTRICT")
    )
    state: Mapped[WhatsAppSessionState] = mapped_column(TextEnum(WhatsAppSessionState))
    active_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    pending_question_fr: Mapped[str | None] = mapped_column(default=None)
    last_inbound_at: Mapped[datetime] = mapped_column(server_default=func.now())
