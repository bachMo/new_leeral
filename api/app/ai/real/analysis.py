import logging
import re
from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.ai.contracts import DocumentAnalysis, KeyPointDraft, UrgencyValue
from app.ai.errors import AiOutputError
from app.ai.real import prompts
from app.ai.real.reasoning import Reasoner
from app.ai.real.safety.brand_names import known_brand_terms
from app.ai.real.safety.dates import FRENCH_MONTHS
from app.ai.real.translation import split_sentences

logger = logging.getLogger("leeral.ai.analysis")

MAX_DOCUMENT_CHARS = 60_000
_DIGITS = re.compile(r"\d")
_GROUPED_NUMBER = re.compile(r"\d{1,3}(?:[ .\u202f\u00a0]\d{3})+(?!\d)|\d+")
_SEPARATORS = re.compile(r"[ .\u202f\u00a0]")
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


class _ContractAmount(BaseModel):
    label: str = "Montant"
    amount_xof: int | None = None

    @field_validator("amount_xof", mode="before")
    @classmethod
    def _parse_amount(cls, value: Any) -> int | None:
        return _optional_amount(value)


class _ContractTerms(BaseModel):
    duration: str | None = None
    auto_renewal: str | None = None
    termination: str | None = None
    penalties: list[str] = Field(default_factory=list)
    parties: list[str] = Field(default_factory=list)
    amounts: list[_ContractAmount] = Field(default_factory=list)
    vigilance_points: list[str] = Field(default_factory=list)


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
    proper_nouns: list[str] = Field(default_factory=list)
    contract: _ContractTerms | None = None

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
    spelled = f"{value.day} {FRENCH_MONTHS[value.month - 1]}"
    numeric = (f"{day}/{month}", f"{day}-{month}", f"{day}.{month}", value.isoformat())
    if any(form in text for form in numeric) or spelled in lowered:
        return value
    return None


def _protected_terms(proper_nouns: list[str], text: str) -> tuple[str, ...]:
    """Brand/institution names to keep untranslated: the known catalog plus names the model saw,
    kept only when they appear verbatim in the source (never trust an invented name)."""
    grounded = (noun.strip() for noun in proper_nouns if noun.strip())
    dynamic = (noun for noun in grounded if noun.lower() in text.lower())
    return tuple(dict.fromkeys((*known_brand_terms(text), *dynamic)))


def _is_grounded(fragment: str, text: str) -> bool:
    available = _numbers_in(text)
    return all(number in available for number in _numbers_in(fragment))


def _grounded_summary(summary: str, text: str) -> str:
    sentences = split_sentences(summary) or [summary]
    kept = [sentence for sentence in sentences if _is_grounded(sentence, text)]
    if len(kept) < len(sentences):
        logger.warning("analysis_summary_ungrounded", extra={"dropped": len(sentences) - len(kept)})
    return " ".join(kept) if kept else summary


def _urgency_from_due_date(due: date | None, today: date, declared: UrgencyValue) -> UrgencyValue:
    if due is None:
        return declared
    if due - today <= timedelta(days=7):
        return "urgent"
    if due - today <= timedelta(days=30):
        return "soon" if declared == "none" else declared
    return declared


CUT_OFF_WARNING = "Attention, une partie de ce document n'était pas dans la photo."
CONTRACT_DISCLAIMER = (
    "Ceci n'est pas un avis juridique. Pour toute décision, demande à un professionnel du droit."
)


