import uuid
from datetime import date, datetime
from typing import Literal

from app.core.languages import Language
from app.models.enums import (
    Channel,
    DocumentCategory,
    DocumentStatus,
    ExplanationVariant,
    KeyPointKind,
    LineStatus,
    Urgency,
)
from app.schemas.common import Schema


class PageOut(Schema):
    position: int
    mime_type: str
    url: str


class ExplanationOut(Schema):
    id: uuid.UUID
    language: Language
    variant: ExplanationVariant
    text: str
    text_fr: str
    audio_url: str
    audio_duration_s: int


class KeyPointOut(Schema):
    position: int
    kind: KeyPointKind
    tag: str
    title_fr: str
    detail_fr: str | None
    due_date: date | None
    amount_xof: int | None
    audio_url: str


class SuggestedQuestionOut(Schema):
    id: uuid.UUID
    position: int
    text_fr: str
    audio_url: str


class PrescriptionLineOut(Schema):
    position: int
    status: LineStatus
    name: str | None
    name_read: str | None
    suggestion: str | None
    dci: str | None
    strength: str | None
    form: str | None
    times_per_day: int | None
    duration_days: int | None
    timing: str | None
    instructions: str | None
    raw: str | None
    image_url: str | None


class DocumentSummaryOut(Schema):
    id: uuid.UUID
    source: Channel
    status: DocumentStatus
    failure_reason: str | None
    title: str | None
    doc_type: str | None
    category: DocumentCategory
    urgency: Urgency
    urgency_label: str | None
    main_due_date: date | None
    main_amount_xof: int | None
    page_count: int
    created_at: datetime


class DocumentOut(DocumentSummaryOut):
    issuer: str | None
    document_date: date | None
    pages: list[PageOut]
    explanation: ExplanationOut | None
    simple_explanation: ExplanationOut | None
    key_points: list[KeyPointOut]
    suggested_questions: list[SuggestedQuestionOut]
    prescription_lines: list[PrescriptionLineOut]


class DocumentPageOut(Schema):
    items: list[DocumentSummaryOut]
    next_before: datetime | None


class ExplanationRequestIn(Schema):
    variant: ExplanationVariant = ExplanationVariant.SIMPLE
    language: Language | None = None


class ExplanationRequestOut(Schema):
    status: Literal["ready", "pending"]
    explanation: ExplanationOut | None = None


class LibraryItemOut(Schema):
    kind: Literal["document", "writing"]
    id: uuid.UUID
    title: str
    category: str
    status: str
    created_at: datetime
