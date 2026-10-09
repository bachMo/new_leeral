"""Tests du rapprochement avec le lexique (aucune dépendance au vrai fichier apps/api)."""

from __future__ import annotations

from pathlib import Path

from lexicon import Lexicon


def _write_lexicon(tmp_path: Path) -> Path:
    path = tmp_path / "lexicon_terms.csv"
    path.write_text(
        "term,kind,status,n_entries,sources\n"
        "amoxicilline,dci,verified,5,bdpm\n"
        "doliprane,brand,official,3,national\n"
        "efferalgan codeine,brand,official,1,national\n"
        "paracetamol,dci,unverified,2,national\n",
        encoding="utf-8",
    )
    return path


def test_exact_match_on_trusted_status(tmp_path: Path) -> None:
    lexicon = Lexicon.load(_write_lexicon(tmp_path))
    match = lexicon.lookup("Amoxicilline")
    assert match.trusted
    assert match.ratio == 1.0
    assert match.status == "verified"


def test_exact_match_on_untrusted_status_is_not_trusted(tmp_path: Path) -> None:
    lexicon = Lexicon.load(_write_lexicon(tmp_path))
    match = lexicon.lookup("Paracetamol")
    assert match.matched_term is not None
    assert not match.trusted
    assert match.status == "unverified"


def test_fuzzy_typo_is_found_but_not_trusted(tmp_path: Path) -> None:
    lexicon = Lexicon.load(_write_lexicon(tmp_path))
    match = lexicon.lookup("Amoxiciline")  # une lettre manquante
    assert match.matched_term == "amoxicilline"
    assert match.ratio >= 0.85
    assert not match.trusted


def test_unrelated_name_has_no_match(tmp_path: Path) -> None:
    lexicon = Lexicon.load(_write_lexicon(tmp_path))
    match = lexicon.lookup("Xylca extend")
    assert match.matched_term is None
    assert not match.trusted


def test_real_world_case_xylca_vs_xykaa_not_in_lexicon(tmp_path: Path) -> None:
    """Reproduit le cas 'accord faux' trouvé dans le banc d'essai réel : un nom qui n'existe
    dans aucune liste de médicaments ne doit jamais être considéré comme sûr."""
    lexicon = Lexicon.load(_write_lexicon(tmp_path))
    assert not lexicon.lookup("Xylca extend").trusted
    assert not lexicon.lookup("Xykaa extend").trusted
