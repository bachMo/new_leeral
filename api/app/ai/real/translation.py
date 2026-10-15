import asyncio
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.ai.contracts import LocalizedText
from app.ai.errors import (
    AiAuthError,
    AiError,
    AiInputError,
    AiOutputError,
    AiUnavailableError,
    TranslationError,
)
from app.ai.real import prompts
from app.ai.real.clients.openrouter import ModelProfile, OpenRouterClient
from app.ai.real.safety.dates import localize_month_names
from app.ai.real.safety.posology_phrases import localize_posology_phrase
from app.ai.real.safety.protected_tokens import TokenMismatchError, protect, restore
from app.core.languages import Language

logger = logging.getLogger("leeral.ai.translation")

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?:;\n])\s+")
_CONCURRENCY = 4
_WHOLE_TEXT_ATTEMPTS = 2
_MIN_LENGTH_RATIO = 0.3
_MAX_LENGTH_RATIO = 4.0
_ISOLATED_TERM_MAX_WORDS = 4
_SENTENCE_END = re.compile(r"[.!?]")

UNTRANSLATED_NOTICE_FR = (
    "Une partie n'a pas pu être traduite avec certitude. "
    "Demande à quelqu'un de confiance de te la relire."
)


@dataclass(frozen=True, slots=True)
class _Segment:
    source: str
    translated: str | None


def _is_isolated_term(text: str) -> bool:
    return not _SENTENCE_END.search(text) and len(text.split()) <= _ISOLATED_TERM_MAX_WORDS


def split_sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(text) if sentence.strip()]


def _protect_known_phrases(sentence: str, language: Language) -> tuple[str, tuple[str, ...]]:
    """Deterministic substitutions that must never reach the general translator unprotected."""
    with_months, months = localize_month_names(sentence, language)
    with_timing, timing = localize_posology_phrase(with_months, language)
    return with_timing, (*months, *timing)


