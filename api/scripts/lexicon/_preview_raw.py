"""Convertit les sources brutes en CSV lisibles (en-têtes, UTF-8), sans modifier les originaux.

Usage ponctuel, pour inspection humaine seulement :
    python -m scripts.lexicon._preview_raw --raw-dir data/raw/2026-10-04

Les fichiers BDPM sont des tabulations sans en-tête, en Windows-1252 : illisibles tels quels.
Les pages ARP sont du HTML brut (5 Mo). Ce script ne remplace pas lexicon_entries.csv
(app/data/lexicon/), qui reste la vue normalisée et dédupliquée de référence.
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Sequence
from pathlib import Path

from scripts.lexicon import arp, bdpm

_BDPM_SPEC_HEADER = [
    "code_cis",
    "denomination",
    "forme_pharmaceutique",
    "voies_administration",
    "statut_amm",
    "type_procedure",
    "etat_commercialisation",
    "date_amm",
    "statut_bdm",
    "numero_autorisation_europeenne",
    "titulaire",
    "surveillance_renforcee",
]
_BDPM_COMPO_HEADER = [
    "code_cis",
    "forme_composition",
    "code_substance",
    "denomination_substance",
    "dosage",
    "reference_dosage",
    "nature_composant",
    "numero_lien",
]
_BDPM_MITM_HEADER = ["code_cis", "code_atc", "libelle", "url"]
_ARP_HEADER = ["name", "amm", "dci", "strength", "presentation", "form", "route", "holder", "class"]


def _write_tabbed(source: Path, destination: Path, header: Sequence[str]) -> int:
    text = bdpm.read_text(source)
    rows = [line.split("\t") for line in text.splitlines() if line.strip()]
    with destination.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aperçu lisible des sources brutes du lexique.")
    parser.add_argument("--raw-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    raw: Path = args.raw_dir
    out = raw / "lisible"
    out.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    if (raw / "CIS_bdpm.txt").exists():
        counts["CIS_bdpm.csv"] = _write_tabbed(
            raw / "CIS_bdpm.txt", out / "CIS_bdpm.csv", _BDPM_SPEC_HEADER
        )
    if (raw / "CIS_COMPO_bdpm.txt").exists():
        counts["CIS_COMPO_bdpm.csv"] = _write_tabbed(
            raw / "CIS_COMPO_bdpm.txt", out / "CIS_COMPO_bdpm.csv", _BDPM_COMPO_HEADER
        )
    if (raw / "CIS_MITM.txt").exists():
        counts["CIS_MITM.csv"] = _write_tabbed(
            raw / "CIS_MITM.txt", out / "CIS_MITM.csv", _BDPM_MITM_HEADER
        )
    for page in sorted(raw.glob("arp_*.html")):
        records, _ = arp.parse_amm_html(page.read_text(encoding="utf-8", errors="replace"))
        destination = out / f"{page.stem}.csv"
        with destination.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(_ARP_HEADER)
            for r in records:
                writer.writerow(
                    [
                        r.label,
                        r.external_code,
                        r.dci,
                        r.strength,
                        "",
                        r.form,
                        r.route,
                        r.holder,
                        r.therapeutic_class,
                    ]
                )
        counts[destination.name] = len(records)

    for name, n in counts.items():
        print(f"{name}: {n} lignes")
    print(f"Aperçus écrits dans {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
