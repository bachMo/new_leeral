"""Mesure la couverture du lexique sur de vrais noms lus dans des ordonnances.

Usage :
    python -m scripts.lexicon.check_coverage --terms app/data/lexicon/lexicon_terms.csv \
        --names eval/noms_ordonnances.txt

Le fichier de noms contient un nom de médicament par ligne, tel qu'écrit sur l'ordonnance
(avec ou sans dosage). Pour chaque nom :
- exact : trouvé tel quel (marque, DCI ou cœur de DCI) ;
- proche : une ou plusieurs suggestions ; JAMAIS acceptées automatiquement ;
- absent : aucune correspondance, candidat à un ajout manuel validé par un pharmacien.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path

from scripts.lexicon.normalize import base_name

logger = logging.getLogger("leeral.lexicon")


@dataclass(frozen=True)
class Match:
    name: str
    verdict: str  # "exact" | "near" | "miss"
    kind: str | None = None
    status: str | None = None
    suggestions: tuple[str, ...] = ()


def load_terms(path: Path) -> dict[str, tuple[str, str]]:
    """terme normalisé -> (type, statut). Une marque l'emporte sur une DCI de même nom."""
    index: dict[str, tuple[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            term = row["term"]
            if term not in index or row["kind"] == "brand":
                index[term] = (row["kind"], row["status"])
    return index


def classify(name: str, index: dict[str, tuple[str, str]], cutoff: float = 0.85) -> Match:
    normalized = base_name(name)
    if normalized in index:
        kind, status = index[normalized]
        return Match(name, "exact", kind, status)
    close = tuple(get_close_matches(normalized, list(index), n=3, cutoff=cutoff))
    if close:
        return Match(name, "near", suggestions=close)
    return Match(name, "miss")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Couverture du lexique sur des noms réels.")
    parser.add_argument("--terms", type=Path, required=True)
    parser.add_argument("--names", type=Path, required=True)
    parser.add_argument("--cutoff", type=float, default=0.85)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    index = load_terms(args.terms)
    names = [n.strip() for n in args.names.read_text(encoding="utf-8").splitlines() if n.strip()]
    matches = [classify(n, index, args.cutoff) for n in names]
    out = sys.stdout
    for m in matches:
        detail = f"{m.kind}/{m.status}" if m.verdict == "exact" else ", ".join(m.suggestions)
        out.write(f"{m.verdict:6} {m.name}  {detail}\n")
    total = len(matches) or 1
    exact = sum(m.verdict == "exact" for m in matches)
    near = sum(m.verdict == "near" for m in matches)
    out.write(
        f"\nTotal {len(matches)} | exact {exact} ({exact / total:.0%}) | "
        f"proche {near} ({near / total:.0%}) | absent {len(matches) - exact - near}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
