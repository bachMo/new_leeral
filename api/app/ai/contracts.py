from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any, Literal

from app.core.languages import Language

LineStatusValue = Literal["sure", "to_check", "unreadable"]
CategoryValue = Literal["health", "money", "school", "admin", "other"]
UrgencyValue = Literal["urgent", "soon", "none"]
KeyPointKindValue = Literal["action", "date", "amount", "info"]
WordCategoryValue = Literal["health", "money", "school", "admin", "common"]

PRESCRIPTION = "prescription"


class QualityIssue(StrEnum):
    TOO_BLURRY = "IMAGE_TOO_BLURRY"
    TOO_DARK = "IMAGE_TOO_DARK"
    UNREADABLE = "IMAGE_UNREADABLE"


@dataclass(frozen=True, slots=True)
class ImageQuality:
    issue: QualityIssue | None
    blur_score: float = 0.0
    brightness: float = 0.0
    width: int = 0
    height: int = 0

    @property
    def ok(self) -> bool:
        return self.issue is None


@dataclass(frozen=True, slots=True)
class PageInput:
    position: int
    mime_type: str
    image: bytes | None = None
    text: str | None = None
    filename: str = "page.jpg"


@dataclass(frozen=True, slots=True)
class MedicationLine:
    position: int
    page_position: int
    status: LineStatusValue
    name_read: str | None
    lexicon_name: str | None
    lexicon_suggestion: str | None
    strength: str | None
    times_per_day: int | None
    duration_days: int | None
    timing: str | None
    field_statuses: dict[str, LineStatusValue] = field(default_factory=dict)
    pharmacology_flags: tuple[str, ...] = ()

    @property
    def display_name(self) -> str | None:
        return self.lexicon_name or self.name_read


@dataclass(frozen=True, slots=True)
class KeyPointDraft:
    kind: KeyPointKindValue
    tag: str
    title_fr: str
    detail_fr: str | None = None
    due_date: date | None = None
    amount_xof: int | None = None


@dataclass(frozen=True, slots=True)
class DocumentAnalysis:
    readable: bool
    doc_type: str
    title: str
    category: CategoryValue
    summary_fr: str
    full_text: str
    page_texts: tuple[str, ...] = ()
    issuer: str | None = None
    document_date: date | None = None
    urgency: UrgencyValue = "none"
    urgency_label: str | None = None
    main_due_date: date | None = None
    main_amount_xof: int | None = None
    key_points: tuple[KeyPointDraft, ...] = ()
    suggested_questions_fr: tuple[str, ...] = ()
    medications: tuple[MedicationLine, ...] = ()
    protected_terms: tuple[str, ...] = ()
    extracted_data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_prescription(self) -> bool:
        return self.doc_type == PRESCRIPTION


@dataclass(frozen=True, slots=True)
class DocumentContext:
    doc_type: str | None
    title: str | None
    summary_fr: str
    full_text: str
    medications: tuple[MedicationLine, ...] = ()

    @property
    def is_prescription(self) -> bool:
        return self.doc_type == PRESCRIPTION

    @property
    def protected_terms(self) -> tuple[str, ...]:
        return tuple(name for line in self.medications if (name := line.display_name))


@dataclass(frozen=True, slots=True)
class LocalizedText:
    language: Language
    text: str
    text_fr: str
    complete: bool = True


@dataclass(frozen=True, slots=True)
class SpeechAudio:
    content: bytes
    duration_s: int
    mime_type: str = "audio/mpeg"
    extension: str = "mp3"


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    language: Language | None


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    role: Literal["user", "assistant"]
    text_fr: str


@dataclass(frozen=True, slots=True)
class QuestionContext:
    question_fr: str
    document: DocumentContext | None
    history: tuple[ConversationTurn, ...] = ()


@dataclass(frozen=True, slots=True)
class Answer:
    text_fr: str
    source_quote: str | None = None
    grounded: bool = True


@dataclass(frozen=True, slots=True)
class WritingField:
    key: str
    question_fr: str
    hint_fr: str | None = None


@dataclass(frozen=True, slots=True)
class WritingSection:
    heading: str | None
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ComposedDocument:
    kind: Literal["cv", "cover_letter", "letter"]
    title: str
    sections: tuple[WritingSection, ...]

    def as_text(self) -> str:
        blocks = [self.title]
        for section in self.sections:
            lines = "\n".join(section.lines)
            blocks.append(f"{section.heading}\n{lines}" if section.heading else lines)
        return "\n\n".join(blocks)


@dataclass(frozen=True, slots=True)
class ComposedWriting:
    documents: tuple[ComposedDocument, ...]
    readback_fr: str


@dataclass(frozen=True, slots=True)
class VocabularyCandidate:
    word_fr: str
    category: WordCategoryValue
    sentence_fr: str
