"""Tests du constructeur de lexique (hors ligne, sur de petits fichiers d'exemple).

Teste `scripts/lexicon/` (BDPM + ARP -> `app/ai/real/data/lexicon_terms.csv`), pas le module de
recherche en ligne (`app/ai/real/safety/lexicon.py`, testé dans `tests/ai/test_lexicon.py`)."""

from __future__ import annotations

import csv
from pathlib import Path

from scripts.lexicon import arp, bdpm, build
from scripts.lexicon.check_coverage import classify, load_terms
from scripts.lexicon.normalize import (
    base_name,
    dci_components,
    dci_core,
    fix_entities,
    fold,
)
from scripts.lexicon.records import RawRecord

BDPM_SPEC = (
    "61266250\tDOLIPRANE 500 mg, comprimé\tcomprimé\torale\tAutorisation active\t"
    "Procédure nationale\tCommercialisée\t12/03/1999\t\t\tOPELLA\tNon\n"
    "60234100\tAMOXICILLINE BIOGARAN 500 mg, gélule\tgélule\torale\tAutorisation active\t"
    "Procédure nationale\tCommercialisée\t01/01/2000\t\t\tBIOGARAN\tNon\n"
    "60234101\tAMOXICILLINE BIOGARAN 1 g, comprimé\tcomprimé\torale\tAutorisation active\t"
    "Procédure nationale\tCommercialisée\t01/01/2000\t\t\tBIOGARAN\tNon\n"
    "69000001\tGLUCOPHAGE 850 mg, comprimé\tcomprimé\torale\tAutorisation active\t"
    "Procédure nationale\tNon commercialisée\t01/01/2000\t\t\tMERCK\tNon\n"
)
BDPM_COMPO = (
    "61266250\tcomprimé\t02202\tPARACÉTAMOL\t500 mg\tun comprimé\tSA\t1\n"
    "60234100\tgélule\t03001\tAMOXICILLINE TRIHYDRATÉE\t500 mg\tune gélule\tSA\t1\n"
    "60234101\tcomprimé\t03001\tAMOXICILLINE TRIHYDRATÉE\t1 g\tun comprimé\tSA\t1\n"
    "69000001\tcomprimé\t05001\tCHLORHYDRATE DE METFORMINE\t850 mg\tun comprimé\tSA\t1\n"
    "69000001\tcomprimé\t99999\tEXCIPIENT X\t10 mg\tun comprimé\tST\t1\n"
)
ARP_HTML = """
<html><body><table>
<tr><th>NOM DU MEDICAMENT</th><th>Numero AMM</th><th>Prix Public</th><th>DCI2</th><th>dosage</th>
<th>présentation</th><th>Forme Galénique</th><th>Voie d’administration</th><th>Laboratoire</th>
<th>classe thérapeutique</th><th>RCP</th></tr>
<tr><td>AMOXI-DENK 1000</td><td>7429bis</td><td>0</td><td>AMOXCILLINE</td><td>1000 mg</td>
<td>B/10</td><td>comprimé</td><td>orale</td><td>DENK PHARMA</td><td>ANTIBIOTIQUE</td>
<td>RCP</td></tr>
<tr><td>ZERODOL P 100 MG/500 MG</td><td>7329</td><td>2377</td><td>ACECLOFENAC / PARACETAMOL</td>
<td>100 mg / 500 mg</td><td>BOITE / 10</td><td>COMPRIMÉ</td><td>ORALE</td><td>IPCA</td>
<td>ANTALGIQUE</td><td>RCP</td></tr>
<tr><td>ALEPSAL</td><td>7974</td><td>1462</td><td>PHÉNOBARBITAL</td><td>150 mg</td>
<td>B/30</td><td>comprimé</td><td>orale</td><td>GEN&EACUTE;VRIER</td><td>ANTIEPILEPTIQUE</td><td>RCP</td></tr>
<tr><td>INCONNU XYZ</td><td>1</td><td>1</td><td>ZZQXWVY</td><td>5 mg</td>
<td>B/30</td><td>comprimé</td><td>orale</td><td>LABO</td><td></td><td>RCP</td></tr>
<tr><td>NOM DU MEDICAMENT</td><td>Numero AMM</td><td>Prix Public</td><td>DCI2</td><td>dosage</td>
<td>présentation</td><td>Forme Galénique</td><td>Voie d’administration</td><td>Laboratoire</td>
<td>classe thérapeutique</td><td>RCP</td></tr>
</table></body></html>
"""


