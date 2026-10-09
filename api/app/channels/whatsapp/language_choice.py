import re
import unicodedata
from difflib import SequenceMatcher

from app.core.languages import Language

LANGUAGE_ALIASES: dict[Language, tuple[str, ...]] = {
    Language.WOLOF: ("wolof", "wolofu", "olof", "ouolof", "walaf"),
    Language.PULAAR: ("pulaar", "pular", "poular", "pulaaar", "fulfulde", "peul", "pullo"),
    Language.SERER: ("seereer", "sereer", "serer", "serere", "sereere"),
}
FILLER_WORDS = frozenset(
    {
        "ci",
        "e",
        "en",
        "la",
        "le",
        "ma",
        "rek",
        "tan",
        "tey",
        "lakk",
        "langue",
        "demngal",
        "haalpulaar",
        "ko",
        "mi",
        "dama",
        "begg",
    }
)
MAX_SPOKEN_WORDS = 3
MATCH_THRESHOLD = 0.8


def named_language(transcript: str) -> Language | None:
    words = _words(transcript)
    if not words or len(words) > MAX_SPOKEN_WORDS:
        return None
    candidates = [word for word in words if word not in FILLER_WORDS]
    if len(candidates) != 1:
        return None
    return _closest(candidates[0])


def _words(text: str) -> list[str]:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    plain = plain.replace("ɗ", "d").replace("ŋ", "n").replace("ñ", "n")
    return re.findall(r"[a-z]+", plain)


def _closest(word: str) -> Language | None:
    score, language = max(
        (SequenceMatcher(None, word, alias).ratio(), language)
        for language, aliases in LANGUAGE_ALIASES.items()
        for alias in aliases
    )
    return language if score >= MATCH_THRESHOLD else None
