import uuid
from datetime import datetime

from app.core.languages import Language, TextLanguage
from app.models.enums import (
    ContentType,
    ConversationKind,
    MessageRole,
    MessageStatus,
)
from app.schemas.common import Schema


class ConversationOut(Schema):
    id: uuid.UUID
    kind: ConversationKind
    document_id: uuid.UUID | None
    language: Language
    last_message_at: datetime
    created_at: datetime


class MessageOut(Schema):
    id: uuid.UUID
    role: MessageRole
    content_type: ContentType
    language: TextLanguage
    status: MessageStatus
    text: str | None
    text_fr: str | None
    audio_url: str | None
    audio_duration_s: int | None
    source_quote: str | None
    suggested_question_id: uuid.UUID | None
    created_at: datetime


class ExchangeOut(Schema):
    question: MessageOut
    answer: MessageOut