def _records() -> list[RawRecord]:
    records = bdpm.load_records(BDPM_SPEC, BDPM_COMPO)
    parsed, _ = arp.parse_amm_html(ARP_HTML)
    return [*records, *parsed]


def test_fold_removes_accents_and_ligatures() -> None:
    assert fold("Œstrogène  Béta-Bloquant") == "oestrogene beta bloquant"


def test_fix_entities_repairs_uppercase_entity() -> None:
    assert fix_entities("GEN&EACUTE;VRIER") == "GENÉVRIER"
    assert fix_entities("A &amp; B") == "A & B"


def test_base_name_strips_dosage_pack_and_form() -> None:
    assert base_name("DOLIPRANE 500 mg") == "doliprane"
    assert base_name("ZERODOL P 100 MG/500 MG") == "zerodol p"
    assert base_name("ALBENDAZOLE UBITHERA 400MG B/50") == "albendazole ubithera"
    assert base_name("AMOXI-DENK 1000") == "amoxi denk"
    assert base_name("TERCEFIX 200 MG COMPRIME B10") == "tercefix"


def test_base_name_keeps_legitimate_digits() -> None:
    assert base_name("5-FLUOROURACILE SANDOZ") == "5 fluorouracile sandoz"
    assert base_name("VITAMINE B12") == "vitamine b12"
    assert base_name("AMLOVAS-AT") == "amlovas at"


def test_core_handles_feminine_hydrate_used_by_bdpm() -> None:
    assert dci_core("amoxicilline trihydratee") == "amoxicilline"


def test_dci_components_and_core() -> None:
    assert dci_components("ACECLOFENAC + PARACETAMOL") == ["aceclofenac", "paracetamol"]
    assert dci_components("PARACETAMOL / ACECLOFENAC") == ["aceclofenac", "paracetamol"]
    assert dci_components(None) == []
    assert dci_core("chlorhydrate de metformine") == "metformine"
    assert dci_core("chlorhydrate d amiodarone") == "amiodarone"
    assert dci_core("amlodipine besilate") == "amlodipine"
    assert dci_core("acide folique") == "acide folique"


def test_bdpm_parsing_joins_composition_and_flags_marketing() -> None:
    records = bdpm.load_records(BDPM_SPEC, BDPM_COMPO)
    by_code = {r.external_code: r for r in records}
    assert by_code["CIS:61266250"].dci == "PARACÉTAMOL"
    assert by_code["CIS:61266250"].is_active is True
    assert by_code["CIS:69000001"].dci == "CHLORHYDRATE DE METFORMINE"  # le "ST" est ignoré
    assert by_code["CIS:69000001"].is_active is False


def test_arp_parsing_by_header_and_cleaning() -> None:
    records, stats = arp.parse_amm_html(ARP_HTML)
    assert stats.tables_used == 1
    assert stats.rows_kept == 4  # l'en-tête répété est ignoré
    zerodol = next(r for r in records if r.label.startswith("ZERODOL"))
    assert zerodol.external_code == "ARP:7329"
    assert zerodol.dci == "ACECLOFENAC / PARACETAMOL"
    alepsal = next(r for r in records if r.label == "ALEPSAL")
    assert alepsal.holder == "GENÉVRIER"


def test_arp_without_expected_table_warns() -> None:
    records, stats = arp.parse_amm_html("<html><body><p>chargement...</p></body></html>")
    assert records == []
    assert stats.warnings


def test_typo_dci_is_never_verified() -> None:
    result = build.build(_records())
    amoxi = next(e for e in result.entries if e.name_normalized == "amoxi denk")
    assert amoxi.dci_status == "suspect_typo"
    assert amoxi.dci_suggestion is not None
    assert "amoxicilline" in amoxi.dci_suggestion


