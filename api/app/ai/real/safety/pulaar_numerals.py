"""Deterministic Pulaar (Senegal) cardinal number generator, grounded in a source cited by a
peer-reviewed article: Sylla, Yèro (1982). "Grammaire moderne du pulaar", Les Nouvelles Éditions
Africaines, Dakar -- quoted in Guérin, Maximilien (2020), "Système de numération en wolof :
description et comparaison avec les autres langues atlantiques", Faits de langues 51(2), §3.3.

`spell_number` reproduces the one fully worked example given for this source (1245 ->
"ujunere e teemedde ɗiɗi e capanɗe nay e joy") exactly. Unlike the wolof module
(`wolof_numerals.py`), no irregular forms are reported for this system at all (Guérin's article
flags wolof's 20 and 30 explicitly; it flags nothing for pulaar) -- but the pulaar section of
that article is much shorter than its wolof section, so treat this as less exhaustively checked
against edge cases, not as equally scrutinized.

A general-public site (languagesandnumbers.com) describes a structurally identical system but
with different words for 10/20/1000 (nogay, wuluure) -- its page states that dialect is
"pular fuuta" of the former Fouta-Djalon imamate, i.e. Guinea, not the Senegalese Pulaar this
module targets, so it was not used as a source here.

Covers 0-999 999, same reasoning as the wolof module: the source's own example only goes as far
as a single-digit multiplier before "ujunere" (e.g. "ujunere" alone = 1000); `_multiple` extends
the same rule recursively for a multi-digit multiplier (e.g. 25 000 = "ujunnaaje" + the spelled-
out word for 25) -- a structurally motivated generalization, not an attested form itself. Treat
numbers at or above 10 000 as slightly less certain than smaller ones for this reason. Beyond
999 999, `spell_number` returns None rather than guess -- callers must have a safe fallback (see
numerals.py).
"""

_UNITS = {
    1: "goo",
    2: "ɗiɗi",
    3: "tati",
    4: "nay",
    5: "joy",
    6: "jeegom",
    7: "jeeɗiɗi",
    8: "jeetati",
    9: "jeenay",
}


def _below_100(n: int) -> str:
    if n < 10:
        return _UNITS[n]
    tens, units = divmod(n, 10)
    if tens == 1:
        tens_word = "sappo"
    elif tens == 2:
        tens_word = "noogaas"
    else:
        tens_word = f"capanɗe {_UNITS[tens]}"
    return tens_word if units == 0 else f"{tens_word} e {_UNITS[units]}"


def _below_1000(n: int) -> str:
    if n < 100:
        return _below_100(n)
    hundreds, remainder = divmod(n, 100)
    parts = [_multiple(hundreds, "teemedere", "teemedde")]
    if remainder:
        parts.append(_below_100(remainder))
    return " e ".join(parts)


def _multiple(multiplier: int, singular: str, plural: str) -> str:
    if multiplier == 1:
        return singular
    multiplier_word = _UNITS[multiplier] if multiplier < 10 else _below_1000(multiplier)
    return f"{plural} {multiplier_word}"


def spell_number(n: int) -> str | None:
    """Spell out `n` in Senegalese Pulaar words, or None outside the grounded 0-999 999 range (0
    itself has no dedicated number word, same situation as wolof)."""
    if n <= 0 or n > 999_999:
        return None
    if n < 1000:
        return _below_1000(n)
    thousands, remainder = divmod(n, 1000)
    parts = [_multiple(thousands, "ujunere", "ujunnaaje")]
    if remainder:
        parts.append(_below_1000(remainder))
    return " e ".join(parts)
