import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(_NON_ALNUM.sub(" ", stripped.lower()).split())


def trigrams(text: str) -> set[str]:
    padded = f"  {text} "
    return {padded[index : index + 3] for index in range(len(padded) - 2)}
