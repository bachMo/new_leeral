"""Rapprochement flou d'un nom lu contre le lexique de médicaments (apps/api/app/data/lexicon/).

Ne réimplémente pas le lexique : lit le CSV déjà construit par `apps/api/scripts/lexicon/build.py`
(voir docs/lexique-medicaments.md). Sert uniquement à mesurer, hors ligne et sans appel réseau,
l'effet d'un rapprochement flou sur les erreurs non signalées du banc d'essai de lecture
(voir eval/apply_lexicon.py). La vraie implémentation produit (`app/safety/lexicon_match.py`,
pas encore écrite) devra suivre la même règle de sécurité : un statut non "verified"/"official"
ne peut jamais rendre une ligne "sure" (docs/lexique-medicaments.md section 3).
Bibliothèque standard uniquement.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LEXICON_PATH = (
    Path(__file__).resolve().parent.parent / "apps" / "api" / "app" / "data" / "lexicon" / "lexicon_terms.csv"
)

# Statuts qui autorisent une ligne "sure" (docs/lexique-medicaments.md section 3).
TRUSTED_STATUSES = {"official", "verified"}
FUZZY_RATIO_THRESHOLD = 0.85  # seuil documenté pour une coquille suspectée


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", stripped.lower()).split())


@dataclass(frozen=True)
class LexiconMatch:
    query: str
    matched_term: str | None
    status: str | None  # official | verified | unverified | suspect_typo | None (aucun rapprochement)
    ratio: float  # 1.0 si correspondance exacte
    trusted: bool  # True seulement si statut dans TRUSTED_STATUSES ET correspondance exacte


class Lexicon:
    def __init__(self, exact: dict[str, str], by_first_letter: dict[str, list[str]]) -> None:
        self._exact = exact  # terme replié -> meilleur statut
        self._by_first_letter = by_first_letter  # première lettre -> termes repliés (pour le flou)

    @classmethod
    def load(cls, path: Path = DEFAULT_LEXICON_PATH) -> Lexicon:
        exact: dict[str, str] = {}
        by_first_letter: dict[str, list[str]] = defaultdict(list)
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                term = fold(row["term"])
                if not term:
                    continue
                status = row["status"]
                # Une marque "official" ou une DCI "verified" l'emporte sur un statut moins sûr
                # si le même terme replié apparaît plusieurs fois (différents dosages/formes).
                current = exact.get(term)
                if current is None or (current not in TRUSTED_STATUSES and status in TRUSTED_STATUSES):
                    exact[term] = status
                by_first_letter[term[0]].append(term)
        return cls(exact, dict(by_first_letter))

    def __len__(self) -> int:
        return len(self._exact)

    def lookup(self, name: str) -> LexiconMatch:
        query = fold(name)
        if not query:
            return LexiconMatch(query=name, matched_term=None, status=None, ratio=0.0, trusted=False)
        status = self._exact.get(query)
        if status is not None:
            return LexiconMatch(query=name, matched_term=query, status=status, ratio=1.0, trusted=status in TRUSTED_STATUSES)

        best_term: str | None = None
        best_ratio = 0.0
        for candidate in self._by_first_letter.get(query[0], ()):
            if abs(len(candidate) - len(query)) > 4:
                continue
            ratio = _similarity(query, candidate)
            if ratio > best_ratio:
                best_term, best_ratio = candidate, ratio
        if best_term is not None and best_ratio >= FUZZY_RATIO_THRESHOLD:
            return LexiconMatch(
                query=name, matched_term=best_term, status=self._exact[best_term], ratio=best_ratio, trusted=False
            )
        return LexiconMatch(query=name, matched_term=None, status=None, ratio=best_ratio, trusted=False)


def _similarity(a: str, b: str) -> float:
    import difflib

    return difflib.SequenceMatcher(None, a, b).ratio()
