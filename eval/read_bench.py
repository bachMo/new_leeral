"""Banc d'essai de lecture d'ordonnances avec des modèles servis par OpenRouter.

Pour chaque photo et chaque modèle, le script demande une lecture structurée (JSON), la compare à
la vérité terrain, et mesure ce qui compte pour Leeral :
- les erreurs NON signalées (valeur fausse alors que le modèle dit "legible = yes") ;
- l'exactitude par champ (nom, dosage, prises par jour, durée) ;
- la stabilité entre plusieurs lancements ;
- pour une paire de modèles : accord correct, accord faux (la double lecture ne voit rien), désaccord.

Usage (clé dans une variable d'environnement, jamais dans un fichier) :
    export OPENROUTER_API_KEY=...        # Windows PowerShell : $env:OPENROUTER_API_KEY="..."
    python eval/read_bench.py --images eval/ordonnances --out eval/results/essai1 --runs 3 \
        --provider deepinfra --models qwen/qwen3.8-27b meta/muse-glimmer-30b

Chaque photo `ord_01.jpg` a une vérité terrain `ord_01.truth.json`. Les réponses brutes sont
enregistrées : relancer la commande ne facture pas deux fois un appel déjà réussi.
Utiliser UNIQUEMENT des ordonnances fictives ou anonymisées avec accord.
Bibliothèque standard uniquement.
"""

from __future__ import annotations

import argparse
import base64
import difflib
import json
import logging
import mimetypes
import os
import re
import statistics
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger("leeral.bench")

JsonObj = dict[str, object]
Key = tuple[int, str]  # (indice du médicament dans la vérité terrain, champ)

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODELS = ("qwen/qwen3.8-27b", "meta/muse-glimmer-30b")
DEFAULT_MAX_COST = 10.0  # dollars, voir PARTIE A5 du brief : budget par défaut sauf indication contraire
FIELDS = ("name", "strength", "times_per_day", "duration_days")
MAX_TOKENS = 1500
MAX_IMAGE_BYTES = 8_000_000
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

PROMPT = """Tu lis la photo d'une ordonnance médicale. Réponds uniquement par un objet JSON valide, \
sans aucun texte autour.

Règles :
- Ne devine jamais. Si un nom, un dosage, un nombre de prises ou une durée est illisible ou \
incertain, mets null pour ce champ et indique "legible": "partial" ou "no".
- Ne corrige pas un nom de médicament : écris exactement ce que tu lis.
- Ne complète jamais une posologie absente de l'ordonnance.
- "times_per_day" est un entier (prises par jour). "duration_days" est un entier (jours).
- "strength" est le dosage lu avec son unité, par exemple "500 mg".
- "legible": "yes" seulement si TOUTE la ligne est lisible sans aucun doute.

Format exact :
{"document_language": "fr|en|mixed|unknown",
 "medications": [{"raw": "ligne telle que lue", "name_read": "...", "strength": "...",
 "times_per_day": 3, "duration_days": 7, "timing": "...", "legible": "yes|partial|no"}]}"""


