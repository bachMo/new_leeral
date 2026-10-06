"""Construit le lexique (CSV + rapport + manifeste) à partir des fichiers bruts.

Usage :
    python -m scripts.lexicon.build --raw-dir data/raw/2026-10-04 --out-dir app/data/lexicon \
        --bdpm-date 2026-09-29

Fichiers attendus dans --raw-dir :
    CIS_bdpm.txt, CIS_COMPO_bdpm.txt        (obligatoires, BDPM)
    CIS_MITM.txt                            (facultatif, codes ATC)
    arp_*.html                              (listes de l'ARP)
    manual_additions.csv                    (facultatif : label, dci, strength, form, validated_by)

Principe de sécurité : une DCI n'est `verified` que si elle existe dans une source de référence
(BDPM, ou ajout manuel validé par un professionnel). Une DCI de l'ARP proche d'une DCI vérifiée
sans lui être égale est `suspect_typo` (coquille probable). Les autres sont `unverified`.
Le moteur de lecture ne doit jamais classer une ligne `sure` à partir d'une entrée non `verified`.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, fields, replace
from datetime import UTC, datetime
from difflib import get_close_matches
from pathlib import Path

from scripts.lexicon import arp, bdpm
from scripts.lexicon.normalize import (
    base_name,
    clean_label,
    dci_components,
    dci_core,
    fold,
)
from scripts.lexicon.records import (
    STATUS_RANK,
    DciStatus,
    LexiconEntry,
    ParseStats,
    RawRecord,
    TermRow,
)

logger = logging.getLogger("leeral.lexicon")

_SOURCE_ORDER = {"bdpm": 0, "manual": 1, "national": 2}
_OFFICIAL_SOURCES = {"bdpm", "national"}


@dataclass
class BuildResult:
    entries: list[LexiconEntry]
    terms: list[TermRow]
    core_status: dict[str, tuple[DciStatus, str | None]]


def _is_reference(record: RawRecord) -> bool:
    return record.source == "bdpm" or (record.source == "manual" and bool(record.validated_by))


def build(records: Sequence[RawRecord], *, typo_cutoff: float = 0.85) -> BuildResult:
    ordered = sorted(records, key=lambda r: _SOURCE_ORDER.get(r.source, 9))
    reference = {dci_core(c) for r in ordered if _is_reference(r) for c in dci_components(r.dci)}
    reference_sorted = sorted(reference)
    cache: dict[str, tuple[DciStatus, str | None]] = {}

    def check(core: str) -> tuple[DciStatus, str | None]:
        if core not in cache:
            if core in reference:
                cache[core] = ("verified", None)
            else:
                suggestion: str | None = None
                if len(core) >= 5:
                    close = get_close_matches(core, reference_sorted, n=1, cutoff=typo_cutoff)
                    suggestion = close[0] if close else None
                cache[core] = ("suspect_typo", suggestion) if suggestion else ("unverified", None)
        return cache[core]

    entries: list[LexiconEntry] = []
    index_by_key: dict[tuple[str, str, str, str], int] = {}
    also_in: dict[int, set[str]] = defaultdict(set)

    for record in ordered:
        label = clean_label(record.label)
        first_part = label.split(",")[0] if record.source == "bdpm" else label
        name_normalized = base_name(first_part)
        if not name_normalized:
            continue
        components = dci_components(record.dci)
        cores = sorted({dci_core(c) for c in components})
        results = [check(core) for core in cores]
        status: DciStatus = "unverified"
        suggestion_text: str | None = None
        if results:
            status = max((s for s, _ in results), key=lambda s: STATUS_RANK[s])
            pairs = [
                f"{core} -> {sug}" for core, (_, sug) in zip(cores, results, strict=True) if sug
            ]
            suggestion_text = "; ".join(pairs) or None
        dci_normalized = " / ".join(components) or None
        key = (
            name_normalized,
            dci_normalized or "",
            fold(record.strength or ""),
            fold(record.form or ""),
        )
        if key in index_by_key:
            existing = index_by_key[key]
            if entries[existing].source != record.source:
                also_in[existing].add(record.source)
            continue
        index_by_key[key] = len(entries)
        entries.append(
            LexiconEntry(
                source=record.source,
                external_code=record.external_code,
                name=label,
                name_normalized=name_normalized,
                label_normalized=fold(label),
                dci=clean_label(record.dci) if record.dci else None,
                dci_normalized=dci_normalized,
                dci_core=" / ".join(cores) or None,
                strength=record.strength,
                form=record.form,
                route=record.route,
                holder=record.holder,
                therapeutic_class=record.therapeutic_class,
                atc_code=record.atc_code,
                dci_status=status,
                dci_suggestion=suggestion_text,
                is_active=record.is_active,
                also_in="",
                validated_by=record.validated_by,
            )
        )
    entries = [
        replace(e, also_in="|".join(sorted(also_in.get(i, set())))) for i, e in enumerate(entries)
    ]
    return BuildResult(entries=entries, terms=_build_terms(entries, check), core_status=cache)


def _build_terms(
    entries: Sequence[LexiconEntry],
    check: Callable[[str], tuple[DciStatus, str | None]],
) -> list[TermRow]:
    """Termes cherchables dédoublonnés : marques, DCI complètes et cœurs de DCI."""
    counts: Counter[tuple[str, str]] = Counter()
    sources: dict[tuple[str, str], set[str]] = defaultdict(set)
    official: set[str] = set()
    validated: set[str] = set()
    for entry in entries:
        entry_sources = {entry.source, *[s for s in entry.also_in.split("|") if s]}
        brand_key = (entry.name_normalized, "brand")
        counts[brand_key] += 1
        sources[brand_key] |= entry_sources
        if entry_sources & _OFFICIAL_SOURCES:
            official.add(entry.name_normalized)
        elif entry.validated_by:
            validated.add(entry.name_normalized)
        for component in (entry.dci_normalized or "").split(" / "):
            if not component:
                continue
            for kind, term in (("dci", component), ("dci_core", dci_core(component))):
                counts[(term, kind)] += 1
                sources[(term, kind)] |= entry_sources
    rows: list[TermRow] = []
    for (term, kind), n in counts.items():
        if kind == "brand":
            status = (
                "official"
                if term in official
                else "validated"
                if term in validated
                else "manual_unvalidated"
            )
        else:
            status = check(dci_core(term))[0]
        rows.append(TermRow(term, kind, status, n, "|".join(sorted(sources[(term, kind)]))))
    return sorted(rows, key=lambda r: (r.kind, r.term))


def load_manual(path: Path) -> list[RawRecord]:
    """Ajouts manuels (marques vues sur de vraies ordonnances, validées par un pharmacien)."""
    records: list[RawRecord] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            label = (row.get("label") or "").strip()
            if not label:
                continue
            records.append(
                RawRecord(
                    source="manual",
                    external_code=None,
                    label=label,
                    dci=(row.get("dci") or "").strip() or None,
                    strength=(row.get("strength") or "").strip() or None,
                    form=(row.get("form") or "").strip() or None,
                    validated_by=(row.get("validated_by") or "").strip() or None,
                )
            )
    return records


def write_csv(path: Path, rows: Sequence[LexiconEntry] | Sequence[TermRow]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    names = [f.name for f in fields(rows[0])]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_report(
    result: BuildResult,
    arp_stats: list[ParseStats],
    bdpm_date: str | None,
    built_at: str,
) -> str:
    entries = result.entries
    by_source = Counter(e.source for e in entries)
    status_counts = Counter(e.dci_status for e in entries)
    cores = [t for t in result.terms if t.kind == "dci_core"]
    core_status = Counter(t.status for t in cores)
    brands = [t for t in result.terms if t.kind == "brand"]
    suspects = sorted((t for t in cores if t.status == "suspect_typo"), key=lambda t: -t.n_entries)
    unverified = sorted((t for t in cores if t.status == "unverified"), key=lambda t: -t.n_entries)
    lines = [
        "# Rapport de construction du lexique",
        "",
        f"- Construit le : {built_at}",
        f"- Date de mise à jour de la BDPM (à citer) : {bdpm_date or 'NON RENSEIGNEE'}",
        f"- Entrées : {len(entries)} "
        f"({', '.join(f'{k}: {v}' for k, v in sorted(by_source.items()))})",
        f"- Marques distinctes : {len(brands)}",
        f"- DCI (cœurs) distinctes : {len(cores)} "
        f"({', '.join(f'{k}: {v}' for k, v in sorted(core_status.items()))})",
        f"- Entrées par statut de DCI : "
        f"{', '.join(f'{k}: {v}' for k, v in sorted(status_counts.items()))}",
        "",
        "## Contrôle de complétude de l'ARP",
        "",
    ]
    if not arp_stats:
        lines.append("Aucune page de l'ARP lue.")
    for i, stats in enumerate(arp_stats, start=1):
        lines.append(
            f"- Page {i} : tableaux trouvés {stats.tables_found}, utilisés {stats.tables_used}, "
            f"lignes lues {stats.rows_total}, conservées {stats.rows_kept}"
        )
        lines.extend(f"  - ATTENTION : {w}" for w in stats.warnings)
    lines += ["", "## Coquilles probables dans les DCI (à relire par un pharmacien)", ""]
    for term in suspects[:40]:
        suggestion = result.core_status.get(term.term, ("", None))[1]
        lines.append(
            f"- `{term.term}` -> `{suggestion}` ({term.n_entries} entrées, {term.sources})"
        )
    if not suspects:
        lines.append("Aucune.")
    lines += [
        "",
        "## DCI non vérifiées les plus fréquentes (aucune correspondance de référence)",
        "",
    ]
    lines.extend(f"- `{t.term}` ({t.n_entries} entrées, {t.sources})" for t in unverified[:40])
    if not unverified:
        lines.append("Aucune.")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Construit le lexique de médicaments de Leeral.")
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--bdpm-date", help="Date de mise à jour de la BDPM (JJ/MM/AAAA), à citer.")
    parser.add_argument("--typo-cutoff", type=float, default=0.85)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    raw: Path = args.raw_dir
    spec, compo, mitm = raw / "CIS_bdpm.txt", raw / "CIS_COMPO_bdpm.txt", raw / "CIS_MITM.txt"
    if not spec.exists() or not compo.exists():
        logger.error("CIS_bdpm.txt et CIS_COMPO_bdpm.txt sont obligatoires dans %s", raw)
        return 2
    if not args.bdpm_date:
        logger.warning(
            "--bdpm-date absent : la licence BDPM impose de citer la date de mise à jour."
        )

    records = bdpm.load_records(
        bdpm.read_text(spec),
        bdpm.read_text(compo),
        bdpm.read_text(mitm) if mitm.exists() else None,
    )
    logger.info("BDPM : %d spécialités", len(records))

    arp_stats: list[ParseStats] = []
    arp_files = sorted(raw.glob("arp_*.html"))
    for page in arp_files:
        parsed, stats = arp.parse_amm_html(page.read_text(encoding="utf-8", errors="replace"))
        arp_stats.append(stats)
        records.extend(parsed)
        logger.info("ARP %s : %d lignes", page.name, stats.rows_kept)
    if not arp_files:
        logger.warning(
            "Aucun fichier arp_*.html : le lexique ne couvrira pas les marques du Sénégal."
        )

    manual = raw / "manual_additions.csv"
    if manual.exists():
        records.extend(load_manual(manual))

    result = build(records, typo_cutoff=args.typo_cutoff)
    out: Path = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "lexicon_entries.csv", result.entries)
    write_csv(out / "lexicon_terms.csv", result.terms)
    built_at = datetime.now(UTC).isoformat(timespec="seconds")
    (out / "lexicon_report.md").write_text(
        render_report(result, arp_stats, args.bdpm_date, built_at), encoding="utf-8"
    )
    manifest = {
        "built_at": built_at,
        "bdpm_update_date": args.bdpm_date,
        "bdpm_source": "https://base-donnees-publique.medicaments.gouv.fr",
        "arp_source": "https://arp.sn",
        "inputs_sha256": {p.name: sha256(p) for p in [spec, compo, *arp_files] if p.exists()},
        "entries": len(result.entries),
        "terms": len(result.terms),
    }
    (out / "lexicon_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Lexique écrit dans %s (%d entrées)", out, len(result.entries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
