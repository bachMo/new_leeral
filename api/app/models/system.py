import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.languages import Language
from app.db.base import Entity, TextEnum
from app.models.enums import AiJobStatus, AiJobType


class AiJob(Entity):
    __tablename__ = "ai_jobs"
    __table_args__ = (Index("ix_ai_jobs_status_created", "status", "created_at"),)

    job_type: Mapped[AiJobType] = mapped_column(TextEnum(AiJobType))
    provider: Mapped[str]
    status: Mapped[AiJobStatus] = mapped_column(TextEnum(AiJobStatus), default=AiJobStatus.QUEUED)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    writing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("writings.id", ondelete="SET NULL")
    )
    input: Mapped[dict[str, Any]]
    output: Mapped[dict[str, Any] | None]
    error: Mapped[str | None]
    duration_ms: Mapped[int | None]
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]


class UiPrompt(Entity):
    __tablename__ = "ui_prompts"
    __table_args__ = (UniqueConstraint("key", "language"),)

    key: Mapped[str]
    language: Mapped[Language] = mapped_column(TextEnum(Language))
    text_fr: Mapped[str]
    audio_key: Mapped[str]
