"""Tests de la renotation avec lexique (aucun appel réseau, rejoue des réponses déjà enregistrées)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import apply_lexicon as al
import read_bench as rb
from lexicon import Lexicon, LexiconMatch


def _lexicon(tmp_path: Path) -> Lexicon:
    path = tmp_path / "lexicon_terms.csv"
    path.write_text(
        "term,kind,status,n_entries,sources\namoxicilline,dci,verified,1,bdpm\n",
        encoding="utf-8",
    )
    return Lexicon.load(path)


def test_apply_lexicon_downgrade_untrusted_name() -> None:
    read = [{"name_read": "Xylca extend", "legible": "yes", "times_per_day": 3}]

    class FakeLexicon:
        def lookup(self, name: str) -> LexiconMatch:
            return LexiconMatch(query=name, matched_term=None, status=None, ratio=0.0, trusted=False)

    adjusted, matches = al.apply_lexicon_downgrade(read, FakeLexicon())  # type: ignore[arg-type]
    assert adjusted[0]["legible"] == "to_check"
    assert len(matches) == 1


def test_apply_lexicon_keeps_trusted_name(tmp_path: Path) -> None:
    lexicon = _lexicon(tmp_path)
    read: list[al.JsonObj] = [{"name_read": "Amoxicilline", "legible": "yes"}]
    adjusted, matches = al.apply_lexicon_downgrade(read, lexicon)
    assert adjusted[0]["legible"] == "yes"
    assert matches[0].trusted


def test_compare_reduces_unflagged_errors_for_untrusted_name(tmp_path: Path) -> None:
    lexicon = _lexicon(tmp_path)
    truth: list[al.JsonObj] = [{"name": "Amoxicilline", "strength": "500 mg"}]
    read = {
        "document_language": "fr",
        "medications": [{"name_read": "Amoxiciline forte", "strength": "500 mg", "legible": "yes"}],
    }
    record = rb.CallRecord(
        model="m/x",
        image="ord_01.jpg",
        run=0,
        ok=True,
        content=json.dumps(read),
    )
    results_dir = tmp_path / "results"
    model_dir = results_dir / rb.slug("m/x")
    model_dir.mkdir(parents=True)
    (model_dir / "ord_01.run0.json").write_text(json.dumps(asdict(record)), encoding="utf-8")

    comparison = al.compare(results_dir, "m/x", {"ord_01.jpg": truth}, lexicon)
    assert comparison.calls == 1
    assert comparison.unflagged_before == 1  # "Amoxiciline forte" != "Amoxicilline", déclaré sûr
    assert comparison.unflagged_after == 0  # rétrogradé car absent du lexique (exact), devient to_check
    assert comparison.newly_flagged_cases  # au moins un cas listé
