import re

from app.core.languages import Language

FRENCH_MONTHS: tuple[str, ...] = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)

# DRAFT — rédigé par emprunt direct du français (même convention que "oktoobar" pour octobre,
# confirmée par un utilisateur wolofophone), jamais relu par un locuteur natif. À valider avant
# de considérer ces noms fiables, même posture que `pharmacology_rules.csv` (voir AI_DECISIONS.md,
# décision 7) : seul "octobre" est confirmé, les 11 autres mois de chaque langue et les trois
# mois pulaar/sérère sont une hypothèse de travail, pas une vérité linguistique établie.
MONTH_NAMES: dict[Language, tuple[str, ...]] = {
    Language.WOLOF: (
        "samwiyee",
        "fewriyee",
        "mars",
        "awril",
        "me",
        "suwe",
        "sulet",
        "ut",
        "sàttumbar",
        "oktoobar",
        "nowàmbar",
        "desàmbar",
    ),
    Language.PULAAR: (
        "sanwiyee",
        "fewriyee",
        "marsa",
        "awiril",
        "mee",
        "suwe",
        "sulyee",
        "ut",
        "satumbar",
        "oktoobar",
        "nowembar",
        "desembar",
    ),
    Language.SERER: (
        "sanwiye",
        "fewriye",
        "marsa",
        "awiril",
        "me",
        "suwe",
        "sulet",
        "ut",
        "satumbar",
        "oktoobar",
        "nowambar",
        "desambar",
    ),
}

_MONTH_PATTERN = re.compile(
    "|".join(re.escape(month) for month in FRENCH_MONTHS), re.IGNORECASE
)


def localize_month_names(text: str, language: Language) -> tuple[str, tuple[str, ...]]:
    """Replace French month names with their target-language equivalent before translation.

    Returns the rewritten text and the substituted words, to be passed as `protected_terms`
    so the translator copies them verbatim instead of retranslating (and possibly mangling)
    an already-correct word (see AI_DECISIONS.md, decision 14).
    """
    table = MONTH_NAMES.get(language)
    if table is None:
        return text, ()
    substituted: list[str] = []

    def replace(match: re.Match[str]) -> str:
        localized = table[FRENCH_MONTHS.index(match.group(0).lower())]
        substituted.append(localized)
        return localized

    return _MONTH_PATTERN.sub(replace, text), tuple(substituted)
