"""Télécharge les sources brutes du lexique dans un dossier daté.

Usage :
    python -m scripts.lexicon.fetch --raw-dir data/raw/2026-10-04

Les fichiers bruts ne sont jamais modifiés (licence BDPM) et ne sont pas versionnés dans Git.
Chaque téléchargement est tracé dans fetch_manifest.json (URL, statut, taille, empreinte).
Bibliothèque standard uniquement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger("leeral.lexicon")

BDPM_BASE = "https://base-donnees-publique.medicaments.gouv.fr/download/file"
BDPM_FILES = ("CIS_bdpm.txt", "CIS_COMPO_bdpm.txt", "CIS_MITM.txt")
ARP_PAGES = {
    "arp_liste_amms.html": "https://arp.sn/liste-des-amms/",
    "arp_medicaments_rcp.html": "https://arp.sn/medicaments-rcp/",
}
USER_AGENT = "Leeral-lexicon-builder/0.1 (projet hackathon; contact: equipe Leeral)"
PAUSE_SECONDS = 2.0


def download(url: str, destination: Path, timeout: float = 60.0) -> dict[str, str | int]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    entry: dict[str, str | int] = {"url": url, "file": destination.name}
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            data: bytes = response.read()
            entry["status"] = int(response.status)
    except urllib.error.HTTPError as error:
        entry["status"] = error.code
        logger.error("HTTP %s pour %s", error.code, url)
        return entry
    except urllib.error.URLError as error:
        entry["status"] = 0
        logger.error("Échec réseau pour %s : %s", url, error.reason)
        return entry
    destination.write_bytes(data)
    entry["bytes"] = len(data)
    entry["sha256"] = hashlib.sha256(data).hexdigest()
    logger.info("OK %s (%d octets)", destination.name, len(data))
    return entry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Télécharge les sources du lexique.")
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--skip-arp", action="store_true", help="Ne télécharge que la BDPM.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    raw: Path = args.raw_dir
    raw.mkdir(parents=True, exist_ok=True)
    jobs = [(f"{BDPM_BASE}/{name}", raw / name) for name in BDPM_FILES]
    if not args.skip_arp:
        jobs += [(url, raw / name) for name, url in ARP_PAGES.items()]

    results: list[dict[str, str | int]] = []
    for url, destination in jobs:
        results.append(download(url, destination))
        time.sleep(PAUSE_SECONDS)
    manifest = {"fetched_at": datetime.now(UTC).isoformat(timespec="seconds"), "files": results}
    (raw / "fetch_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    failures = [r for r in results if r.get("status") != 200]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
