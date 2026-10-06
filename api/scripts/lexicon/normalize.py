"""Normalisation des noms de médicaments (marques et DCI).

Toutes les fonctions sont pures et testées (tests/unit/test_lexicon.py).
"""

from __future__ import annotations

import html
import re
import unicodedata

_LIGATURES = str.maketrans({"\u0153": "oe", "\u0152": "OE", "\u00e6": "ae", "\u00c6": "AE"})
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_UPPER_ENTITY = re.compile(r"&([A-Z]+);")
_WHITESPACE = re.compile(r"\s+")

_UNIT = r"(?:mg|g|mcg|ug|\u00b5g|ui|mui|u\.i\.?|ml|l|%|mmol|meq|dose|doses)"
# Début du dosage, du conditionnement ou de la forme dans un libellé de marque.
_CUT = re.compile(
    r"(?<![a-z0-9])(?:"
    rf"\d+(?:[.,]\d+)?\s*{_UNIT}"
    r"|\d+(?:[.,]\d+)?"
    r"|(?:b|fl|t|p)\s*/\s*\d+"
    r"|(?:boite|flacon|tube)"
    r"|(?:comprimes?|cpr?|gelules?|sirop|suspension|susp|injectable|inj|ampoules?|sachets?"
    r"|collyre|creme|pommade|solution)"
    r")(?![a-z])"
)

_SALTS = (
    "chlorhydrate|dichlorhydrate|bromhydrate|hydrochlorure|hydrochloride|sulfate|sulphate"
    "|besilate|besylate|maleate|tartrate|citrate|phosphate|acetate|fumarate|succinate"
    "|mesilate|tosilate|nitrate"
)
_LEADING_SALT = re.compile(rf"^(?:{_SALTS})\s+(?:de\s+|d\s+)?(?P<core>.+)$")
_TRAILING_SALT = re.compile(
    rf"^(?P<core>.+?)\s+(?:{_SALTS}|sodique|sodium|potassique|calcique|magnesique"
    r"|(?:tri|mono|di|hemi)hydrat(?:e|ee|es)|anhydre|anhydree|hcl)$"
)
_COMPONENT_SPLIT = re.compile(r"\s*(?:/|\+|;|,|\bet\b)\s*")


def fix_entities(text: str) -> str:
    """Décode les entités HTML, y compris les entités mal casées vues chez l'ARP ('&EACUTE;')."""
    decoded = html.unescape(text)
    return _UPPER_ENTITY.sub(lambda m: html.unescape(f"&{m.group(1).capitalize()};"), decoded)


def clean_label(text: str) -> str:
    """Libellé lisible : entités décodées, espaces compactés.

    Ne change ni la casse ni les accents.
    """
    return _WHITESPACE.sub(" ", fix_entities(text)).strip()


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.translate(_LIGATURES))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def fold(text: str) -> str:
    """Minuscules, sans accents, tout ce qui n'est pas alphanumérique devient un espace."""
    lowered = strip_accents(text).lower()
    return _WHITESPACE.sub(" ", _NON_ALNUM.sub(" ", lowered)).strip()


def base_name(label: str) -> str:
    """Nom de marque sans dosage, conditionnement ni forme, normalisé.

    'ZERODOL P 100 MG/500 MG' -> 'zerodol p'. Un nombre au tout début est conservé
    ('5-FLUOROURACILE SANDOZ' -> '5 fluorouracile sandoz').
    """
    raw = strip_accents(fix_entities(label)).lower().strip()
    for match in _CUT.finditer(raw):
        if match.start() > 0:
            return fold(raw[: match.start()]) or fold(raw)
    return fold(raw)


def dci_components(dci: str | None) -> list[str]:
    """Composants d'une DCI (association 'A / B + C'), normalisés, triés, sans doublon."""
    if not dci:
        return []
    raw = strip_accents(fix_entities(dci)).lower()
    parts = (fold(p) for p in _COMPONENT_SPLIT.split(raw))
    return sorted({p for p in parts if p})


def dci_core(component: str) -> str:
    """Retire le sel ou l'hydrate ('chlorhydrate de metformine' -> 'metformine').

    Sert d'alias de recherche uniquement : la vérification compare cœur contre cœur,
    jamais un nom entier contre un cœur.
    """
    current = component
    for _ in range(3):
        match = _LEADING_SALT.match(current) or _TRAILING_SALT.match(current)
        if not match or not match.group("core"):
            break
        current = match.group("core")
    return current
