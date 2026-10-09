"""Mesure l'effet du lexique de médicaments sur les résultats déjà enregistrés de read_bench.py.

Ne fait AUCUN appel réseau : relit les réponses déjà obtenues (results/.../<model>/*.json) et
renote avec un rapprochement flou contre le lexique (voir eval/lexicon.py), pour mesurer
(brief, Phase 2 point e) :
- combien d'erreurs non signalées deviennent signalées (sécurité gagnée) ;
- le coût en couverture (combien de lignes correctes passent de "sûr" à "à vérifier").

Usage :
    python eval/apply_lexicon.py --results eval/results/real/read --models qwen/qwen3.8-27b meta/muse-glimmer-30b

Règle appliquée (docs/lexique-medicaments.md section 3) : si le nom lu ne correspond pas
exactement à une entrée "official" (marque) ou "verified" (DCI) du lexique, toute la ligne est
rétrogradée à "to_check" avant notation, quel que soit le `legible` déclaré par le modèle.
Bibliothèque standard uniquement.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import read_bench as rb
from lexicon import Lexicon, LexiconMatch

JsonObj = dict[str, object]


def apply_lexicon_downgrade(read: list[JsonObj], lexicon: Lexicon) -> tuple[list[JsonObj], list[LexiconMatch]]:
    """Retourne une copie de `read` avec `legible` rétrogradé si le nom n'est pas vérifié par le lexique."""
    adjusted: list[JsonObj] = []
    matches: list[LexiconMatch] = []
    for med in read:
        med = dict(med)
        name = med.get("name_read")
        if isinstance(name, str) and name.strip():
            match = lexicon.lookup(name)
            matches.append(match)
            if not match.trusted and str(med.get("legible", "yes")).lower() == "yes":
                med["legible"] = "to_check"
        adjusted.append(med)
    return adjusted, matches


@dataclass
class ModelComparison:
    calls: int = 0
    unflagged_before: int = 0
    unflagged_after: int = 0
    newly_flagged_cases: list[str] = field(default_factory=list)
    confident_correct_before: int = 0
    confident_correct_after: int = 0
    downgraded_but_was_correct: list[str] = field(default_factory=list)  # coût en couverture
    not_in_lexicon_at_all: list[tuple[str, str]] = field(default_factory=list)  # (image, name)


def compare(results_dir: Path, model: str, truths: dict[str, list[JsonObj]], lexicon: Lexicon) -> ModelComparison:
    comparison = ModelComparison()
    model_dir = results_dir / rb.slug(model)
    for path in sorted(model_dir.glob("*.json")):
        record = rb.CallRecord(**json.loads(path.read_text(encoding="utf-8")))
        if not record.ok:
            continue
        read = rb.parse_read(record)
        if read is None:
            continue
        comparison.calls += 1
        truth = truths[record.image]

        score_before = rb.score_run(truth, read)
        comparison.unflagged_before += rb.unflagged_errors(score_before)

        adjusted, matches = apply_lexicon_downgrade(read, lexicon)
        for match in matches:
            if match.matched_term is None:
                comparison.not_in_lexicon_at_all.append((record.image, match.query))
        score_after = rb.score_run(truth, adjusted)
        comparison.unflagged_after += rb.unflagged_errors(score_after)

        for key, result_before in score_before.fields.items():
            result_after = score_after.fields.get(key)
            if result_after is None:
                continue
            if result_before.confident:
                comparison.confident_correct_before += 1 if result_before.status == "correct" else 0
            if result_after.confident:
                comparison.confident_correct_after += 1 if result_after.status == "correct" else 0
            if result_before.confident and not result_after.confident and result_before.status == "correct":
                idx, field_name = key
                comparison.downgraded_but_was_correct.append(f"{record.image} med#{idx} {field_name}")
            if result_before.status == "wrong" and result_before.confident and (not result_after.confident):
                idx, field_name = key
                comparison.newly_flagged_cases.append(f"{record.image} med#{idx} {field_name}")

        before_invented = score_before.invented_confident
        after_invented = score_after.invented_confident
        if before_invented and not after_invented:
            comparison.newly_flagged_cases.append(f"{record.image} (médicament inventé, maintenant signalé)")
    return comparison


def render_report(results: dict[str, ModelComparison], lexicon_size: int) -> str:
    lines = [
        "# Effet du lexique de médicaments sur les erreurs non signalées",
        "",
        f"Lexique : {lexicon_size} termes (apps/api/app/data/lexicon/lexicon_terms.csv).",
        "Aucun nouvel appel réseau : renotation des réponses déjà enregistrées.",
        "",
        "| Modèle | Appels | Erreurs non signalées avant | après | Lignes gagnées (sécurité) "
        "| Lignes rétrogradées à tort (coût couverture) | Noms absents du lexique |",
        "|---|---|---|---|---|---|---|",
    ]
    for model, comp in results.items():
        lines.append(
            f"| {model} | {comp.calls} | {comp.unflagged_before} | {comp.unflagged_after} "
            f"| {len(comp.newly_flagged_cases)} | {len(comp.downgraded_but_was_correct)} "
            f"| {len(comp.not_in_lexicon_at_all)} |"
        )
    for model, comp in results.items():
        lines += ["", f"## {model}"]
        if comp.newly_flagged_cases:
            lines += ["", "Erreurs désormais signalées (sécurité gagnée) :"]
            lines += [f"- {c}" for c in comp.newly_flagged_cases]
        if comp.downgraded_but_was_correct:
            lines += ["", "Lignes correctes rétrogradées à tort (coût en couverture) :"]
            lines += [f"- {c}" for c in comp.downgraded_but_was_correct]
        if comp.not_in_lexicon_at_all:
            lines += ["", "Noms lus sans aucun rapprochement dans le lexique (échantillon) :"]
            seen: set[str] = set()
            for image, name in comp.not_in_lexicon_at_all:
                if name in seen:
                    continue
                seen.add(name)
                lines.append(f"- {image}: `{name}`")
                if len(seen) >= 30:
                    lines.append("- ...")
                    break
    lines.append("")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True, help="Dossier results/.../read (sorties de read_bench.py)")
    parser.add_argument("--ordonnances", type=Path, default=Path("ordonnances"))
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--lexicon", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="Fichier de sortie (défaut : stdout seulement)")
    args = parser.parse_args(argv)

    lexicon = Lexicon.load(args.lexicon) if args.lexicon else Lexicon.load()

    images = sorted(p for p in args.ordonnances.iterdir() if p.suffix.lower() in rb.IMAGE_SUFFIXES)
    truths = {p.name: rb.load_truth(p) for p in images}

    results = {model: compare(args.results, model, truths, lexicon) for model in args.models}
    report = render_report(results, len(lexicon))
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    try:
        sys.stdout.write(report)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        sys.stdout.write(report.encode(encoding, errors="replace").decode(encoding))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
