import re
from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.ai.contracts import DocumentAnalysis, KeyPointDraft, UrgencyValue
from app.ai.errors import AiOutputError
from app.ai.real import prompts
from app.ai.real.reasoning import Reasoner

MAX_DOCUMENT_CHARS = 60_000
_DIGITS = re.compile(r"\d")
_GROUPED_NUMBER = re.compile(r"\d{1,3}(?:[ .\u202f\u00a0]\d{3})+(?!\d)|\d+")
_SEPARATORS = re.compile(r"[ .\u202f\u00a0]")
_FRENCH_MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)
_DOC_TYPES = {
    "invoice",
    "letter",
    "contract",
    "lab_result",
    "school",
    "bank",
    "administrative",
    "other",
}


def _optional_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def _optional_amount(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value) if value > 0 else None
    if isinstance(value, str):
        digits = "".join(_DIGITS.findall(value))
        return int(digits) if digits else None
    return None


class _KeyPoint(BaseModel):
    kind: Literal["action", "date", "amount", "info"] = "info"
    tag: str = "Info"
    title_fr: str
    detail_fr: str | None = None
    due_date: date | None = None
    amount_xof: int | None = None

    @field_validator("due_date", mode="before")
    @classmethod
    def _parse_date(cls, value: Any) -> date | None:
        return _optional_date(value)

    @field_validator("amount_xof", mode="before")
    @classmethod
    def _parse_amount(cls, value: Any) -> int | None:
        return _optional_amount(value)


class _Analysis(BaseModel):
    title: str = "Document"
    doc_type: str = "other"
    category: Literal["health", "money", "school", "admin", "other"] = "other"
    issuer: str | None = None
    document_date: date | None = None
    urgency: UrgencyValue = "none"
    urgency_label: str | None = None
    main_due_date: date | None = None
    main_amount_xof: int | None = None
    summary_fr: str
    key_points: list[_KeyPoint] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)

    @field_validator("document_date", "main_due_date", mode="before")
    @classmethod
    def _parse_date(cls, value: Any) -> date | None:
        return _optional_date(value)

    @field_validator("main_amount_xof", mode="before")
    @classmethod
    def _parse_amount(cls, value: Any) -> int | None:
        return _optional_amount(value)

    @field_validator("doc_type", mode="before")
    @classmethod
    def _known_type(cls, value: Any) -> str:
        return value if value in _DOC_TYPES else "other"


def _numbers_in(text: str) -> set[int]:
    return {int(_SEPARATORS.sub("", match)) for match in _GROUPED_NUMBER.findall(text)}


def _amount_in_text(amount: int | None, text: str) -> int | None:
    if amount is None:
        return None
    return amount if amount in _numbers_in(text) else None


def _date_in_text(value: date | None, text: str) -> date | None:
    if value is None:
        return None
    day, month = f"{value.day:02d}", f"{value.month:02d}"
    lowered = text.lower()
    spelled = f"{value.day} {_FRENCH_MONTHS[value.month - 1]}"
    numeric = (f"{day}/{month}", f"{day}-{month}", f"{day}.{month}", value.isoformat())
    if any(form in text for form in numeric) or spelled in lowered:
        return value
    return None


def _urgency_from_due_date(due: date | None, today: date, declared: UrgencyValue) -> UrgencyValue:
    if due is None:
        return declared
    if due - today <= timedelta(days=7):
        return "urgent"
    if due - today <= timedelta(days=30):
        return "soon" if declared == "none" else declared
    return declared


async def analyze_text(
    reasoner: Reasoner, text: str, *, page_texts: tuple[str, ...], today: date
) -> DocumentAnalysis:
    clipped = text[:MAX_DOCUMENT_CHARS]
    raw = await reasoner.complete_json(
        prompts.ANALYZE_DOCUMENT.format(text=clipped, today=today.isoformat()),
        operation="analyze_document",
        max_tokens=2500,
    )
    try:
        parsed = _Analysis.model_validate(raw)
    except ValidationError as exc:
        raise AiOutputError(f"analysis output invalid: {exc.error_count()} errors") from exc

    due = _date_in_text(parsed.main_due_date, clipped)
    key_points = tuple(
        KeyPointDraft(
            kind=point.kind,
            tag=point.tag[:40],
            title_fr=point.title_fr,
            detail_fr=point.detail_fr,
            due_date=_date_in_text(point.due_date, clipped),
            amount_xof=_amount_in_text(point.amount_xof, clipped),
        )
        for point in parsed.key_points[:5]
        if point.title_fr.strip()
    )
    return DocumentAnalysis(
        readable=True,
        doc_type=parsed.doc_type,
        title=parsed.title.strip()[:120] or "Document",
        category=parsed.category,
        summary_fr=parsed.summary_fr.strip(),
        full_text=text,
        page_texts=page_texts,
        issuer=parsed.issuer,
        document_date=_date_in_text(parsed.document_date, clipped),
        urgency=_urgency_from_due_date(due, today, parsed.urgency),
        urgency_label=parsed.urgency_label,
        main_due_date=due,
        main_amount_xof=_amount_in_text(parsed.main_amount_xof, clipped),
        key_points=key_points,
        suggested_questions_fr=tuple(
            q.strip() for q in parsed.suggested_questions[:3] if q.strip()
        ),
    )
