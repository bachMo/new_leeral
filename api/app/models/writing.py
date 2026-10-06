import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.languages import Language
from app.db.base import Entity, TextEnum
from app.models.enums import WritingOutputKind, WritingStatus, WritingType


class Writing(Entity):
    __tablename__ = "writings"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), unique=True
    )
    type: Mapped[WritingType] = mapped_column(TextEnum(WritingType))
    status: Mapped[WritingStatus] = mapped_column(TextEnum(WritingStatus))
    current_step: Mapped[int] = mapped_column(default=0)
    total_steps: Mapped[int]
    collected_data: Mapped[dict[str, Any]] = mapped_column(default=dict)

    steps: Mapped[list["WritingStep"]] = relationship(
        order_by="WritingStep.position", lazy="raise", passive_deletes=True
    )
    outputs: Mapped[list["WritingOutput"]] = relationship(
        order_by="WritingOutput.version", lazy="raise", passive_deletes=True
    )


class WritingStep(Entity):
    __tablename__ = "writing_steps"
    __table_args__ = (UniqueConstraint("writing_id", "position"),)

    writing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("writings.id", ondelete="CASCADE"))
    position: Mapped[int]
    field_key: Mapped[str]
    question_message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE")
    )
    answer_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    understood_value: Mapped[str | None]
    confirmed_at: Mapped[datetime | None]


class WritingOutput(Entity):
    __tablename__ = "writing_outputs"
    __table_args__ = (UniqueConstraint("writing_id", "version", "kind"),)

    writing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("writings.id", ondelete="CASCADE"))
    version: Mapped[int]
    kind: Mapped[WritingOutputKind] = mapped_column(TextEnum(WritingOutputKind))
    content: Mapped[str]
    pdf_key: Mapped[str]
    readback_language: Mapped[Language] = mapped_column(TextEnum(Language))
    readback_audio_key: Mapped[str | None]