# --------------------------------------------------------------------------- normalisation


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def fold(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", strip_accents(text)).split())


def norm_strength(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    compact = re.sub(r"\s+", "", strip_accents(str(value)).replace(",", "."))
    return re.sub(r"[^a-z0-9./%]", "", compact)


def norm_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def norm_field(name: str, value: object) -> str | int | None:
    if name == "name":
        text = fold(str(value)) if value not in (None, "") else ""
        return text or None
    if name == "strength":
        return norm_strength(value)
    return norm_int(value)


def as_dict(value: object) -> JsonObj:
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def extract_json(text: str) -> JsonObj | None:
    """Extrait le premier objet JSON d'une réponse (tolère les blocs de code Markdown)."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    for candidate in (cleaned, cleaned[cleaned.find("{") : cleaned.rfind("}") + 1]):
        try:
            parsed: object = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return as_dict(parsed)
    return None


# --------------------------------------------------------------------------- notation


@dataclass
class FieldResult:
    value: str | int | None
    status: str  # "correct" | "wrong" | "abstain"
    confident: bool


@dataclass
class RunScore:
    fields: dict[Key, FieldResult] = field(default_factory=dict)
    omitted: int = 0  # médicaments de la vérité terrain absents de la lecture
    invented_confident: int = 0  # médicaments lus mais absents de la vérité, déclarés lisibles


def _med_name(med: JsonObj) -> str:
    return fold(str(med.get("name_read") or med.get("name") or med.get("raw") or ""))


def match_meds(truth: list[JsonObj], read: list[JsonObj]) -> tuple[dict[int, int], set[int]]:
    """Associe chaque médicament de la vérité à la lecture la plus proche (ratio >= 0,6)."""
    pairs: dict[int, int] = {}
    used: set[int] = set()
    for t_index, t_med in enumerate(truth):
        best, best_ratio = -1, 0.6
        for r_index, r_med in enumerate(read):
            if r_index in used:
                continue
            ratio = difflib.SequenceMatcher(None, _med_name(t_med), _med_name(r_med)).ratio()
            if ratio >= best_ratio:
                best, best_ratio = r_index, ratio
        if best >= 0:
            pairs[t_index] = best
            used.add(best)
    return pairs, used


def score_run(truth: list[JsonObj], read: list[JsonObj]) -> RunScore:
    score = RunScore()
    pairs, used = match_meds(truth, read)
    for t_index, t_med in enumerate(truth):
        r_med = read[pairs[t_index]] if t_index in pairs else None
        if r_med is None:
            score.omitted += 1
        confident = r_med is not None and str(r_med.get("legible", "yes")).lower() == "yes"
        for name in FIELDS:
            expected = norm_field(name, t_med.get(name))
            if expected is None:
                continue  # champ non renseigné dans la vérité : non évalué
            source_key = "name_read" if name == "name" else name
            got = norm_field(name, r_med.get(source_key) if r_med else None)
            status = "abstain" if got is None else ("correct" if got == expected else "wrong")
            score.fields[(t_index, name)] = FieldResult(got, status, confident)
    for r_index, r_med in enumerate(read):
        if r_index not in used and str(r_med.get("legible", "yes")).lower() == "yes":
            score.invented_confident += 1
    return score


def unflagged_errors(score: RunScore) -> int:
    wrong = sum(1 for f in score.fields.values() if f.status == "wrong" and f.confident)
    return wrong + score.invented_confident


# --------------------------------------------------------------------------- appels API


@dataclass
class CallRecord:
    model: str
    image: str
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


def build_payload(
    model: str,
    image: Path,
    provider: str | None,
    thinking: bool,
    allow_collection: bool = False,
    reasoning_effort: str = "none",
) -> JsonObj:
    if image.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError(f"{image.name} dépasse {MAX_IMAGE_BYTES // 1_000_000} Mo : réduire l'image")
    mime = mimetypes.guess_type(image.name)[0] or "image/jpeg"
    data = base64.b64encode(image.read_bytes()).decode("ascii")
    routing: JsonObj = {"data_collection": "allow" if allow_collection else "deny"}
    if provider:
        routing["order"] = [provider]
        routing["allow_fallbacks"] = False
    payload: JsonObj = {
        "model": model,
        "temperature": 0,
        "max_tokens": MAX_TOKENS,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                ],
            }
        ],
        "provider": routing,
    }
    if not thinking:
        # "none" désactive complètement le raisonnement sur la plupart des modèles, mais certains
        # (ex. meta/muse-glimmer-30b, vérifié le 4 octobre 2026 : "Reasoning is mandatory for this
        # endpoint and cannot be disabled") l'exigent toujours : utiliser --reasoning-effort minimal
        # pour ceux-là plutôt que de les exclure.
        payload["reasoning"] = {"effort": reasoning_effort}
    return payload


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
    image: Path,
    run: int,
    provider: str | None,
    thinking: bool,
    allow_collection: bool = False,
    timeout: float = 120.0,
    reasoning_effort: str = "none",
) -> CallRecord:
    payload = build_payload(model, image, provider, thinking, allow_collection, reasoning_effort)
    record = CallRecord(model=model, image=image.name, run=run, ok=False)
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
    details = as_dict(usage.get("completion_tokens_details"))
    record.ok = isinstance(content, str) and bool(content.strip())
    record.error = None if record.ok else "Réponse vide"
    record.content = content if isinstance(content, str) else None
    record.provider = str(body["provider"]) if body.get("provider") else None
    record.prompt_tokens = norm_int(usage.get("prompt_tokens")) or 0
    record.completion_tokens = norm_int(usage.get("completion_tokens")) or 0
    record.reasoning_tokens = norm_int(details.get("reasoning_tokens")) or 0
    cost = usage.get("cost")
    record.cost = float(cost) if isinstance(cost, int | float) else 0.0
    return record


# --------------------------------------------------------------------------- orchestration


def slug(model: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "_", model.lower())


def load_truth(image: Path) -> list[JsonObj]:
    path = image.with_suffix("").with_suffix(".truth.json")
    if not path.exists():
        raise FileNotFoundError(f"Vérité terrain manquante : {path.name}")
    return [as_dict(m) for m in as_list(as_dict(json.loads(path.read_text("utf-8"))).get("medications"))]


def run_calls(
    images: list[Path],
    models: Sequence[str],
    runs: int,
    out_dir: Path,
    base_url: str,
    api_key: str,
    provider: str | None,
    thinking: bool,
    allow_collection: bool = False,
    max_cost: float | None = None,
    reasoning_effort: str = "none",
) -> tuple[list[CallRecord], bool]:
    """Exécute les appels manquants. S'arrête et renvoie `budget_exceeded = True` si `max_cost` est atteint.

    Seul le coût des appels effectivement facturés dans CETTE exécution compte vers `max_cost` : un appel
    déjà en cache (reprise) est gratuit et ne consomme pas le budget.
    """
    records: list[CallRecord] = []
    spent = 0.0
    budget_exceeded = False
    combos = [(image, run, model) for image in images for run in range(runs) for model in models]
    for image, run, model in combos:
        if max_cost is not None and spent >= max_cost:
            budget_exceeded = True
            logger.warning("Budget --max-cost=%.4f atteint (dépensé %.4f) : arrêt des appels.", max_cost, spent)
            break
        target = out_dir / slug(model) / f"{image.stem}.run{run}.json"
        if target.exists():
            cached = CallRecord(**json.loads(target.read_text("utf-8")))
            if cached.ok:
                records.append(cached)
                continue
        record = call_model(
            base_url, api_key, model, image, run, provider, thinking, allow_collection, reasoning_effort=reasoning_effort
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(record), ensure_ascii=False, indent=1), "utf-8")
        level = logging.INFO if record.ok else logging.WARNING
        logger.log(level, "%s %s run%d : %s", model, image.name, run, record.error or "ok")
        records.append(record)
        spent += record.cost
        time.sleep(0.2)
    return records, budget_exceeded


def parse_read(record: CallRecord) -> list[JsonObj] | None:
    if not record.ok or not record.content:
        return None
    parsed = extract_json(record.content)
    if parsed is None:
        return None
    return [as_dict(m) for m in as_list(parsed.get("medications"))]


@dataclass
class ModelStats:
    calls: int = 0
    failed: int = 0
    unparsable: int = 0
    counts: Counter[str] = field(default_factory=Counter)
    by_field: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    unflagged: int = 0
    omitted: int = 0
    latencies: list[float] = field(default_factory=list)
    tokens: list[int] = field(default_factory=list)
    reasoning_tokens: int = 0
    cost: float = 0.0
    providers: Counter[str] = field(default_factory=Counter)


def analyse(
    records: list[CallRecord], truths: dict[str, list[JsonObj]]
) -> tuple[dict[str, ModelStats], dict[tuple[str, str, int], RunScore]]:
    stats: dict[str, ModelStats] = defaultdict(ModelStats)
    scores: dict[tuple[str, str, int], RunScore] = {}
    for record in records:
        st = stats[record.model]
        st.calls += 1
        st.cost += record.cost
        st.reasoning_tokens += record.reasoning_tokens
        if record.provider:
            st.providers[record.provider] += 1
        if not record.ok:
            st.failed += 1
            continue
        st.latencies.append(record.latency_s)
        st.tokens.append(record.prompt_tokens + record.completion_tokens)
        read = parse_read(record)
        if read is None:
            st.unparsable += 1
            continue
        score = score_run(truths[record.image], read)
        scores[(record.model, record.image, record.run)] = score
        st.unflagged += unflagged_errors(score)
        st.omitted += score.omitted
        for (_, name), result in score.fields.items():
            st.counts[result.status] += 1
            st.by_field[name][result.status] += 1
    return dict(stats), scores


def stability(scores: dict[tuple[str, str, int], RunScore], model: str) -> float | None:
    values: dict[tuple[str, Key], set[object]] = defaultdict(set)
    for (m, image, _), score in scores.items():
        if m == model:
            for key, result in score.fields.items():
                values[(image, key)].add(result.value)
    runs_seen = {run for (m, _, run) in scores if m == model}
    if len(runs_seen) < 2 or not values:
        return None
    return sum(1 for v in values.values() if len(v) == 1) / len(values)


def pair_analysis(scores: dict[tuple[str, str, int], RunScore], model_a: str, model_b: str) -> Counter[str]:
    result: Counter[str] = Counter()
    for (m, image, run), score_a in scores.items():
        if m != model_a:
            continue
        score_b = scores.get((model_b, image, run))
        if score_b is None:
            continue
        for key, a in score_a.fields.items():
            b = score_b.fields.get(key)
            if b is None:
                continue
            if a.value is not None and a.value == b.value:
                result["accord_correct" if a.status == "correct" else "accord_faux"] += 1
            else:
                result["desaccord"] += 1
    return result


def pct(part: int, total: int) -> str:
    return f"{part / total:.0%}" if total else "n/a"


def render_report(
    stats: dict[str, ModelStats],
    scores: dict[tuple[str, str, int], RunScore],
    models: Sequence[str],
    provider: str | None,
    n_images: int,
    runs: int,
    allow_collection: bool = False,
    budget_exceeded: bool = False,
    max_cost: float | None = None,
) -> str:
    lines = [
        "# Banc d'essai de lecture : rapport",
        "",
        f"- Date : {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- Images : {n_images} ; lancements par image et par modèle : {runs}",
        f"- Fournisseur demandé : {provider or 'automatique (à éviter pour comparer)'}",
        "- Données : "
        + (
            "collecte AUTORISEE (ordonnances fictives uniquement)"
            if allow_collection
            else "aucune collecte autorisée côté fournisseur (`data_collection: deny`)"
        ),
    ]
    if budget_exceeded:
        lines.append(
            f"- **ARRET ANTICIPE** : le budget --max-cost={max_cost} dollar(s) a été atteint avant la fin "
            "des appels prévus. Les chiffres ci-dessous ne portent que sur les appels effectués."
        )
    lines += [
        "",
        "## Par modèle",
        "",
        "| Modèle | Appels | Échecs | JSON invalide | Champs évalués | Corrects | Faux | Abstentions "
        "| **Erreurs non signalées** | Médicaments omis | Stabilité | Latence moy. | Tokens moy. "
        "| Raisonnement (tokens) | Coût total | Fournisseurs servis |",
        "|" + "---|" * 16,
    ]
    for model in models:
        st = stats.get(model, ModelStats())
        total = sum(st.counts.values())
        stable = stability(scores, model)
        lines.append(
            f"| {model} | {st.calls} | {st.failed} | {st.unparsable} | {total} "
            f"| {pct(st.counts['correct'], total)} | {pct(st.counts['wrong'], total)} "
            f"| {pct(st.counts['abstain'], total)} | **{st.unflagged}** | {st.omitted} "
            f"| {f'{stable:.0%}' if stable is not None else 'n/a'} "
            f"| {statistics.mean(st.latencies):.1f} s | {statistics.mean(st.tokens):.0f} "
            f"| {st.reasoning_tokens} | {st.cost:.4f} $ | {dict(st.providers) or 'inconnu'} |"
            if st.latencies
            else f"| {model} | {st.calls} | {st.failed} | - | - | - | - | - | - | - | - | - | - | - | - | - |"
        )
    lines += [
        "",
        "## Exactitude par champ",
        "",
        "| Modèle | Champ | Corrects | Faux | Abstentions |",
        "|---|---|---|---|---|",
    ]
    for model in models:
        st = stats.get(model, ModelStats())
        for name in FIELDS:
            c = st.by_field.get(name, Counter())
            total = sum(c.values())
            lines.append(
                f"| {model} | {name} | {pct(c['correct'], total)} | {pct(c['wrong'], total)} | {pct(c['abstain'], total)} |"
            )
    if len(models) >= 2:
        pair = pair_analysis(scores, models[0], models[1])
        total = sum(pair.values())
        lines += [
            "",
            f"## Double lecture : {models[0]} + {models[1]}",
            "",
            f"- Accord et correct : {pair['accord_correct']} ({pct(pair['accord_correct'], total)})",
            f"- **Accord mais faux** (la double lecture ne voit rien) : {pair['accord_faux']} "
            f"({pct(pair['accord_faux'], total)})",
            f"- Désaccord (détecté, renvoi au pharmacien) : {pair['desaccord']} ({pct(pair['desaccord'], total)})",
            "",
            "Le chiffre critique est l'accord faux, puis les erreurs non signalées de chaque modèle.",
        ]
    lines += ["", "Rappel : un échantillon de quelques ordonnances donne une tendance, pas une garantie."]
    return "\n".join(lines) + "\n"


def print_report(report: str) -> None:
    """Affiche le rapport sans planter si la console (ex. cp1252 sur Windows) ne gère pas un caractère."""
    encoding = sys.stdout.encoding or "utf-8"
    try:
        sys.stdout.write(report)
    except UnicodeEncodeError:
        sys.stdout.write(report.encode(encoding, errors="replace").decode(encoding))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Banc d'essai de lecture d'ordonnances (OpenRouter).")
    parser.add_argument("--images", type=Path, required=True, help="Dossier de photos + *.truth.json")
    parser.add_argument("--out", type=Path, required=True, help="Dossier des résultats (le relancer reprend)")
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--provider", default=None, help="Slug du fournisseur à figer, ex. deepinfra")
    parser.add_argument("--thinking", action="store_true", help="Laisser le raisonnement actif (déconseillé)")
    parser.add_argument("--base-url", default=os.environ.get("OPENROUTER_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument(
        "--allow-collection",
        action="store_true",
        help="Autorise les fournisseurs qui conservent les données : ordonnances FICTIVES uniquement",
    )
    parser.add_argument(
        "--max-cost",
        type=float,
        default=DEFAULT_MAX_COST,
        help=f"Budget maximal en dollars pour cette exécution (défaut : {DEFAULT_MAX_COST}). "
        "Seuls les nouveaux appels facturés comptent ; les appels déjà en cache sont gratuits.",
    )
    parser.add_argument(
        "--reasoning-effort",
        default="none",
        choices=["none", "minimal", "low", "medium", "high"],
        help="Niveau de raisonnement quand --thinking n'est pas passé (défaut : none). Certains modèles "
        "(ex. meta/muse-glimmer-30b) rejettent 'none' avec 'Reasoning is mandatory' : utiliser 'minimal'.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Compter les appels sans les faire")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    images = sorted(p for p in args.images.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        logger.error("Aucune image dans %s", args.images)
        return 2
    try:
        truths = {p.name: load_truth(p) for p in images}
    except FileNotFoundError as error:
        logger.error("%s", error)
        return 2
    n_calls = len(images) * args.runs * len(args.models)
    logger.info(
        "%d images x %d lancements x %d modèles = %d appels",
        len(images),
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
    if not args.provider:
        logger.warning("Aucun --provider : les résultats peuvent varier d'un fournisseur à l'autre.")

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    records, budget_exceeded = run_calls(
        images,
        args.models,
        args.runs,
        out_dir,
        args.base_url,
        api_key,
        args.provider,
        args.thinking,
        args.allow_collection,
        args.max_cost,
        args.reasoning_effort,
    )
    stats, scores = analyse(records, truths)
    report = render_report(
        stats,
        scores,
        args.models,
        args.provider,
        len(images),
        args.runs,
        args.allow_collection,
        budget_exceeded,
        args.max_cost,
    )
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    print_report(report)
    logger.info("Rapport : %s", out_dir / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
