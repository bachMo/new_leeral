"""Structures de données du lexique."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DciStatus = Literal["verified", "suspect_typo", "unverified"]

# Rang pour comparer deux statuts : plus le rang est haut, moins on peut s'y fier.
STATUS_RANK: dict[DciStatus, int] = {"verified": 0, "suspect_typo": 1, "unverified": 2}


@dataclass(frozen=True)
class RawRecord:
    """Une ligne d'une source, avant normalisation."""

    source: str  # "bdpm" | "national" | "manual"
    external_code: str | None
    label: str
    dci: str | None = None
    strength: str | None = None
    form: str | None = None
    route: str | None = None
    holder: str | None = None
    therapeutic_class: str | None = None
    atc_code: str | None = None
    is_active: bool = True
    validated_by: str | None = None


@dataclass(frozen=True)
class LexiconEntry:
    """Une ligne du lexique, au format de la table `lexicon_entries` (docs/database.md)."""

    source: str
    external_code: str | None
    name: str
    name_normalized: str
    label_normalized: str
    dci: str | None
    dci_normalized: str | None
    dci_core: str | None
    strength: str | None
    form: str | None
    route: str | None
    holder: str | None
    therapeutic_class: str | None
    atc_code: str | None
    dci_status: DciStatus
    dci_suggestion: str | None
    is_active: bool
    also_in: str
    validated_by: str | None


@dataclass(frozen=True)
class TermRow:
    """Un terme cherchable (marque, DCI ou cœur de DCI) avec son statut."""

    term: str
    kind: str  # "brand" | "dci" | "dci_core"
    status: str  # "official" pour une marque, sinon un DciStatus
    n_entries: int
    sources: str


@dataclass
class ParseStats:
    """Contrôle de complétude d'un parseur, repris dans le rapport."""

    tables_found: int = 0
    tables_used: int = 0
    rows_total: int = 0
    rows_kept: int = 0
    warnings: list[str] = field(default_factory=list)
