"""Banc d'essai de TRANSCRIPTION (OCR général) avec des modèles servis par OpenRouter.

Complète `read_bench.py` (qui note la lecture structurée des ordonnances) pour les documents qui ne
sont pas des ordonnances : contrat, lettre, facture, certificat... Ici on ne demande pas un JSON de
médicaments mais une transcription fidèle du texte entier, comparée mot à mot à la vérité terrain pour
repérer précisément les erreurs (substitutions, mots omis, mots ajoutés) et les nombres déformés (le
risque le plus grave pour Leeral : téléphone, date, montant, numéro de pièce...).

Usage :
    export OPENROUTER_API_KEY=...
    python eval/transcription_bench.py --images eval/documents --out eval/results/real/transcription \
        --provider deepinfra --models qwen/qwen3.8-27b meta/muse-glimmer-30b \
        --reasoning-effort none minimal --max-cost 1.0

Chaque document `doc_01.jpg` a une vérité terrain `doc_01.truth.txt` (texte brut, pas JSON). Les
réponses brutes sont enregistrées : relancer la commande ne facture pas deux fois un appel réussi.
Utiliser UNIQUEMENT des documents fictifs ou anonymisés avec accord. Ce dossier (`eval/documents/`)
n'est jamais commité (voir .gitignore).
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
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger("leeral.transcription_bench")

JsonObj = dict[str, object]

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MAX_COST = 10.0
MAX_TOKENS = 4000
MAX_IMAGE_BYTES = 8_000_000
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DIGIT_RUN = re.compile(r"\d+")

PROMPT = """Tu lis la photo d'un document administratif ou médical (ordonnance, contrat, lettre, \
facture, certificat...). Transcris FIDELEMENT tout le texte visible, du début à la fin, dans l'ordre \
de lecture naturel.

Règles strictes :
- Ne devine jamais un mot, un chiffre ou un nom que tu ne peux pas lire avec certitude : écris \
[illisible] à sa place plutôt que d'inventer.
- Ne corrige pas l'orthographe, ne reformule pas, ne résume pas : copie exactement ce qui est écrit, \
y compris les fautes et les abréviations.
- Conserve les sauts de ligne visibles sur le document (une ligne du document = une ligne de ta \
réponse).
- Les nombres (téléphone, date, montant, numéro de pièce, dosage...) doivent être transcrits \
caractère par caractère, sans arrondir ni reformater.
- Réponds uniquement par le texte transcrit, sans aucun commentaire ni balise autour."""


def as_dict(value: object) -> JsonObj:
    return {str(k): v for k, v in value.items()} if isinstance(value, dict) else {}


def as_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


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


def clean_transcription(text: str) -> str:
    """Retire un éventuel bloc de code Markdown autour de la transcription."""
    stripped = text.strip()
    stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
    stripped = re.sub(r"\n?```$", "", stripped)
    return stripped.strip("\n")


# --------------------------------------------------------------------------- notation


@dataclass
class DiffStats:
    equal: int = 0
    substituted: int = 0
    deleted: int = 0  # présent dans la vérité, absent de la lecture
    inserted: int = 0  # absent de la vérité, ajouté par la lecture (possible invention)
    substitutions: list[tuple[str, str]] = field(default_factory=list)
    deleted_words: list[str] = field(default_factory=list)
    inserted_words: list[str] = field(default_factory=list)
    digit_mismatches: list[tuple[str, str]] = field(default_factory=list)

    @property
    def truth_word_count(self) -> int:
        return self.equal + self.substituted + self.deleted

    @property
    def word_error_rate(self) -> float | None:
        total = self.truth_word_count
        if total == 0:
            return None
        return (self.substituted + self.deleted + self.inserted) / total


def diff_words(truth: str, read: str) -> DiffStats:
    """Compare mot à mot (espaces comme séparateur, rien d'autre normalisé) pour ne rien manquer."""
    truth_words = truth.split()
    read_words = read.split()
    stats = DiffStats()
    matcher = difflib.SequenceMatcher(None, truth_words, read_words, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            stats.equal += i2 - i1
        elif tag == "replace":
            # difflib peut fusionner une insertion ou une omission adjacente dans le même bloc
            # "replace" (longueurs différentes des deux côtés) : les premiers mots sont appariés en
            # substitutions, le surplus d'un côté est une omission, le surplus de l'autre un ajout.
            pairs = list(zip(truth_words[i1:i2], read_words[j1:j2], strict=False))
            stats.substituted += len(pairs)
            stats.substitutions.extend(pairs)
            extra_truth = truth_words[i1 + len(pairs) : i2]
            extra_read = read_words[j1 + len(pairs) : j2]
            stats.deleted += len(extra_truth)
            stats.deleted_words.extend(extra_truth)
            stats.inserted += len(extra_read)
            stats.inserted_words.extend(extra_read)
        elif tag == "delete":
            stats.deleted += i2 - i1
            stats.deleted_words.extend(truth_words[i1:i2])
        elif tag == "insert":
            stats.inserted += j2 - j1
            stats.inserted_words.extend(read_words[j1:j2])
    for truth_word, read_word in stats.substitutions:
        truth_digits = DIGIT_RUN.findall(truth_word)
        read_digits = DIGIT_RUN.findall(read_word)
        if truth_digits and truth_digits != read_digits:
            stats.digit_mismatches.append((truth_word, read_word))
    for word in stats.deleted_words:
        if DIGIT_RUN.search(word):
            stats.digit_mismatches.append((word, "(absent)"))
    return stats


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
    record.content = clean_transcription(content) if isinstance(content, str) else None
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


def load_truth(image: Path) -> str:
    path = image.with_suffix("").with_suffix(".truth.txt")
    if not path.exists():
        raise FileNotFoundError(f"Vérité terrain manquante : {path.name}")
    return path.read_text(encoding="utf-8")


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
    reasoning_effort_by_model: dict[str, str] | None = None,
) -> tuple[list[CallRecord], bool]:
    """Exécute les appels manquants. S'arrête et renvoie `budget_exceeded = True` si `max_cost` est atteint."""
    reasoning_effort_by_model = reasoning_effort_by_model or {}
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
        effort = reasoning_effort_by_model.get(model, "none")
        record = call_model(
            base_url, api_key, model, image, run, provider, thinking, allow_collection, reasoning_effort=effort
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(record), ensure_ascii=False, indent=1), "utf-8")
        level = logging.INFO if record.ok else logging.WARNING
        logger.log(level, "%s %s run%d : %s", model, image.name, run, record.error or "ok")
        records.append(record)
        spent += record.cost
        time.sleep(0.2)
    return records, budget_exceeded


