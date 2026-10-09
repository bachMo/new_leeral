"""Banc d'essai de traduction (fr/en <-> wolof/pulaar) avec des modèles servis par OpenRouter.

Contexte : décisions ouvertes D2/D3 de docs/roadmap-technique.md (existe-t-il une traduction
wolof/pulaar <-> français/anglais ? quel pivot ?). Ce script compare plusieurs modèles de langue
généralistes (aucun traducteur spécialisé wolof/pulaar n'est disponible sur OpenRouter au moment
de l'écriture) sur les deux dimensions qui comptent pour Leeral : la qualité de traduction
(chrF, mesure de référence pour les langues à faibles ressources, voir Popović 2015 et le papier
NLLB) et le coût/la vitesse réels.

LIMITE IMPORTANTE À LIRE AVANT D'INTERPRÉTER LES RÉSULTATS : la source de données (FLORES-200,
Meta/NLLB Team) n'a PAS de code dédié pour le pulaar sénégalais (Fouta Toro). La colonne "ff"
utilise `fuv_Latn` (Fulfulde du Nigéria), une variété proche mais distincte. Les scores sur "ff"
mesurent donc une capacité de traduction en fulfulde/peul en général, pas spécifiquement le
pulaar sénégalais : à confirmer avec un locuteur natif avant toute décision définitive (voir
docs/etude-traduction.md, section Limites).

Usage (clé dans une variable d'environnement, jamais dans un fichier) :
    export OPENROUTER_API_KEY=...        # Windows PowerShell : $env:OPENROUTER_API_KEY="..."
    python eval/translate_bench.py --data eval/translations/sample_20.json \
        --out eval/results/translation_essai1 \
        --models google/gemini-3.1-pro-preview google/gemini-2.5-flash-lite \
                 openai/gpt-5-mini anthropic/claude-haiku-4.5 qwen/qwen3.8-27b

Chaque phrase a un identifiant stable (`id` dans le fichier source). Les réponses brutes sont
enregistrées : relancer la commande ne facture pas deux fois un appel déjà réussi.

`report.md` ne reflète QUE les modèles passés à `--models` lors de CET appel (comme
read_bench.py). Pour un rapport fusionnant plusieurs lancements faits séparément (ex. un modèle
ajouté après coup), relancer une dernière fois avec la liste complète de `--models` : les
réponses déjà en cache ne sont pas refacturées, seul le rapport est régénéré.
Bibliothèque standard uniquement.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

logger = logging.getLogger("leeral.bench")

JsonObj = dict[str, object]

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODELS = (
    "google/gemini-3.1-pro-preview",
    "google/gemini-2.5-flash-lite",
    "openai/gpt-5-mini",
    "anthropic/claude-haiku-4.5",
    "anthropic/claude-sonnet-5.5",  # référence connue (retour d'expérience wolof/français réel)
    "qwen/qwen3.8-27b",
)
DEFAULT_MAX_COST = 5.0  # dollars ; voir read_bench.py pour le même principe de budget
PIVOTS = ("fr", "en")
TARGETS = ("wo", "ff")
# Les 8 sens utiles au produit : pivot -> langue cible (explication) et langue cible -> pivot
# (dialogue libre, voir architecture.md section 3.2).
DIRECTIONS: tuple[tuple[str, str], ...] = tuple(
    pair for pivot, target in product(PIVOTS, TARGETS) for pair in ((pivot, target), (target, pivot))
)
LANG_NAMES = {"fr": "French", "en": "English", "wo": "Wolof", "ff": "Fulfulde (Pular/Fula)"}
# Volontairement large : certains modèles (ex. google/gemini-3.1-pro-preview) consomment une
# grande partie du budget en raisonnement caché même à --reasoning-effort minimal, avant la
# réponse. Un budget trop court tronque la traduction en plein milieu (vu empiriquement le
# 5 octobre 2026 : 396/400 tokens consommés, contenu coupé après quelques mots) sans jamais
# remonter d'erreur — seul `reasoning_tokens` dans le rapport le révèle.
MAX_TOKENS = 1500


def build_prompt(text: str, source: str, target: str) -> str:
    return (
        f"Translate the following text from {LANG_NAMES[source]} to {LANG_NAMES[target]}. "
        "Output ONLY the translation. No explanation, no quotes, no notes.\n\n"
        f"Text:\n{text}"
    )


# --------------------------------------------------------------------------- chrF (qualité)


def _char_ngrams(text: str, n: int) -> Counter[tuple[str, ...]]:
    chars = [c for c in text if not c.isspace()]
    if len(chars) < n:
        return Counter()
    return Counter(tuple(chars[i : i + n]) for i in range(len(chars) - n + 1))


def chrf(hypothesis: str, reference: str, max_n: int = 6, beta: float = 2.0) -> float:
    """chrF (Popović 2015) : F-score de n-grammes de caractères, sans tokenisation.

    Choisi plutôt que BLEU parce qu'il ne dépend d'aucun segmenteur de mots : adapté au wolof
    et au pulaar, pour lesquels aucun tokeniseur fiable n'est disponible. C'est aussi la mesure
    utilisée par l'équipe NLLB pour évaluer FLORES-200 (voir leur papier, section évaluation).
    """
    if not hypothesis.strip() or not reference.strip():
        return 0.0
    order_scores: list[float] = []
    for n in range(1, max_n + 1):
        hyp_grams = _char_ngrams(hypothesis, n)
        ref_grams = _char_ngrams(reference, n)
        if not hyp_grams or not ref_grams:
            continue
        overlap = sum((hyp_grams & ref_grams).values())
        precision = overlap / sum(hyp_grams.values())
        recall = overlap / sum(ref_grams.values())
        if precision + recall == 0:
            order_scores.append(0.0)
            continue
        f_beta = (1 + beta**2) * precision * recall / (beta**2 * precision + recall)
        order_scores.append(f_beta)
    return (sum(order_scores) / len(order_scores) * 100) if order_scores else 0.0


# --------------------------------------------------------------------------- appels API


@dataclass
class CallRecord:
    model: str
    direction: str  # "fr-wo"
    sentence_id: int
    run: int
    ok: bool
    error: str | None = None
    content: str | None = None
    provider: str | None = None
    latency_s: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cost: float = 0.0


def as_dict(value: object) -> JsonObj:
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def norm_int(value: object) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return 0


def build_payload(model: str, text: str, source: str, target: str, provider: str | None, reasoning_effort: str) -> JsonObj:
    routing: JsonObj = {"data_collection": "deny"}
    if provider:
        routing["order"] = [provider]
        routing["allow_fallbacks"] = False
    return {
        "model": model,
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": build_prompt(text, source, target)}],
        "provider": routing,
        "reasoning": {"effort": reasoning_effort},
    }


def post_json(base_url: str, api_key: str, payload: JsonObj, timeout: float) -> tuple[int, JsonObj]:
    request = urllib.request.Request(  # noqa: S310
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return int(response.status), as_dict(json.loads(response.read()))
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            return error.code, as_dict(json.loads(raw))
        except json.JSONDecodeError:
            return error.code, {"error": raw[:500]}
    except (urllib.error.URLError, TimeoutError) as error:
        return 0, {"error": str(error)}


def call_model(
    base_url: str,
    api_key: str,
    model: str,
    text: str,
    source: str,
    target: str,
    sentence_id: int,
    run: int,
    provider: str | None,
    reasoning_effort: str,
    timeout: float = 60.0,
) -> CallRecord:
    direction = f"{source}-{target}"
    payload = build_payload(model, text, source, target, provider, reasoning_effort)
    record = CallRecord(model=model, direction=direction, sentence_id=sentence_id, run=run, ok=False)
    for attempt in range(3):
        started = time.monotonic()
        status, body = post_json(base_url, api_key, payload, timeout)
        record.latency_s = round(time.monotonic() - started, 2)
        if status == 200 and "choices" in body:
            break
        error = as_dict(body.get("error"))
        record.error = f"HTTP {status}: {error.get('message') or body.get('error') or body}"[:400]
        if status in (0, 429) or status >= 500:
            time.sleep(2.0 * (attempt + 1))
            continue
        return record
    else:
        return record
    message = as_dict(as_dict(as_list(body.get("choices"))[0]).get("message"))
    content = message.get("content")
    usage = as_dict(body.get("usage"))
    record.ok = isinstance(content, str) and bool(content.strip())
    record.error = None if record.ok else "Réponse vide"
    record.content = content.strip() if isinstance(content, str) else None
    record.provider = str(body["provider"]) if body.get("provider") else None
    record.prompt_tokens = norm_int(usage.get("prompt_tokens"))
    record.completion_tokens = norm_int(usage.get("completion_tokens"))
    details = as_dict(usage.get("completion_tokens_details"))
    record.reasoning_tokens = norm_int(details.get("reasoning_tokens"))
    cost = usage.get("cost")
    record.cost = float(cost) if isinstance(cost, int | float) else 0.0
    return record


# --------------------------------------------------------------------------- orchestration


def slug(model: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "_", model.lower())


@dataclass
class Item:
    sentence_id: int
    texts: dict[str, str]  # {"fr": ..., "en": ..., "wo": ..., "ff": ...}


def load_items(path: Path) -> list[Item]:
    data = as_dict(json.loads(path.read_text("utf-8")))
    items = []
    for raw in as_list(data.get("items")):
        row = as_dict(raw)
        items.append(
            Item(
                sentence_id=norm_int(row.get("id")),
                texts={lang: str(row.get(lang, "")) for lang in ("fr", "en", "wo", "ff")},
            )
        )
    return items


def run_calls(
    items: list[Item],
    directions: Sequence[tuple[str, str]],
    models: Sequence[str],
    runs: int,
    out_dir: Path,
    base_url: str,
    api_key: str,
    provider: str | None,
    reasoning_effort: str,
    max_cost: float | None,
) -> tuple[list[CallRecord], bool]:
    """Exécute les appels manquants. S'arrête et renvoie `budget_exceeded = True` si `max_cost` est atteint.

    Seul le coût des appels effectivement facturés dans CETTE exécution compte vers `max_cost` :
    un appel déjà en cache (reprise) est gratuit et ne consomme pas le budget.
    """
    records: list[CallRecord] = []
    spent = 0.0
    budget_exceeded = False
    combos = [
        (item, source, target, run, model)
        for item in items
        for source, target in directions
        for run in range(runs)
        for model in models
    ]
    for item, source, target, run, model in combos:
        if max_cost is not None and spent >= max_cost:
            budget_exceeded = True
            logger.warning("Budget --max-cost=%.4f atteint (dépensé %.4f) : arrêt.", max_cost, spent)
            break
        direction = f"{source}-{target}"
        target_dir = out_dir / slug(model) / direction
        target_file = target_dir / f"id{item.sentence_id}.run{run}.json"
        if target_file.exists():
            cached = CallRecord(**json.loads(target_file.read_text("utf-8")))
            if cached.ok:
                records.append(cached)
                continue
        record = call_model(
            base_url,
            api_key,
            model,
            item.texts[source],
            source,
            target,
            item.sentence_id,
            run,
            provider,
            reasoning_effort,
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file.write_text(json.dumps(asdict(record), ensure_ascii=False, indent=1), "utf-8")
        level = logging.INFO if record.ok else logging.WARNING
        logger.log(level, "%s %s id%d run%d : %s", model, direction, item.sentence_id, run, record.error or "ok")
        records.append(record)
        spent += record.cost
        time.sleep(0.2)
    return records, budget_exceeded


@dataclass
class DirectionStats:
    calls: int = 0
    failed: int = 0
    truncated: int = 0  # completion_tokens proche de MAX_TOKENS : réponse probablement coupée
    chrf_scores: list[float] = field(default_factory=list)
    latencies: list[float] = field(default_factory=list)
    tokens: list[int] = field(default_factory=list)
    reasoning_tokens: int = 0
    cost: float = 0.0


@dataclass
class ModelStats:
    by_direction: dict[str, DirectionStats] = field(default_factory=lambda: defaultdict(DirectionStats))
    providers: Counter[str] = field(default_factory=Counter)

    @property
    def total_cost(self) -> float:
        return sum(d.cost for d in self.by_direction.values())


def analyse(records: list[CallRecord], items_by_id: dict[int, Item]) -> dict[str, ModelStats]:
    stats: dict[str, ModelStats] = defaultdict(ModelStats)
    for record in records:
        st = stats[record.model]
        dst = st.by_direction[record.direction]
        dst.calls += 1
        dst.cost += record.cost
        dst.reasoning_tokens += record.reasoning_tokens
        if record.completion_tokens >= int(MAX_TOKENS * 0.9):
            dst.truncated += 1
        if record.provider:
            st.providers[record.provider] += 1
        if not record.ok or not record.content:
            dst.failed += 1
            continue
        dst.latencies.append(record.latency_s)
        dst.tokens.append(record.prompt_tokens + record.completion_tokens)
        _, target = record.direction.split("-")
        reference = items_by_id[record.sentence_id].texts[target]
        dst.chrf_scores.append(chrf(record.content, reference))
    return dict(stats)


def pct(part: int, total: int) -> str:
    return f"{part / total:.0%}" if total else "n/a"


def mean(values: Sequence[float]) -> float | None:
    return statistics.mean(values) if values else None


def render_report(
    stats: dict[str, ModelStats],
    models: Sequence[str],
    directions: Sequence[tuple[str, str]],
    n_items: int,
    runs: int,
    budget_exceeded: bool,
    max_cost: float | None,
) -> str:
    lines = [
        "# Banc d'essai de traduction : rapport",
        "",
        f"- Date : {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- Phrases : {n_items} ; lancements par phrase/sens/modèle : {runs}",
        "- Mesure de qualité : chrF (n-grammes de caractères 1 à 6, beta=2), 0 à 100, plus haut = meilleur",
        "- **ff = Fulfulde du Nigéria (FLORES-200), proxy du pulaar sénégalais : voir la limite "
        "en tête de fichier avant toute conclusion définitive sur le pulaar.**",
    ]
    if budget_exceeded:
        lines.append(
            f"- **ARRET ANTICIPE** : le budget --max-cost={max_cost} dollar(s) a été atteint. "
            "Les chiffres ci-dessous ne portent que sur les appels effectués."
        )
    truncated_models = sorted(
        {model for model in models for d in stats.get(model, ModelStats()).by_direction.values() if d.truncated}
    )
    if truncated_models:
        lines.append(
            "- **ATTENTION, réponses probablement tronquées** (complétion proche de "
            f"MAX_TOKENS={MAX_TOKENS}, voir colonne « Tronqués ») pour : "
            f"{', '.join(truncated_models)}. Leur chrF est sous-estimé et ne doit pas être "
            "comparé aux autres tant que ce n'est pas corrigé (augmenter --max-tokens n'existe "
            "pas encore en CLI ; modifier MAX_TOKENS dans le script)."
        )
    lines += [
        "",
        "## Par modèle et par sens",
        "",
        "| Modèle | Sens | Appels | Échecs | Tronqués | chrF moyen | Latence moy. | Tokens moy. "
        "| Raisonnement (tokens) | Coût |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for model in models:
        st = stats.get(model, ModelStats())
        for source, target in directions:
            direction = f"{source}-{target}"
            d = st.by_direction.get(direction, DirectionStats())
            total = d.calls
            latency = mean(d.latencies)
            tokens = mean([float(t) for t in d.tokens])
            score = mean(d.chrf_scores)
            lines.append(
                f"| {model} | {direction} | {total} | {d.failed} | {d.truncated or ''} "
                f"| {f'{score:.1f}' if score is not None else 'n/a'} "
                f"| {f'{latency:.1f} s' if latency is not None else 'n/a'} "
                f"| {f'{tokens:.0f}' if tokens is not None else 'n/a'} "
                f"| {d.reasoning_tokens} | {d.cost:.4f} $ |"
            )
    lines += [
        "",
        "## Synthèse par modèle (toutes les phrases et tous les sens confondus)",
        "",
        "| Modèle | chrF moyen global | Latence moy. | Coût total | Fournisseurs servis |",
        "|---|---|---|---|---|",
    ]
    for model in models:
        st = stats.get(model, ModelStats())
        all_scores = [s for d in st.by_direction.values() for s in d.chrf_scores]
        all_latencies = [lat for d in st.by_direction.values() for lat in d.latencies]
        score = mean(all_scores)
        latency = mean(all_latencies)
        lines.append(
            f"| {model} | {f'{score:.1f}' if score is not None else 'n/a'} "
            f"| {f'{latency:.1f} s' if latency is not None else 'n/a'} "
            f"| {st.total_cost:.4f} $ | {dict(st.providers) or 'inconnu'} |"
        )
    lines += [
        "",
        "## Recommandation par paire de langues (moyenne des deux sens)",
        "",
        "| Paire | Meilleur chrF | Modèle | Moins cher à chrF comparable | Modèle |",
        "|---|---|---|---|---|",
    ]
    pivots_targets = [(p, t) for p in PIVOTS for t in TARGETS]
    for pivot, target in pivots_targets:
        pair_label = f"{pivot}<->{target}"
        ranked: list[tuple[str, float, float]] = []  # model, score, cost
        for model in models:
            st = stats.get(model, ModelStats())
            scores = st.by_direction.get(f"{pivot}-{target}", DirectionStats()).chrf_scores
            scores += st.by_direction.get(f"{target}-{pivot}", DirectionStats()).chrf_scores
            if not scores:
                continue
            ranked.append((model, statistics.mean(scores), st.total_cost))
        if not ranked:
            lines.append(f"| {pair_label} | n/a | - | - | - |")
            continue
        best = max(ranked, key=lambda r: r[1])
        cheapest_close = min((r for r in ranked if r[1] >= best[1] - 3.0), key=lambda r: r[2], default=best)
        lines.append(f"| {pair_label} | {best[1]:.1f} | {best[0]} | {cheapest_close[1]:.1f} | {cheapest_close[0]} |")
    lines += [
        "",
        "Rappel : 50 phrases par sens donne une tendance, pas une garantie. « Moins cher à chrF "
        "comparable » = le moins cher parmi les modèles à moins de 3 points chrF du meilleur.",
    ]
    return "\n".join(lines) + "\n"


def print_report(report: str) -> None:
    """Affiche le rapport sans planter si la console (ex. cp1252 sur Windows) ne gère pas un caractère."""
    encoding = sys.stdout.encoding or "utf-8"
    try:
        sys.stdout.write(report)
    except UnicodeEncodeError:
        sys.stdout.write(report.encode(encoding, errors="replace").decode(encoding))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Banc d'essai de traduction fr/en <-> wolof/pulaar (OpenRouter).")
    parser.add_argument("--data", type=Path, required=True, help="Fichier JSON de phrases (voir translations/)")
    parser.add_argument("--out", type=Path, required=True, help="Dossier des résultats (le relancer reprend)")
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument(
        "--directions",
        nargs="+",
        default=None,
        help="Sens à tester, ex. fr-wo wo-fr (défaut : les 8 sens fr/en <-> wo/ff)",
    )
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--provider", default=None, help="Slug du fournisseur OpenRouter à figer, ex. deepinfra")
    parser.add_argument("--base-url", default=os.environ.get("OPENROUTER_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument(
        "--max-cost",
        type=float,
        default=DEFAULT_MAX_COST,
        help=f"Budget maximal en dollars pour cette exécution (défaut : {DEFAULT_MAX_COST}).",
    )
    parser.add_argument("--reasoning-effort", default="none", choices=["none", "minimal", "low", "medium", "high"])
    parser.add_argument("--dry-run", action="store_true", help="Compter les appels sans les faire")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    items = load_items(args.data)
    if not items:
        logger.error("Aucune phrase dans %s", args.data)
        return 2
    items_by_id = {item.sentence_id: item for item in items}
    directions = [(d.split("-")[0], d.split("-")[1]) for d in args.directions] if args.directions else list(DIRECTIONS)

    n_calls = len(items) * len(directions) * args.runs * len(args.models)
    logger.info(
        "%d phrases x %d sens x %d lancements x %d modèles = %d appels",
        len(items),
        len(directions),
        args.runs,
        len(args.models),
        n_calls,
    )
    if args.dry_run:
        return 0
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        logger.error("Variable d'environnement OPENROUTER_API_KEY absente.")
        return 2

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    records, budget_exceeded = run_calls(
        items,
        directions,
        args.models,
        args.runs,
        out_dir,
        args.base_url,
        api_key,
        args.provider,
        args.reasoning_effort,
        args.max_cost,
    )
    stats = analyse(records, items_by_id)
    report = render_report(stats, args.models, directions, len(items), args.runs, budget_exceeded, args.max_cost)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    print_report(report)
    logger.info("Rapport : %s", out_dir / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
