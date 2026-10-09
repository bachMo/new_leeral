import asyncio
import difflib
import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import replace
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.ai.contracts import LineStatusValue, MedicationLine, PageInput
from app.ai.errors import AiError, AiOutputError
from app.ai.real import prompts
from app.ai.real.clients.openrouter import ModelProfile, OpenRouterClient
from app.ai.real.pages import PageReader, crop_band
from app.ai.real.safety.lexicon import Lexicon
from app.ai.real.safety.pharmacology import PharmacologyRules
from app.ai.real.safety.text import fold

logger = logging.getLogger("leeral.ai.prescription")

NAME_MATCH_THRESHOLD = 0.6
_STATUS_RANK: dict[LineStatusValue, int] = {"unreadable": 0, "to_check": 1, "sure": 2}


class MedicationReading(BaseModel):
    raw: str | None = None
    name_read: str | None = None
    dci_read: str | None = None
    strength: str | None = None
    form: str | None = None
    times_per_day: int | None = None
    duration_days: int | None = None
    timing: str | None = None
    instructions: str | None = None
    line_position: float | None = None
    legible: Literal["yes", "partial", "no"] = "no"

    @field_validator(
        "name_read",
        "dci_read",
        "strength",
        "form",
        "timing",
        "instructions",
        "raw",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("times_per_day", "duration_days", mode="before")
    @classmethod
    def _strict_integer(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return int(stripped) if stripped.isdigit() else None
        if isinstance(value, float):
            return int(value) if value.is_integer() else None
        return value


class PrescriptionReading(BaseModel):
    document_language: str = "unknown"
    page_cut_off: bool = False
    medications: list[MedicationReading] = Field(default_factory=list)


class _Field(BaseModel):
    value: str | int | None
    status: LineStatusValue


def _same_value(first: str | int | None, second: str | int | None) -> bool:
    if isinstance(first, str) and isinstance(second, str):
        return fold(first).replace(" ", "") == fold(second).replace(" ", "")
    return first is not None and first == second


def _similarity(first: str | None, second: str | None) -> float:
    return difflib.SequenceMatcher(None, fold(first or ""), fold(second or "")).ratio()


def page_cut_off(first: PrescriptionReading, second: PrescriptionReading) -> bool:
    return first.page_cut_off and second.page_cut_off


def align(
    first: Sequence[MedicationReading],
    second: Sequence[MedicationReading],
    *,
    name_match_threshold: float = NAME_MATCH_THRESHOLD,
) -> list[tuple[MedicationReading | None, MedicationReading | None]]:
    used: set[int] = set()
    pairs: list[tuple[MedicationReading | None, MedicationReading | None]] = []
    for line in first:
        best_index: int | None = None
        best_ratio = name_match_threshold
        for index, other in enumerate(second):
            if index in used:
                continue
            ratio = _similarity(line.name_read, other.name_read)
            if ratio >= best_ratio:
                best_index, best_ratio = index, ratio
        if best_index is None:
            pairs.append((line, None))
        else:
            used.add(best_index)
            pairs.append((line, second[best_index]))
    pairs.extend((None, other) for index, other in enumerate(second) if index not in used)
    return pairs


def _verify_field(
    first: str | int | None, second: str | int | None, *, both_legible: bool
) -> _Field:
    if first is None and second is None:
        return _Field(value=None, status="unreadable")
    agreed = _same_value(first, second)
    return _Field(
        value=first if first is not None else second,
        status="sure" if agreed and both_legible else "to_check",
    )


def verify_line(
    first: MedicationReading | None,
    second: MedicationReading | None,
    *,
    position: int,
    page_position: int,
    lexicon: Lexicon,
    pharmacology: PharmacologyRules,
) -> MedicationLine:
    both_legible = (
        first is not None
        and second is not None
        and first.legible == "yes"
        and second.legible == "yes"
    )

    def pick(attribute: str) -> _Field:
        return _verify_field(
            getattr(first, attribute) if first else None,
            getattr(second, attribute) if second else None,
            both_legible=both_legible,
        )

    name, dci, strength, form, times, duration, timing, instructions = (
        pick("name_read"),
        pick("dci_read"),
        pick("strength"),
        pick("form"),
        pick("times_per_day"),
        pick("duration_days"),
        pick("timing"),
        pick("instructions"),
    )
    name_read = name.value if isinstance(name.value, str) else None
    match = lexicon.lookup(name_read) if name_read else None
    if name.status == "sure" and (match is None or not match.trusted):
        name = _Field(value=name.value, status="to_check")

    dci_read = dci.value if isinstance(dci.value, str) else None
    dci_match = lexicon.lookup(dci_read, dci_only=True) if dci_read else None
    if dci.status == "sure" and (dci_match is None or not dci_match.trusted):
        dci = _Field(value=dci.value, status="to_check")

    raw_read = (first.raw if first else None) or (second.raw if second else None)

    coherence = (
        pharmacology.check(
            name_read,
            strength=strength.value if isinstance(strength.value, str) else None,
            times_per_day=times.value if isinstance(times.value, int) else None,
            duration_days=duration.value if isinstance(duration.value, int) else None,
        )
        if name_read
        else None
    )

    fields = {
        "name": name,
        "dci": dci,
        "strength": strength,
        "form": form,
        "times_per_day": times,
        "duration": duration,
        "timing": timing,
        "instructions": instructions,
    }
    if name.status == "unreadable":
        status: LineStatusValue = "unreadable"
    else:
        evaluated = [field.status for field in fields.values() if field.value is not None]
        status = min(evaluated, key=_STATUS_RANK.__getitem__)
        if coherence is not None and coherence.flagged:
            status = "to_check"

    return MedicationLine(
        position=position,
        page_position=page_position,
        status=status,
        name_read=name_read,
        lexicon_name=name_read if match and match.trusted else None,
        lexicon_suggestion=match.suggestion if match else None,
        dci_read=dci_read,
        dci_lexicon=dci_read if dci_match and dci_match.trusted else None,
        raw_read=raw_read,
        strength=strength.value if isinstance(strength.value, str) else None,
        form=form.value if isinstance(form.value, str) else None,
        instructions=instructions.value if isinstance(instructions.value, str) else None,
        times_per_day=times.value if isinstance(times.value, int) else None,
        duration_days=duration.value if isinstance(duration.value, int) else None,
        timing=timing.value if status == "sure" and isinstance(timing.value, str) else None,
        field_statuses={key: field.status for key, field in fields.items()},
        pharmacology_flags=coherence.reasons if coherence else (),
    )


def _line_position_estimate(
    first: MedicationReading | None, second: MedicationReading | None
) -> float | None:
    values = [
        reading.line_position
        for reading in (first, second)
        if reading is not None and reading.line_position is not None
    ]
    return sum(values) / len(values) if values else None


_CROSS_PAGE_FIELDS = ("strength", "times_per_day", "duration_days", "timing")


def _conflicts_across_pages(first: MedicationLine, second: MedicationLine) -> bool:
    for attribute in _CROSS_PAGE_FIELDS:
        a, b = getattr(first, attribute), getattr(second, attribute)
        if a is not None and b is not None and not _same_value(a, b):
            return True
    return False


def _flag_cross_page_mismatches(lines: list[MedicationLine]) -> list[MedicationLine]:
    groups: dict[str, list[int]] = defaultdict(list)
    for index, line in enumerate(lines):
        name = line.display_name
        if name:
            groups[fold(name)].append(index)
    flagged: set[int] = set()
    for indices in groups.values():
        for position, index_a in enumerate(indices):
            for index_b in indices[position + 1 :]:
                first, second = lines[index_a], lines[index_b]
                if first.page_position == second.page_position:
                    continue
                if _conflicts_across_pages(first, second):
                    flagged.update((index_a, index_b))
    if not flagged:
        return lines
    result = list(lines)
    for index in flagged:
        line = result[index]
        if line.status == "unreadable":
            continue
        result[index] = replace(
            line,
            status="to_check",
            pharmacology_flags=(*line.pharmacology_flags, "cross_page_mismatch"),
        )
    return result


class PrescriptionReader:
    def __init__(
        self,
        client: OpenRouterClient,
        pages: PageReader,
        model_a: ModelProfile,
        model_b: ModelProfile,
        lexicon: Lexicon,
        pharmacology: PharmacologyRules,
        name_match_threshold: float = NAME_MATCH_THRESHOLD,
    ) -> None:
        self._client = client
        self._pages = pages
        self._model_a = model_a
        self._model_b = model_b
        self._lexicon = lexicon
        self._pharmacology = pharmacology
        self._name_match_threshold = name_match_threshold

    async def read_pages(self, pages: Sequence[PageInput]) -> tuple[list[MedicationLine], bool]:
        lines: list[MedicationLine] = []
        cut_off = False
        for page in pages:
            if page.image is None and not (page.text or "").strip():
                continue
            first, second = await self._double_read(page)
            cut_off = cut_off or page_cut_off(first, second)
            pairs = align(
                first.medications,
                second.medications,
                name_match_threshold=self._name_match_threshold,
            )
            for first_line, second_line in pairs:
                line = verify_line(
                    first_line,
                    second_line,
                    position=len(lines),
                    page_position=page.position,
                    lexicon=self._lexicon,
                    pharmacology=self._pharmacology,
                )
                if line.status != "sure" and page.image is not None:
                    estimate = _line_position_estimate(first_line, second_line)
                    if estimate is not None:
                        line = replace(line, image_extract=crop_band(page.image, estimate))
                lines.append(line)
        return _flag_cross_page_mismatches(lines), cut_off

    async def _double_read(
        self, page: PageInput
    ) -> tuple[PrescriptionReading, PrescriptionReading]:
        content = await self._pages.content(
            page,
            image_prompt=prompts.READ_PRESCRIPTION,
            text_prompt=prompts.READ_PRESCRIPTION_TEXT,
        )
        results = await asyncio.gather(
            self._read_once(self._model_a, content),
            self._read_once(self._model_b, content),
            return_exceptions=True,
        )
        readings = [result for result in results if isinstance(result, PrescriptionReading)]
        if len(readings) == 2:
            return readings[0], readings[1]
        failure = next(result for result in results if isinstance(result, BaseException))
        if isinstance(failure, AiError):
            raise failure
        raise AiOutputError("prescription double reading failed") from failure

    async def _read_once(
        self, profile: ModelProfile, content: list[dict[str, Any]]
    ) -> PrescriptionReading:
        raw = await self._client.complete_json(
            profile, content, operation="read_prescription", max_tokens=1500
        )
        try:
            return PrescriptionReading.model_validate(raw)
        except ValidationError as exc:
            logger.warning("prescription_reading_invalid", extra={"model": profile.model})
            raise AiOutputError(f"prescription output invalid: {exc.error_count()} errors") from exc
