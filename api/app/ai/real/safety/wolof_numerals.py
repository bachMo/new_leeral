"""Deterministic Wolof cardinal number generator, grounded in two sources:

- Guérin, Maximilien (2020). "Système de numération en wolof : description et comparaison avec
  les autres langues atlantiques", Faits de langues 51(2), 121-144 (peer-reviewed). Gives the
  base lexemes, the two irregular forms (20, 30), and the "-i ... téeméer/junni" genitive
  construction for a single-digit multiplier (e.g. "ñent-i téeméer" = 400).
- Boston University, "200 Words" Wolof vocabulary page (bu.edu/200word/wolof/numbers), a teaching
  resource rather than peer-reviewed, but the only source found with an actual example above
  10 000: "Fukki Téémééri Junni" for one million, i.e. "fukk-i téeméer-i junni" = 10 x 100 x 1000.
  This is what grounds `_genitive`'s cascading rule below -- without it, a multi-digit or nested
  multiplier (any amount at or above 10 000) would have had no textual support at all.

`spell_number` reproduces every worked example from both sources exactly: 11, 17, 19, 20, 30, 90,
100, 119, 426, 600, 1000, 4000, 9112 (Guérin) and 1 000 000 via "benn milyoŋ" (Boston University,
the loanword alternative given alongside "fukki téeméeri junni" for the same value) -- see tests.

20 and 30 are the system's only irregular forms below 1000 (confirmed by Guérin's abstract); it
gives two attested variants for each, and this module uses the one marked as the contemporary/
Senegal default: "ñaar fukk" for 20 (not the older "nit"), "fanweer" for 30 (not the
Gambia-leaning "ñett fukk").

Covers 0-9 999 999. Above 999 999, "milyoŋ" (a French loanword, confirmed by both sources) takes
an explicit multiplier even for one ("Benn Milyoŋ", not "Milyoŋ" alone -- unlike téeméer/junni,
which drop a multiplier of 1). This module only covers a single-digit count of millions (1-9): a
multi-digit one (10+ million) is excluded on purpose, same reasoning as any gap below -- no
attested or clearly analogous form to extend from. `spell_number` returns None outside its range
-- callers must have a safe fallback (see numerals.py).
"""

_UNITS = {1: "benn", 2: "ñaar", 3: "ñett", 4: "ñent", 5: "juróom"}
_ADDITIVE_UNITS = {"benn", "ñaar", "ñett", "ñent"}


def _unit_word(n: int) -> str:
    if n in _UNITS:
        return _UNITS[n]
    return f"juróom {_UNITS[n - 5]}"


def _tens_word(tens_digit: int) -> str:
    if tens_digit == 1:
        return "fukk"
    if tens_digit == 2:
        return "ñaar fukk"
    if tens_digit == 3:
        return "fanweer"
    return f"{_unit_word(tens_digit)} fukk"


def _below_100(n: int) -> str:
    if n < 10:
        return _unit_word(n)
    tens, units = divmod(n, 10)
    tens_word = _tens_word(tens)
    return tens_word if units == 0 else f"{tens_word} ak {_unit_word(units)}"


def _genitive(phrase: str) -> str:
    """Attach the genitive-plural "-i" marker to a multiplier phrase, as a multiplier of
    téeméer/junni (e.g. "ñent-i téeméer" = 400) or recursively as a multiplier built the same way
    (e.g. "fukk-i téeméer-i junni" = 1 000 000, see module docstring).

    Fully hyphenated only for the bare 5+unit compound 6-9 (juróom-benn-i, juróom-ñent-i --
    attested exactly). Every other phrase, including one that already carries its own "-i" from a
    nested call, takes the marker on its rightmost word only, leaving the rest untouched -- this
    is what the "Fukki Téémééri Junni" example shows (fukk-i, then téeméer-i, junni left bare),
    and is applied here the same way to an "ak"-built tens+units compound, which has no attested
    example of taking this marker at all. The text only ever reaches a TTS engine, never a reader,
    so the exact hyphen placement has no effect on what gets spoken -- only the word sequence
    does."""
    words = phrase.split(" ")
    if len(words) == 2 and words[0] == "juróom" and words[1] in _ADDITIVE_UNITS:
        return f"{words[0]}-{words[1]}-i"
    head, _, last = phrase.rpartition(" ")
    return f"{head} {last}-i" if head else f"{last}-i"


def _multiple(multiplier: int, base_singular: str) -> str:
    """multiplier * base_singular (téeméer, junni, or a smaller multiplier phrase recursively).
    Omits the multiplier entirely for 1 (attested: "téeméer"/"junni" alone -- unlike "milyoŋ",
    handled separately in `spell_number`)."""
    if multiplier == 1:
        return base_singular
    multiplier_phrase = _unit_word(multiplier) if multiplier < 10 else _below_1000(multiplier)
    return f"{_genitive(multiplier_phrase)} {base_singular}"


def _below_1000(n: int) -> str:
    if n < 100:
        return _below_100(n)
    hundreds, remainder = divmod(n, 100)
    parts = [_multiple(hundreds, "téeméer")]
    if remainder:
        parts.append(_below_100(remainder))
    return " ak ".join(parts)


def _below_million(n: int) -> str:
    if n < 1000:
        return _below_1000(n)
    thousands, remainder = divmod(n, 1000)
    parts = [_multiple(thousands, "junni")]
    if remainder:
        parts.append(_below_1000(remainder))
    return " ak ".join(parts)


def spell_number(n: int) -> str | None:
    """Spell out `n` in Wolof words, or None outside the grounded 0-9 999 999 range (0 itself has
    no dedicated number word in Wolof, see Guérin's section 2.1)."""
    if n <= 0 or n > 9_999_999:
        return None
    if n < 1_000_000:
        return _below_million(n)
    millions, remainder = divmod(n, 1_000_000)
    parts = [f"{_unit_word(millions)} milyoŋ"]
    if remainder:
        parts.append(_below_million(remainder))
    return " ak ".join(parts)
