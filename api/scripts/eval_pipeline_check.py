"""Service-side regression check: run the real document pipeline (no database, no backend) over
every file in eval/ordonnances and eval/documents, and summarize crashes/warnings.

    cd api
    python -m scripts.eval_pipeline_check --limit 13
    python -m scripts.eval_pipeline_check          # every file

Each file gets its own report/audio under api/var/try/eval-batch-<timestamp>/<file>/. A single
summary.md is written at the batch root.
"""

import argparse
import asyncio
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.cli import try_document
from app.core.config import PROJECT_ROOT
from app.core.logging import configure_logging

REPOSITORY_ROOT = PROJECT_ROOT.parent
EVAL_ROOT = REPOSITORY_ROOT / "eval"
_WARNING_EVENTS = (
    "analysis_summary_ungrounded",
    "analysis_key_point_ungrounded",
    "translation_multiline_output",
    "translation_token_mismatch",
    "ai_network_retry",
    "ai_status_retry",
    "classification_invalid",
    "prescription_reading_invalid",
)


class _WarningCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.events: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.events.append(record.getMessage())


@dataclass(slots=True)
class _Result:
    name: str
    duration_s: float
    crashed: str | None
    warnings: list[str] = field(default_factory=list)


def discover_files(limit_per_category: int | None = None) -> list[Path]:
    categories = [
        sorted((EVAL_ROOT / "ordonnances").glob("*.jpg")),
        sorted((EVAL_ROOT / "documents").glob("*.jpg")),
        sorted((EVAL_ROOT / "documents").glob("*.pdf")),
    ]
    if limit_per_category:
        categories = [category[:limit_per_category] for category in categories]
    return [path for category in categories for path in category]


async def _run_one(path: Path, out_dir: Path, language: str) -> _Result:
    collector = _WarningCollector()
    root = logging.getLogger()
    root.addHandler(collector)
    started = time.perf_counter()
    crashed: str | None = None
    try:
        await try_document([str(path)], language, [], [], [], str(out_dir))
    except Exception as exc:  # the whole point is to record what broke, not to swallow it
        crashed = f"{type(exc).__name__}: {exc}"
    finally:
        root.removeHandler(collector)
    return _Result(
        name=path.name,
        duration_s=time.perf_counter() - started,
        crashed=crashed,
        warnings=collector.events,
    )


def _write_summary(batch_dir: Path, results: list[_Result]) -> Path:
    lines = ["# Résultat du test de bout en bout (côté service)", ""]
    crashed = [r for r in results if r.crashed]
    warned = [r for r in results if r.warnings and not r.crashed]
    clean = [r for r in results if not r.crashed and not r.warnings]
    lines.append(
        f"{len(results)} fichiers | {len(clean)} ok | {len(warned)} avec avertissement | "
        f"{len(crashed)} en échec"
    )
    lines.append("")
    lines.append("| Fichier | Statut | Durée | Détail |")
    lines.append("|---|---|---|---|")
    for result in results:
        status = "ÉCHEC" if result.crashed else ("avertissement" if result.warnings else "ok")
        detail = result.crashed or "; ".join(result.warnings) or "-"
        lines.append(f"| {result.name} | {status} | {result.duration_s:.1f}s | {detail} |")
    path = batch_dir / "summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit-per-category",
        type=int,
        default=None,
        help="only test the first N files of each of ordonnances/documents-jpg/documents-pdf",
    )
    parser.add_argument("--language", default="wo", choices=["wo", "ff"])
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    configure_logging("WARNING", json_output=False)

    files = discover_files(args.limit_per_category)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    batch_dir = PROJECT_ROOT / "var" / "try" / f"eval-batch-{stamp}"
    results = []
    for index, path in enumerate(files, start=1):
        result = await _run_one(path, batch_dir / path.stem, args.language)
        results.append(result)
        status = "ÉCHEC" if result.crashed else ("avertissement" if result.warnings else "ok")
        print(f"[{index}/{len(files)}] {status} {path.name} ({result.duration_s:.1f}s)")
        if result.crashed:
            print(f"    {result.crashed}")

    summary_path = _write_summary(batch_dir, results)
    print(f"\nrésumé : {summary_path}")


if __name__ == "__main__":
    asyncio.run(main())
