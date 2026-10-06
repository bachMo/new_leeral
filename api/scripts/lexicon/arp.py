"""Lecture des listes publiques de l'ARP (Agence sénégalaise de réglementation pharmaceutique).

Pages concernées : https://arp.sn/liste-des-amms/ et https://arp.sn/medicaments-rcp/ (tableaux HTML
des médicaments autorisés au Sénégal : nom, numéro d'AMM, DCI, dosage, forme, laboratoire...).

Les colonnes sont retrouvées par leur intitulé (pas par leur position) car les deux pages
n'ont pas le même ordre. Le parseur n'utilise que la bibliothèque standard.

Limites connues : un tableau chargé dynamiquement (JavaScript) ou paginé côté serveur n'est
pas visible dans le HTML brut. `ParseStats` permet de le détecter (nombre de lignes lues).
"""

from __future__ import annotations

from html.parser import HTMLParser

from scripts.lexicon.normalize import clean_label, fold
from scripts.lexicon.records import ParseStats, RawRecord

_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("nom du medicament", "nom"),
    "amm": ("numero amm", "numero de l amm"),
    "dci": ("dci", "dci2"),
    "strength": ("dosage",),
    "presentation": ("presentation",),
    "form": ("forme galenique",),
    "route": ("voie d administration",),
    "holder": ("laboratoire", "nom du laboratoire titulaire"),
    "klass": ("classe therapeutique",),
}


class _TableCollector(HTMLParser):
    """Collecte toutes les tables d'un document sous forme de listes de lignes de texte."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._stack: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._stack.append([])
        elif tag == "tr" and self._stack:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._stack:
            if any(self._row):
                self._stack[-1].append(self._row)
            self._row = None
        elif tag == "table" and self._stack:
            self.tables.append(self._stack.pop())

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def _column_map(header: list[str]) -> dict[str, int]:
    folded = [fold(h) for h in header]
    mapping: dict[str, int] = {}
    for key, aliases in _ALIASES.items():
        for alias in aliases:
            if alias in folded:
                mapping[key] = folded.index(alias)
                break
    return mapping


def parse_amm_html(html_text: str) -> tuple[list[RawRecord], ParseStats]:
    collector = _TableCollector()
    collector.feed(html_text)
    stats = ParseStats(tables_found=len(collector.tables))
    records: list[RawRecord] = []
    for table in collector.tables:
        if not table:
            continue
        header, body = table[0], table[1:]
        columns = _column_map(header)
        if "name" not in columns or "dci" not in columns:
            continue
        stats.tables_used += 1
        header_folded = [fold(h) for h in header]
        for row in body:
            stats.rows_total += 1
            if [fold(c) for c in row] == header_folded:
                continue  # en-tête répété par certains plugins de tableau

            def cell(key: str, row: list[str] = row, columns: dict[str, int] = columns) -> str:
                index = columns.get(key)
                return clean_label(row[index]) if index is not None and index < len(row) else ""

            name = cell("name")
            if not name:
                continue
            amm = cell("amm")
            records.append(
                RawRecord(
                    source="national",
                    external_code=f"ARP:{amm}" if amm else None,
                    label=name,
                    dci=cell("dci") or None,
                    strength=cell("strength") or None,
                    form=cell("form") or None,
                    route=cell("route") or None,
                    holder=cell("holder") or None,
                    therapeutic_class=cell("klass") or None,
                )
            )
            stats.rows_kept += 1
    if stats.tables_used == 0:
        stats.warnings.append(
            "Aucun tableau avec colonnes 'nom' et 'DCI' : "
            "la page est peut-être chargée en JavaScript."
        )
    return records, stats