def _contract_key_points(contract: _ContractTerms, text: str) -> list[KeyPointDraft]:
    points: list[KeyPointDraft] = [
        KeyPointDraft(kind="info", tag="Avis", title_fr=CONTRACT_DISCLAIMER)
    ]
    if contract.duration and _is_grounded(contract.duration, text):
        points.append(KeyPointDraft(kind="info", tag="Durée", title_fr=contract.duration.strip()))
    if contract.auto_renewal and _is_grounded(contract.auto_renewal, text):
        points.append(
            KeyPointDraft(kind="info", tag="Reconduction", title_fr=contract.auto_renewal.strip())
        )
    if contract.termination and _is_grounded(contract.termination, text):
        points.append(
            KeyPointDraft(kind="info", tag="Résiliation", title_fr=contract.termination.strip())
        )
    for penalty in contract.penalties[:5]:
        if penalty.strip() and _is_grounded(penalty, text):
            points.append(KeyPointDraft(kind="info", tag="Pénalité", title_fr=penalty.strip()))
    for party in contract.parties[:5]:
        if party.strip() and _is_grounded(party, text):
            points.append(KeyPointDraft(kind="info", tag="Partie", title_fr=party.strip()))
    for amount in contract.amounts[:5]:
        grounded = _amount_in_text(amount.amount_xof, text)
        if grounded is not None:
            points.append(
                KeyPointDraft(
                    kind="amount",
                    tag="Montant",
                    title_fr=amount.label[:40] or "Montant",
                    amount_xof=grounded,
                )
            )
    for vigilance in contract.vigilance_points[:5]:
        if vigilance.strip() and _is_grounded(vigilance, text):
            points.append(KeyPointDraft(kind="info", tag="Vigilance", title_fr=vigilance.strip()))
    return points


async def analyze_text(
    reasoner: Reasoner,
    text: str,
    *,
    page_texts: tuple[str, ...],
    today: date,
    cut_off: bool = False,
    uncertain: bool = False,
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
    dropped_points = 0
    key_points_list: list[KeyPointDraft] = []
    for point in parsed.key_points[:5]:
        if not point.title_fr.strip():
            continue
        if not _is_grounded(f"{point.title_fr} {point.detail_fr or ''}", clipped):
            dropped_points += 1
            continue
        key_points_list.append(
            KeyPointDraft(
                kind=point.kind,
                tag=point.tag[:40],
                title_fr=point.title_fr,
                detail_fr=point.detail_fr,
                due_date=_date_in_text(point.due_date, clipped),
                amount_xof=_amount_in_text(point.amount_xof, clipped),
            )
        )
    if dropped_points:
        logger.warning("analysis_key_point_ungrounded", extra={"dropped": dropped_points})
    contract_points = _contract_key_points(parsed.contract, clipped) if parsed.contract else []
    prefix_points: list[KeyPointDraft] = []
    if cut_off:
        prefix_points.append(
            KeyPointDraft(
                kind="info",
                tag="Incomplet",
                title_fr="Une partie du document manque",
                detail_fr="Le haut ou le bas de la page n'était pas dans la photo.",
            )
        )
    if uncertain:
        prefix_points.append(
            KeyPointDraft(
                kind="info",
                tag="Incertain",
                title_fr="Leeral n'est pas sûr du type de document",
            )
        )
    key_points = (*prefix_points, *contract_points, *key_points_list)
    summary_fr = _grounded_summary(parsed.summary_fr.strip(), clipped)
    if cut_off:
        summary_fr = f"{CUT_OFF_WARNING} {summary_fr}"
    suggested_questions = tuple(q.strip() for q in parsed.suggested_questions[:3] if q.strip())
    if uncertain:
        suggested_questions = ("Quel est ce document ?", *suggested_questions)
    return DocumentAnalysis(
        readable=True,
        doc_type=parsed.doc_type,
        title=parsed.title.strip()[:120] or "Document",
        category=parsed.category,
        summary_fr=summary_fr,
        full_text=text,
        cut_off=cut_off,
        page_texts=page_texts,
        issuer=parsed.issuer,
        document_date=_date_in_text(parsed.document_date, clipped),
        urgency=_urgency_from_due_date(due, today, parsed.urgency),
        urgency_label=parsed.urgency_label,
        main_due_date=due,
        main_amount_xof=_amount_in_text(parsed.main_amount_xof, clipped),
        key_points=key_points,
        suggested_questions_fr=suggested_questions,
        protected_terms=_protected_terms(parsed.proper_nouns, clipped),
    )
