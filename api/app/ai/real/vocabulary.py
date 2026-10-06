from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.ai.contracts import VocabularyCandidate
from app.ai.errors import AiOutputError
from app.ai.real import prompts
from app.ai.real.reasoning import Reasoner

MAX_TEXT_CHARS = 12_000


class _Word(BaseModel):
    word_fr: str
    category: Literal["health", "money", "school", "admin", "common"] = "common"
    sentence_fr: str


class _Words(BaseModel):
    words: list[_Word] = Field(default_factory=list)


async def extract_vocabulary(
    reasoner: Reasoner, text_fr: str, *, limit: int
) -> list[VocabularyCandidate]:
    raw = await reasoner.complete_json(
        prompts.EXTRACT_VOCABULARY.format(text=text_fr[:MAX_TEXT_CHARS], limit=limit),
        operation="extract_vocabulary",
        max_tokens=1200,
    )
    try:
        parsed = _Words.model_validate(raw)
    except ValidationError as exc:
        raise AiOutputError("vocabulary output invalid") from exc
    lowered_text = text_fr.lower()
    seen: set[str] = set()
    candidates: list[VocabularyCandidate] = []
    for word in parsed.words:
        normalized = word.word_fr.strip().lower()
        if not normalized or normalized in seen or len(normalized) < 3:
            continue
        if normalized[:4] not in lowered_text:
            continue
        seen.add(normalized)
        candidates.append(
            VocabularyCandidate(
                word_fr=normalized, category=word.category, sentence_fr=word.sentence_fr.strip()
            )
        )
    return candidates[:limit]