@dataclass
class ModelStats:
    calls: int = 0
    failed: int = 0
    latencies: list[float] = field(default_factory=list)
    tokens: list[int] = field(default_factory=list)
    reasoning_tokens: int = 0
    cost: float = 0.0
    wers: list[float] = field(default_factory=list)
    total_substituted: int = 0
    total_deleted: int = 0
    total_inserted: int = 0
    digit_mismatches: list[tuple[str, str, str]] = field(default_factory=list)  # (image, truth, read)


def analyse(
    records: list[CallRecord], truths: dict[str, str]
) -> tuple[dict[str, ModelStats], dict[tuple[str, str, int], DiffStats]]:
    stats: dict[str, ModelStats] = {}
    diffs: dict[tuple[str, str, int], DiffStats] = {}
    for record in records:
        st = stats.setdefault(record.model, ModelStats())
        st.calls += 1
        st.cost += record.cost
        st.reasoning_tokens += record.reasoning_tokens
        if not record.ok or not record.content:
            st.failed += 1
            continue
        st.latencies.append(record.latency_s)
        st.tokens.append(record.prompt_tokens + record.completion_tokens)
        stat = diff_words(truths[record.image], record.content)
        diffs[(record.model, record.image, record.run)] = stat
        wer = stat.word_error_rate
        if wer is not None:
            st.wers.append(wer)
        st.total_substituted += stat.substituted
        st.total_deleted += stat.deleted
        st.total_inserted += stat.inserted
        for truth_word, read_word in stat.digit_mismatches:
            st.digit_mismatches.append((record.image, truth_word, read_word))
    return stats, diffs


def pct(value: float) -> str:
    return f"{value:.1%}"


