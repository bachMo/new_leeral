from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.ai.contracts import ComposedDocument, ComposedWriting, WritingField, WritingSection
from app.ai.errors import AiOutputError
from app.ai.real import prompts
from app.ai.real.reasoning import Reasoner

_DOCUMENTS_RULE = {
    "cv_cover_letter": 'Produis deux documents : un CV ("cv") et une lettre de motivation '
    '("cover_letter").',
    "request_letter": 'Produis un seul document : une lettre de demande ("letter").',
    "bank_letter": 'Produis un seul document : un courrier à la banque ("letter").',
    "other": 'Produis un seul document : un courrier ("letter").',
}

_WRITING_LABELS = {
    "cv_cover_letter": "CV et lettre de motivation",
    "request_letter": "lettre de demande administrative",
    "bank_letter": "courrier à une banque",
    "other": "courrier",
}


class _Value(BaseModel):
    value: str | None = None


class _Section(BaseModel):
    heading: str | None = None
    lines: list[str] = Field(default_factory=list)


class _Document(BaseModel):
    kind: Literal["cv", "cover_letter", "letter"]
    title: str
    sections: list[_Section]


class _Composition(BaseModel):
    documents: list[_Document] = Field(min_length=1)
    readback_fr: str


async def interpret_answer(reasoner: Reasoner, field: WritingField, answer_fr: str) -> str | None:
    raw = await reasoner.complete_json(
        prompts.INTERPRET_WRITING_ANSWER.format(
            question=field.question_fr,
            hint=f"Précision : {field.hint_fr}" if field.hint_fr else "",
            answer=answer_fr,
        ),
        operation="interpret_writing_answer",
        max_tokens=400,
    )
    try:
        value = _Value.model_validate(raw).value
    except ValidationError as exc:
        raise AiOutputError("writing interpretation invalid") from exc
    return value.strip() if value and value.strip() else None


async def compose(
    reasoner: Reasoner,
    writing_type: str,
    fields: Sequence[WritingField],
    values: dict[str, str],
) -> ComposedWriting:
    facts = "\n".join(
        f"- {field.question_fr} → {values[field.key]}" for field in fields if values.get(field.key)
    )
    raw = await reasoner.complete_json(
        prompts.COMPOSE_WRITING.format(
            writing_type=_WRITING_LABELS.get(writing_type, "courrier"),
            facts=facts,
            documents_rule=_DOCUMENTS_RULE.get(writing_type, _DOCUMENTS_RULE["other"]),
        ),
        operation="compose_writing",
        max_tokens=3000,
    )
    try:
        parsed = _Composition.model_validate(raw)
    except ValidationError as exc:
        raise AiOutputError("writing composition invalid") from exc
    return ComposedWriting(
        documents=tuple(
            ComposedDocument(
                kind=document.kind,
                title=document.title.strip(),
                sections=tuple(
                    WritingSection(
                        heading=section.heading.strip() if section.heading else None,
                        lines=tuple(line.strip() for line in section.lines if line.strip()),
                    )
                    for section in document.sections
                ),
            )
            for document in parsed.documents
        ),
        readback_fr=parsed.readback_fr.strip(),
    )
