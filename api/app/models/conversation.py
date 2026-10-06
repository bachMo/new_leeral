import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.languages import Language, TextLanguage
from app.db.base import Entity, TextEnum
from app.models.enums import Channel, ContentType, ConversationKind, MessageRole, MessageStatus


class Conversation(Entity):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_user_last_message", "user_id", "last_message_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE")
    )
    source: Mapped[Channel] = mapped_column(TextEnum(Channel))
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("whatsapp_channels.id", ondelete="RESTRICT")
    )
    language: Mapped[Language] = mapped_column(TextEnum(Language))
    kind: Mapped[ConversationKind] = mapped_column(TextEnum(ConversationKind))
    context_summary: Mapped[str | None]
    last_message_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ConversationDocument(Entity):
    __tablename__ = "conversation_documents"
    __table_args__ = (UniqueConstraint("conversation_id", "document_id"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))


class Message(Entity):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[MessageRole] = mapped_column(TextEnum(MessageRole))
    content_type: Mapped[ContentType] = mapped_column(TextEnum(ContentType))
    language: Mapped[TextLanguage] = mapped_column(TextEnum(TextLanguage))
    status: Mapped[MessageStatus] = mapped_column(TextEnum(MessageStatus))
    text: Mapped[str | None]
    text_fr: Mapped[str | None]
    audio_key: Mapped[str | None]
    audio_duration_s: Mapped[int | None]
    media_key: Mapped[str | None]
    source_quote: Mapped[str | None]
    explanation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_explanations.id", ondelete="SET NULL")
    )
    suggested_question_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_suggested_questions.id", ondelete="SET NULL")
    )
    whatsapp_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("whatsapp_messages.id", ondelete="SET NULL")
    )
