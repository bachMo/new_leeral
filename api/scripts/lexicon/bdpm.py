"""Lecture des fichiers de la BDPM (base de données publique des médicaments, France).

Format : fichiers texte séparés par des tabulations, sans en-tête (voir le fichier descriptif
de la BDPM). Colonnes utilisées :
- CIS_bdpm.txt : 0 code CIS, 1 dénomination, 2 forme, 3 voies, 4 statut AMM,
  6 état de commercialisation
- CIS_COMPO_bdpm.txt : 0 code CIS, 3 substance, 4 dosage, 6 nature (SA = substance active)
- CIS_MITM.txt : 0 code CIS, 1 code ATC

Licence : réutilisation libre à condition de ne pas altérer les données, de citer la source
et la date de mise à jour. Les fichiers bruts ne sont donc jamais modifiés ici.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from scripts.lexicon.normalize import clean_label
from scripts.lexicon.records import RawRecord


def read_text(path: Path) -> str:
    """Lit un fichier de la BDPM : UTF-8 si possible, sinon Windows-1252."""
    data = path.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _rows(text: str) -> list[list[str]]:
    return [line.split("\t") for line in text.splitlines() if line.strip()]


def _col(row: list[str], index: int) -> str:
    return row[index].strip() if index < len(row) else ""


def parse_compositions(text: str) -> dict[str, list[tuple[str, str]]]:
    """code CIS -> liste de (substance active, dosage)."""
    result: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in _rows(text):
        if _col(row, 6) != "SA":
            continue
        cis, substance, dosage = _col(row, 0), _col(row, 3), _col(row, 4)
        if cis and substance:
            result[cis].append((substance, dosage))
    return dict(result)


def parse_atc(text: str) -> dict[str, str]:
    """code CIS -> code ATC (fichier des médicaments d'intérêt thérapeutique majeur)."""
    return {_col(r, 0): _col(r, 1) for r in _rows(text) if _col(r, 0) and _col(r, 1)}


def load_records(
    specialties_text: str,
    compositions_text: str,
    mitm_text: str | None = None,
) -> list[RawRecord]:
    compositions = parse_compositions(compositions_text)
    atc = parse_atc(mitm_text) if mitm_text else {}
    records: list[RawRecord] = []
    for row in _rows(specialties_text):
        cis, denomination = _col(row, 0), _col(row, 1)
        if not cis or not denomination:
            continue
        parts = compositions.get(cis, [])
        substances = list(dict.fromkeys(name for name, _ in parts))
        strengths = [dose for _, dose in parts if dose]
        status = _col(row, 4).lower()
        marketed = _col(row, 6).lower() == "commercialisée"
        records.append(
            RawRecord(
                source="bdpm",
                external_code=f"CIS:{cis}",
                label=clean_label(denomination),
                dci=" / ".join(substances) or None,
                strength=" / ".join(strengths) or None,
                form=_col(row, 2) or None,
                route=_col(row, 3) or None,
                holder=_col(row, 10) or None,
                atc_code=atc.get(cis),
                is_active=status.startswith("autorisation active") and marketed,
            )
        )
    return records
