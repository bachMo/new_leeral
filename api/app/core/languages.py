from enum import StrEnum

from app.core.errors import AppError, ErrorCode


class Language(StrEnum):
    WOLOF = "wo"
    PULAAR = "ff"
    SERER = "sr"


class TextLanguage(StrEnum):
    WOLOF = "wo"
    PULAAR = "ff"
    SERER = "sr"
    FRENCH = "fr"


AVAILABLE_LANGUAGES: frozenset[Language] = frozenset({Language.WOLOF, Language.PULAAR})

LANGUAGE_NAMES: dict[Language, str] = {
    Language.WOLOF: "Wolof",
    Language.PULAAR: "Pulaar",
    Language.SERER: "Seereer",
}


def ensure_available(language: Language) -> Language:
    if language not in AVAILABLE_LANGUAGES:
        raise AppError(ErrorCode.LANGUAGE_NOT_AVAILABLE, fields={"language": language.value})
    return language
