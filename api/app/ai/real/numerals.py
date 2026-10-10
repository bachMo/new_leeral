import json
import logging
import re
from typing import Any

from app.ai.errors import AiError
from app.ai.real import prompts
from app.ai.real.clients.openrouter import ModelProfile, OpenRouterClient
from app.core.languages import Language

logger = logging.getLogger("leeral.ai.numerals")

_NUMBER = re.compile(r"\d{1,3}(?:[ .  ]\d{3})+(?!\d)|\d+")
_SEPARATORS = re.compile(r"[ .  ]")

# KIRIKU's TTS reads 0-10 correctly on its own; above that it silently drops the number from the
# audio instead of speaking it (confirmed by comparing synthesized audio byte-for-byte with and
# without the number). Writing it out in words avoids that — worth doing carefully here since the
# numbers at stake are money amounts and ages, not decoration.
_SPOKEN_THRESHOLD = 10


def _numbers_above(text: str, threshold: int) -> list[int]:
    seen: dict[int, None] = {}
    for match in _NUMBER.finditer(text):
        value = int(_SEPARATORS.sub("", match.group(0)))
        if value > threshold:
            seen.setdefault(value, None)
    return list(seen)


def _parse_words_by_value(raw: dict[str, Any], expected: list[int]) -> dict[int, str]:
    entries = raw.get("numbers")
    if not isinstance(entries, list):
        return {}
    wanted = set(expected)
    result: dict[int, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        value, words = entry.get("value"), entry.get("words")
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and value in wanted
            and isinstance(words, str)
            and words.strip()
        ):
            result[value] = words.strip()
    return result


def _parse_value_by_words(raw: dict[str, Any]) -> dict[str, int]:
    entries = raw.get("numbers")
    if not isinstance(entries, list):
        return {}
    result: dict[str, int] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        words, value = entry.get("words"), entry.get("value")
        if isinstance(words, str) and isinstance(value, int) and not isinstance(value, bool):
            result[words.strip()] = value
    return result


async def _convert_to_words(
    client: OpenRouterClient, profile: ModelProfile, values: list[int], language_name: str
) -> dict[int, str]:
    raw = await client.complete_json(
        profile,
        prompts.NUMBER_TO_WORDS.format(language=language_name, numbers=json.dumps(values)),
        operation="number_to_words",
        max_tokens=max(600, 200 * len(values)),
    )
    return _parse_words_by_value(raw, values)


async def _verify_round_trip(
    client: OpenRouterClient,
    profile: ModelProfile,
    words_by_value: dict[int, str],
    language_name: str,
) -> dict[int, str]:
    phrases = list(words_by_value.values())
    raw = await client.complete_json(
        profile,
        prompts.WORDS_TO_NUMBER.format(language=language_name, phrases=json.dumps(phrases)),
        operation="words_to_number",
        max_tokens=max(600, 150 * len(phrases)),
    )
    value_by_words = _parse_value_by_words(raw)
    return {
        value: words
        for value, words in words_by_value.items()
        if value_by_words.get(words) == value
    }


def _substitute(text: str, verified: dict[int, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        value = int(_SEPARATORS.sub("", match.group(0)))
        return verified.get(value, match.group(0))

    return _NUMBER.sub(replace, text)


async def spell_out_numbers(
    client: OpenRouterClient, profile: ModelProfile, text: str, language: Language
) -> str:
    """Replace numbers KIRIKU's TTS would otherwise drop (above 10) with their spelled-out form,
    kept only once an independent reverse conversion confirms it represents the same value — a
    number KIRIKU still drops is safer than a number KIRIKU would mispronounce, so any failure
    here (parsing, mismatch, AI error) falls back to leaving `text` unchanged. `profile` should be
    a model already trusted for Wolof/Pulaar fidelity (the translator's primary model): a cheaper
    model tested for this produced inconsistent, unverifiable numerals."""
    values = _numbers_above(text, _SPOKEN_THRESHOLD)
    if not values:
        return text
    language_name = prompts.LANGUAGE_NAMES[language.value]
    try:
        words_by_value = await _convert_to_words(client, profile, values, language_name)
        if not words_by_value:
            return text
        verified = await _verify_round_trip(client, profile, words_by_value, language_name)
    except AiError as exc:
        logger.warning("numerals_spell_out_failed", extra={"error": str(exc)})
        return text
    if not verified:
        return text
    if len(verified) < len(words_by_value):
        logger.warning(
            "numerals_round_trip_mismatch",
            extra={"attempted": len(words_by_value), "verified": len(verified)},
        )
    return _substitute(text, verified)