def test_reference_and_unknown_dci_statuses() -> None:
    result = build.build(_records())
    status = {e.name_normalized: e.dci_status for e in result.entries}
    assert status["doliprane"] == "verified"
    assert status["glucophage"] == "verified"
    # aceclofenac est absent de la BDPM de test : l'association ne peut pas être vérifiée
    assert status["zerodol p"] == "unverified"


def test_unknown_dci_is_unverified_not_verified() -> None:
    result = build.build(_records())
    inconnu = next(e for e in result.entries if e.name_normalized == "inconnu xyz")
    assert inconnu.dci_status == "unverified"


def test_entries_are_deduplicated_on_name_dci_strength_form() -> None:
    result = build.build(_records())
    amoxi_bdpm = [e for e in result.entries if e.name_normalized == "amoxicilline biogaran"]
    assert len(amoxi_bdpm) == 2  # 500 mg gélule et 1 g comprimé restent distincts
    duplicated = build.build([*_records(), *_records()])
    assert len(duplicated.entries) == len(result.entries)


def test_terms_contain_brand_dci_and_core() -> None:
    result = build.build(_records())
    kinds = {(t.term, t.kind) for t in result.terms}
    assert ("doliprane", "brand") in kinds
    assert ("paracetamol", "dci") in kinds
    assert ("metformine", "dci_core") in kinds
    brand = next(t for t in result.terms if t.term == "doliprane" and t.kind == "brand")
    assert brand.status == "official"


def test_manual_unvalidated_entry_cannot_be_verified(tmp_path: Path) -> None:
    csv_path = tmp_path / "manual_additions.csv"
    csv_path.write_text(
        "label,dci,strength,form,validated_by\n"
        "MARQUE LOCALE,PARACETAMOL,500 mg,comprimé,\n"
        "AUTRE MARQUE,NOUVELLEDCI,10 mg,gélule,Pharmacien X\n",
        encoding="utf-8",
    )
    manual = build.load_manual(csv_path)
    result = build.build([*bdpm.load_records(BDPM_SPEC, BDPM_COMPO), *manual])
    status = {e.name_normalized: e.dci_status for e in result.entries}
    assert status["marque locale"] == "verified"  # sa DCI existe dans la BDPM
    assert status["autre marque"] == "verified"  # validée par un professionnel
    brand_status = {t.term: t.status for t in result.terms if t.kind == "brand"}
    assert brand_status["marque locale"] == "manual_unvalidated"
    assert brand_status["autre marque"] == "validated"
    assert brand_status["doliprane"] == "official"


def test_outputs_are_written_and_coverage_classifies(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "CIS_bdpm.txt").write_text(BDPM_SPEC, encoding="utf-8")
    (raw / "CIS_COMPO_bdpm.txt").write_text(BDPM_COMPO, encoding="utf-8")
    (raw / "arp_liste_amms.html").write_text(ARP_HTML, encoding="utf-8")
    out = tmp_path / "out"
    assert (
        build.main(["--raw-dir", str(raw), "--out-dir", str(out), "--bdpm-date", "29/09/2026"]) == 0
    )
    for name in (
        "lexicon_entries.csv",
        "lexicon_terms.csv",
        "lexicon_report.md",
        "lexicon_manifest.json",
    ):
        assert (out / name).exists()
    with (out / "lexicon_entries.csv").open(encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    assert "dci_status" in header and "name_normalized" in header
    index = load_terms(out / "lexicon_terms.csv")
    assert classify("Doliprane 1000 mg", index).verdict == "exact"
    assert classify("Dolipran", index).verdict == "near"
    assert classify("Xyzzyqwerty", index).verdict == "miss"


def test_build_requires_bdpm(tmp_path: Path) -> None:
    (tmp_path / "raw").mkdir()
    assert build.main(["--raw-dir", str(tmp_path / "raw"), "--out-dir", str(tmp_path / "o")]) == 2