def render_report(
    stats: dict[str, ModelStats],
    diffs: dict[tuple[str, str, int], DiffStats],
    models: Sequence[str],
    provider: str | None,
    n_images: int,
    runs: int,
    budget_exceeded: bool = False,
    max_cost: float | None = None,
) -> str:
    lines = [
        "# Banc d'essai de transcription (OCR général) : rapport",
        "",
        f"- Date : {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"- Documents : {n_images} ; lancements par document et par modèle : {runs}",
        f"- Fournisseur demandé : {provider or 'automatique (à éviter pour comparer)'}",
    ]
    if budget_exceeded:
        lines.append(f"- **ARRET ANTICIPE** : budget --max-cost={max_cost} dollar(s) atteint.")
    lines += [
        "",
        "## Par modèle",
        "",
        "| Modèle | Appels | Échecs | Erreur mots (moy.) | Substitutions | Omissions | Ajouts "
        "| Nombres déformés | Latence moy. | Tokens moy. | Raisonnement | Coût total |",
        "|" + "---|" * 11,
    ]
    for model in models:
        st = stats.get(model, ModelStats())
        wer = statistics.mean(st.wers) if st.wers else None
        lines.append(
            f"| {model} | {st.calls} | {st.failed} | {pct(wer) if wer is not None else 'n/a'} "
            f"| {st.total_substituted} | {st.total_deleted} | {st.total_inserted} "
            f"| **{len(st.digit_mismatches)}** "
            f"| {statistics.mean(st.latencies):.1f} s | {statistics.mean(st.tokens):.0f} "
            f"| {st.reasoning_tokens} | {st.cost:.4f} $ |"
            if st.latencies
            else f"| {model} | {st.calls} | {st.failed} | - | - | - | - | - | - | - | - | - |"
        )
    lines += ["", "## Nombres déformés (le risque le plus grave : téléphone, date, montant, dosage...)", ""]
    any_digit_mismatch = False
    for model in models:
        st = stats.get(model, ModelStats())
        if not st.digit_mismatches:
            continue
        any_digit_mismatch = True
        lines.append(f"### {model}")
        lines.append("")
        lines.append("| Document | Vérité | Lu |")
        lines.append("|---|---|---|")
        for image, truth_word, read_word in st.digit_mismatches:
            lines.append(f"| {image} | `{truth_word}` | `{read_word}` |")
        lines.append("")
    if not any_digit_mismatch:
        lines.append("Aucun nombre déformé détecté sur cet échantillon.")
        lines.append("")
    lines += ["## Détail par document et par modèle", ""]
    for (model, image, run), stat in sorted(diffs.items()):
        wer = stat.word_error_rate
        lines.append(f"### {model} — {image} (lancement {run})")
        lines.append(
            f"Erreur mots : {pct(wer) if wer is not None else 'n/a'} "
            f"(substitutions {stat.substituted}, omissions {stat.deleted}, ajouts {stat.inserted})"
        )
        if stat.substitutions:
            lines.append("")
            lines.append("Substitutions (vérité -> lu) :")
            for truth_word, read_word in stat.substitutions[:30]:
                lines.append(f"- `{truth_word}` -> `{read_word}`")
        if stat.deleted_words:
            lines.append("")
            lines.append("Mots omis : " + ", ".join(f"`{w}`" for w in stat.deleted_words[:30]))
        if stat.inserted_words:
            lines.append("")
            lines.append("Mots ajoutés (possible invention) : " + ", ".join(f"`{w}`" for w in stat.inserted_words[:30]))
        lines.append("")
    lines.append("Rappel : un échantillon de quelques documents donne une tendance, pas une garantie.")
    return "\n".join(lines) + "\n"


def print_report(report: str) -> None:
    """Affiche le rapport sans planter si la console (ex. cp1252 sur Windows) ne gère pas un caractère."""
    encoding = sys.stdout.encoding or "utf-8"
    try:
        sys.stdout.write(report)
    except UnicodeEncodeError:
        sys.stdout.write(report.encode(encoding, errors="replace").decode(encoding))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Banc d'essai de transcription OCR générale (OpenRouter).")
    parser.add_argument("--images", type=Path, required=True, help="Dossier de photos + *.truth.txt")
    parser.add_argument("--out", type=Path, required=True, help="Dossier des résultats (le relancer reprend)")
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--provider", default=None, help="Slug du fournisseur à figer, ex. deepinfra")
    parser.add_argument("--thinking", action="store_true", help="Laisser le raisonnement actif (déconseillé)")
    parser.add_argument("--base-url", default=os.environ.get("OPENROUTER_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--allow-collection", action="store_true")
    parser.add_argument(
        "--max-cost",
        type=float,
        default=DEFAULT_MAX_COST,
        help=f"Budget maximal en dollars pour cette exécution (défaut : {DEFAULT_MAX_COST}).",
    )
    parser.add_argument(
        "--reasoning-effort",
        nargs="+",
        default=["none"],
        help="Un niveau par modèle (même ordre que --models) ou une seule valeur pour tous. "
        "Ex. : meta/muse-glimmer-30b exige 'minimal' au minimum.",
    )
    parser.add_argument("--dry-run", action="store_true")
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

    if len(args.reasoning_effort) == 1:
        reasoning_by_model = {model: args.reasoning_effort[0] for model in args.models}
    elif len(args.reasoning_effort) == len(args.models):
        reasoning_by_model = dict(zip(args.models, args.reasoning_effort, strict=True))
    else:
        logger.error("--reasoning-effort doit avoir 1 valeur ou autant que --models.")
        return 2

    n_calls = len(images) * args.runs * len(args.models)
    logger.info("%d documents x %d lancements x %d modèles = %d appels", len(images), args.runs, len(args.models), n_calls)
    if args.dry_run:
        return 0
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        logger.error("Variable d'environnement OPENROUTER_API_KEY absente.")
        return 2

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
        reasoning_by_model,
    )
    stats, diffs = analyse(records, truths)
    report = render_report(stats, diffs, args.models, args.provider, len(images), args.runs, budget_exceeded, args.max_cost)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    print_report(report)
    logger.info("Rapport : %s", out_dir / "report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
