import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.languages import Language
from app.db.base import Entity, TextEnum
from app.models.enums import (
    Channel,
    DocumentCategory,
    DocumentStatus,
    ExplanationVariant,
    KeyPointKind,
    LineStatus,
    Urgency,
)


class Document(Entity):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_user_created", "user_id", "created_at"),
        Index("ix_documents_user_category", "user_id", "category"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    source: Mapped[Channel] = mapped_column(TextEnum(Channel))
    status: Mapped[DocumentStatus] = mapped_column(
        TextEnum(DocumentStatus), default=DocumentStatus.PENDING
    )
    failure_reason: Mapped[str | None]
    title: Mapped[str | None]
    doc_type: Mapped[str | None]
    category: Mapped[DocumentCategory] = mapped_column(
        TextEnum(DocumentCategory), default=DocumentCategory.OTHER
    )
    issuer: Mapped[str | None]
    document_date: Mapped[date | None]
    urgency: Mapped[Urgency] = mapped_column(TextEnum(Urgency), default=Urgency.NONE)
    urgency_label: Mapped[str | None]
    main_due_date: Mapped[date | None]
    main_amount_xof: Mapped[int | None]
    page_count: Mapped[int] = mapped_column(default=0)
    ocr_text: Mapped[str | None]
    summary_fr: Mapped[str | None]
    extracted_data: Mapped[dict[str, Any] | None]
    processed_at: Mapped[datetime | None]

    files: Mapped[list["DocumentFile"]] = relationship(
        order_by="DocumentFile.position", lazy="raise", passive_deletes=True
    )
    explanations: Mapped[list["DocumentExplanation"]] = relationship(
        lazy="raise", passive_deletes=True
    )
    key_points: Mapped[list["DocumentKeyPoint"]] = relationship(
        order_by="DocumentKeyPoint.position", lazy="raise", passive_deletes=True
    )
    suggested_questions: Mapped[list["DocumentSuggestedQuestion"]] = relationship(
        order_by="DocumentSuggestedQuestion.position", lazy="raise", passive_deletes=True
    )
    prescription_lines: Mapped[list["PrescriptionLine"]] = relationship(
        order_by="PrescriptionLine.position", lazy="raise", passive_deletes=True
    )

    @property
    def is_prescription(self) -> bool:
        return self.doc_type == "prescription"


class DocumentFile(Entity):
    __tablename__ = "document_files"

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    position: Mapped[int]
    file_key: Mapped[str]
    mime_type: Mapped[str]
    original_filename: Mapped[str | None]
    size_bytes: Mapped[int]
    ocr_text: Mapped[str | None]


class DocumentExplanation(Entity):
    __tablename__ = "document_explanations"
    __table_args__ = (UniqueConstraint("document_id", "language", "variant"),)

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    language: Mapped[Language] = mapped_column(TextEnum(Language))
    variant: Mapped[ExplanationVariant] = mapped_column(TextEnum(ExplanationVariant))
    text: Mapped[str]
    text_fr: Mapped[str]
    audio_key: Mapped[str]
    audio_duration_s: Mapped[int]


class DocumentKeyPoint(Entity):
    __tablename__ = "document_key_points"
    __table_args__ = (UniqueConstraint("document_id", "language", "position"),)

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    language: Mapped[Language] = mapped_column(TextEnum(Language))
    position: Mapped[int]
    kind: Mapped[KeyPointKind] = mapped_column(TextEnum(KeyPointKind))
    tag: Mapped[str]
    title_fr: Mapped[str]
    detail_fr: Mapped[str | None]
    due_date: Mapped[date | None]
    amount_xof: Mapped[int | None]
    audio_key: Mapped[str]


class DocumentSuggestedQuestion(Entity):
    __tablename__ = "document_suggested_questions"
    __table_args__ = (UniqueConstraint("document_id", "language", "position"),)

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    language: Mapped[Language] = mapped_column(TextEnum(Language))
    position: Mapped[int]
    text_fr: Mapped[str]
    audio_key: Mapped[str]


class PrescriptionLine(Entity):
    __tablename__ = "prescription_lines"
    __table_args__ = (UniqueConstraint("document_id", "position"),)

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    position: Mapped[int]
    page_position: Mapped[int]
    status: Mapped[LineStatus] = mapped_column(TextEnum(LineStatus))
    name_read: Mapped[str | None]
    lexicon_name: Mapped[str | None]
    lexicon_suggestion: Mapped[str | None]
    strength: Mapped[str | None]
    times_per_day: Mapped[int | None]
    duration_days: Mapped[int | None]
    timing: Mapped[str | None]
    field_statuses: Mapped[dict[str, Any]]
    pharmacology_flags: Mapped[list[Any]]
