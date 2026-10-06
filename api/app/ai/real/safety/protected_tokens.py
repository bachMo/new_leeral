import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

_NUMBER = r"\d+(?:[.,:h]\d+)*"
_TOKEN_OPEN = "⟦"
_TOKEN_CLOSE = "⟧"
_TOKEN = re.compile(rf"{_TOKEN_OPEN}(\d+){_TOKEN_CLOSE}")


@dataclass(frozen=True, slots=True)
class ProtectedText:
    text: str
    values: tuple[str, ...]

    @property
    def has_tokens(self) -> bool:
        return bool(self.values)


class TokenMismatchError(Exception):
    def __init__(self, missing: list[int], duplicated: list[int]) -> None:
        self.missing = missing
        self.duplicated = duplicated
        super().__init__(f"missing tokens {missing}, duplicated tokens {duplicated}")


def protect(text: str, *, protected_terms: Sequence[str] = ()) -> ProtectedText:
    values: list[str] = []
    terms = sorted(
        {term.strip() for term in protected_terms if term.strip()}, key=len, reverse=True
    )
    alternatives = [rf"\b{re.escape(term)}\b" for term in terms] + [_NUMBER]
    pattern = re.compile("|".join(alternatives), re.IGNORECASE)

    def substitute(match: re.Match[str]) -> str:
        values.append(match.group(0))
        return f"{_TOKEN_OPEN}{len(values) - 1}{_TOKEN_CLOSE}"

    return ProtectedText(text=pattern.sub(substitute, text), values=tuple(values))


def restore(translated: str, protected: ProtectedText) -> str:
    counts = Counter(int(index) for index in _TOKEN.findall(translated))
    expected = range(len(protected.values))
    missing = [index for index in expected if counts[index] == 0]
    duplicated = [index for index in expected if counts[index] > 1]
    unknown = [index for index in counts if index >= len(protected.values)]
    if missing or duplicated or unknown:
        raise TokenMismatchError(missing, duplicated + unknown)
    return _TOKEN.sub(lambda match: protected.values[int(match.group(1))], translated)
