import re

from app.core.languages import Language

# Vocabulaire fermé des moments de prise, tel qu'on les trouve sur une ordonnance française.
# Volontairement limité à des expressions multi-mots spécifiques au contexte médical (jamais un
# mot isolé comme « pendant » ou « jours », trop génériques et ambigus hors de ce contexte pour
# être substitués sans risque dans n'importe quel document).
TIMING_PHRASES: tuple[str, ...] = (
    "avant le repas",
    "après le repas",
    "pendant le repas",
    "au cours du repas",
    "à jeun",
    "au coucher",
    "au réveil",
    "au lever",
    "le matin",
    "le soir",
    "le midi",
)

# DRAFT volontairement vide : traduire une consigne de moment de prise (« avant/après le repas »)
# a un impact santé réel si c'est faux, contrairement au nom d'un mois. Tant qu'une langue n'a pas
# d'entrée ici, `localize_posology_phrase` ne substitue rien et laisse la phrase partir vers le
# traducteur général (comportement actuel, aucune régression) — à remplir uniquement après
# relecture par un locuteur natif et, idéalement, un pharmacien (même posture que
# `pharmacology_rules.csv`, `reviewed_by` vide : voir AI_DECISIONS.md, décision 7 et décision 23).
TRANSLATED_TIMING: dict[Language, dict[str, str]] = {
    Language.WOLOF: {},
    Language.PULAAR: {},
    Language.SERER: {},
}

_TIMING_PATTERN = re.compile(
    "|".join(re.escape(phrase) for phrase in sorted(TIMING_PHRASES, key=len, reverse=True)),
    re.IGNORECASE,
)


def localize_posology_phrase(
    text: str,
    language: Language,
    *,
    table: dict[Language, dict[str, str]] = TRANSLATED_TIMING,
) -> tuple[str, tuple[str, ...]]:
    """Replace a known intake-timing phrase with its validated translation, if one exists.

    Mirrors `safety.dates.localize_month_names`: the matched phrase is replaced in `text` and
    returned alongside the substituted words, to be passed as `protected_terms` so the general
    translator copies them verbatim instead of retranslating them. A phrase with no entry yet in
    `table[language]` is left untouched — this function is a no-op until the catalog is filled.
    """
    translations = table.get(language)
    if not translations:
        return text, ()
    substituted: list[str] = []

    def replace(match: re.Match[str]) -> str:
        found = match.group(0).lower()
        localized = translations.get(found)
        if localized is None:
            return match.group(0)
        substituted.append(localized)
        return localized

    return _TIMING_PATTERN.sub(replace, text), tuple(substituted)