class Translator:
    def __init__(
        self,
        client: OpenRouterClient,
        primary: ModelProfile,
        fallback: ModelProfile,
        *,
        max_attempts: int,
    ) -> None:
        self._client = client
        self._primary = primary
        self._fallback = fallback
        self._max_attempts = max(1, max_attempts)
        self._notices: dict[Language, str] = {}
        self._semaphore = asyncio.Semaphore(_CONCURRENCY)

    async def localize(
        self, text_fr: str, language: Language, *, protected_terms: Sequence[str] = ()
    ) -> LocalizedText:
        sentences = split_sentences(text_fr)
        if not sentences:
            raise AiInputError("nothing to translate")
        if _is_isolated_term(text_fr):
            return await self._localize_by_sentence(sentences, text_fr, language, protected_terms)
        prepared_text, extra_terms = _protect_known_phrases(" ".join(sentences), language)
        whole = await self._translate_whole(
            prepared_text,
            "fr",
            language,
            (*protected_terms, *extra_terms),
            source_length=len(text_fr),
        )
        if whole is not None:
            return LocalizedText(language=language, text=whole, text_fr=text_fr, complete=True)
        return await self._localize_by_sentence(sentences, text_fr, language, protected_terms)

    async def _localize_by_sentence(
        self,
        sentences: list[str],
        text_fr: str,
        language: Language,
        protected_terms: Sequence[str],
    ) -> LocalizedText:
        prepared = [_protect_known_phrases(sentence, language) for sentence in sentences]
        segments = await asyncio.gather(
            *(
                self._translate_sentence(sentence, "fr", language, (*protected_terms, *extra))
                for sentence, extra in prepared
            )
        )
        if all(segment.translated is None for segment in segments):
            raise TranslationError(f"no sentence could be translated to {language.value}")
        parts: list[str] = []
        complete = True
        notice_added = False
        for segment in segments:
            if segment.translated is not None:
                parts.append(segment.translated)
                continue
            complete = False
            if not notice_added:
                notice = await self._notice(language)
                if notice:
                    parts.append(notice)
                notice_added = True
        return LocalizedText(
            language=language, text=" ".join(parts), text_fr=text_fr, complete=complete
        )

    async def to_french(self, text: str, language: Language) -> str:
        sentences = split_sentences(text) or [text]
        whole = await self._translate_whole(
            " ".join(sentences), language.value, "fr", (), source_length=len(text)
        )
        if whole is not None:
            return whole
        segments = await asyncio.gather(
            *(
                self._translate_sentence(sentence, language.value, "fr", ())
                for sentence in sentences
            )
        )
        translated = [segment.translated for segment in segments if segment.translated]
        if not translated:
            raise TranslationError(f"could not translate from {language.value}")
        return " ".join(translated)

    async def _notice(self, language: Language) -> str | None:
        if language not in self._notices:
            segment = await self._translate_sentence(UNTRANSLATED_NOTICE_FR, "fr", language, ())
            if segment.translated is None:
                return None
            self._notices[language] = segment.translated
        return self._notices[language]

    async def _translate_sentence(
        self, sentence: str, source: str, target: Language | str, protected_terms: Sequence[str]
    ) -> _Segment:
        target_code = target.value if isinstance(target, Language) else target
        protected = protect(sentence, protected_terms=protected_terms)
        async with self._semaphore:
            for attempt in range(self._max_attempts):
                profile = self._primary if attempt == 0 else self._fallback
                try:
                    raw = await self._call(profile, protected.text, source, target_code)
                except (AiUnavailableError, AiOutputError):
                    if profile is self._fallback:
                        raise
                    raw = await self._call(self._fallback, protected.text, source, target_code)
                if "\n" in raw:
                    logger.warning(
                        "translation_multiline_output",
                        extra={"attempt": attempt, "target": target_code},
                    )
                    continue
                try:
                    return _Segment(sentence, restore(raw, protected))
                except TokenMismatchError as exc:
                    logger.warning(
                        "translation_token_mismatch",
                        extra={
                            "attempt": attempt,
                            "missing": exc.missing,
                            "duplicated": exc.duplicated,
                            "target": target_code,
                        },
                    )
        return _Segment(sentence, None)

    async def _call(self, profile: ModelProfile, text: str, source: str, target: str) -> str:
        prompt = prompts.TRANSLATE.format(
            source=prompts.LANGUAGE_NAMES[source],
            target=prompts.LANGUAGE_NAMES[target],
            text=text,
        )
        raw = await self._client.complete(profile, prompt, operation="translate", max_tokens=1500)
        return raw.strip().strip('"').strip()

    async def _translate_whole(
        self,
        text: str,
        source: str,
        target: Language | str,
        protected_terms: Sequence[str],
        *,
        source_length: int,
    ) -> str | None:
        target_code = target.value if isinstance(target, Language) else target
        protected = protect(text, protected_terms=protected_terms)
        prompt = _whole_text_prompt(protected.text, source, target_code)
        max_tokens = min(8000, 1500 + len(protected.text))
        for attempt in range(_WHOLE_TEXT_ATTEMPTS):
            try:
                async with self._semaphore:
                    raw = await self._client.complete(
                        self._primary, prompt, operation="translate_text", max_tokens=max_tokens
                    )
            except AiAuthError:
                raise
            except AiError as exc:
                logger.warning(
                    "translation_whole_failed",
                    extra={"attempt": attempt, "target": target_code, "error": type(exc).__name__},
                )
                continue
            candidate = raw.strip().strip('"').strip()
            if "\n" in candidate:
                logger.warning(
                    "translation_whole_multiline", extra={"attempt": attempt, "target": target_code}
                )
                continue
            try:
                restored = restore(candidate, protected)
            except TokenMismatchError as exc:
                logger.warning(
                    "translation_whole_token_mismatch",
                    extra={
                        "attempt": attempt,
                        "missing": exc.missing,
                        "duplicated": exc.duplicated,
                        "target": target_code,
                    },
                )
                continue
            ratio = len(restored) / max(1, source_length)
            if not _MIN_LENGTH_RATIO <= ratio <= _MAX_LENGTH_RATIO:
                logger.warning(
                    "translation_whole_length_suspicious",
                    extra={"attempt": attempt, "ratio": round(ratio, 2), "target": target_code},
                )
                continue
            return restored
        logger.warning("translation_falls_back_to_sentences", extra={"target": target_code})
        return None


def _whole_text_prompt(text: str, source: str, target: str) -> str:
    if target == "fr":
        return prompts.TRANSLATE_TO_FRENCH.format(source=prompts.LANGUAGE_NAMES[source], text=text)
    return prompts.TRANSLATE_FOR_LISTENERS.format(target=prompts.LANGUAGE_NAMES[target], text=text)
