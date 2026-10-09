"""Tests du banc d'essai de transcription, contre un faux serveur OpenRouter local."""

from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import transcription_bench as tb

CAPTURED: list[dict[str, object]] = []
REPLIES: dict[str, str] = {
    "model/good": "Bonjour Monsieur\nTel : 77 621 04 73\nDate : 12/09/2024",
    "model/bad": "```\nBonjour Madame\nTel : 77 621 04 78\nDate : 12/09/2024\nEt une phrase en plus\n```",
}


class FakeOpenRouter(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        CAPTURED.append({"auth": self.headers.get("Authorization"), "body": body})
        reply = {
            "provider": "DeepInfra",
            "choices": [{"message": {"content": REPLIES[body["model"]]}}],
            "usage": {
                "prompt_tokens": 500,
                "completion_tokens": 50,
                "cost": 0.0002,
                "completion_tokens_details": {"reasoning_tokens": 0},
            },
        }
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def test_clean_transcription_strips_code_fences() -> None:
    assert tb.clean_transcription("```\nligne 1\nligne 2\n```") == "ligne 1\nligne 2"
    assert tb.clean_transcription("texte simple") == "texte simple"


def test_diff_words_counts_substitution_deletion_insertion() -> None:
    truth = "Bonjour Monsieur Tel 77 621 04 73"
    read = "Bonjour Madame Tel 77 621 04 78 svp"
    stats = tb.diff_words(truth, read)
    assert stats.substituted == 2  # "Monsieur"->"Madame", "73"->"78"
    assert stats.inserted == 1  # "svp"
    assert stats.deleted == 0
    assert stats.word_error_rate is not None
    assert ("73", "78") in stats.digit_mismatches


def test_diff_words_flags_deleted_numbers_as_digit_mismatch() -> None:
    truth = "Montant 220000 francs"
    read = "Montant francs"
    stats = tb.diff_words(truth, read)
    assert stats.deleted == 1
    assert ("220000", "(absent)") in stats.digit_mismatches


def test_diff_words_perfect_match_has_zero_error() -> None:
    stats = tb.diff_words("ligne identique ici", "ligne identique ici")
    assert stats.word_error_rate == 0.0
    assert stats.substitutions == []


def test_end_to_end_against_fake_server(tmp_path: Path) -> None:
    server = HTTPServer(("127.0.0.1", 0), FakeOpenRouter)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    images = tmp_path / "documents"
    images.mkdir()
    (images / "doc_01.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
    (images / "doc_01.truth.txt").write_text("Bonjour Monsieur\nTel : 77 621 04 73\nDate : 12/09/2024", encoding="utf-8")
    os.environ["OPENROUTER_API_KEY"] = "sk-test"
    out = tmp_path / "out"
    code = tb.main(
        [
            "--images",
            str(images),
            "--out",
            str(out),
            "--runs",
            "1",
            "--provider",
            "deepinfra",
            "--models",
            "model/good",
            "model/bad",
            "--base-url",
            f"http://127.0.0.1:{server.server_port}",
        ]
    )
    server.shutdown()
    assert code == 0
    assert len(CAPTURED) == 2
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "model/good" in report and "model/bad" in report
    assert "Nombres déformés" in report
    assert "77 621 04 78" not in report or "73" in report  # le nombre déformé doit apparaître dans le tableau
    # relancer ne refacture pas un appel déjà réussi (reprise)
    CAPTURED.clear()
    server2 = HTTPServer(("127.0.0.1", 0), FakeOpenRouter)
    threading.Thread(target=server2.serve_forever, daemon=True).start()
    tb.main(
        [
            "--images",
            str(images),
            "--out",
            str(out),
            "--runs",
            "1",
            "--provider",
            "deepinfra",
            "--models",
            "model/good",
            "model/bad",
            "--base-url",
            f"http://127.0.0.1:{server2.server_port}",
        ]
    )
    server2.shutdown()
    assert CAPTURED == []


def test_dry_run_makes_no_call(tmp_path: Path) -> None:
    images = tmp_path / "d"
    images.mkdir()
    (images / "a.jpg").write_bytes(b"x")
    (images / "a.truth.txt").write_text("texte", encoding="utf-8")
    assert tb.main(["--images", str(images), "--out", str(tmp_path / "r"), "--models", "m/x", "--dry-run"]) == 0


def test_reasoning_effort_per_model_mismatch_errors(tmp_path: Path) -> None:
    images = tmp_path / "d"
    images.mkdir()
    (images / "a.jpg").write_bytes(b"x")
    (images / "a.truth.txt").write_text("texte", encoding="utf-8")
    os.environ["OPENROUTER_API_KEY"] = "sk-test"
    code = tb.main(
        [
            "--images",
            str(images),
            "--out",
            str(tmp_path / "r"),
            "--models",
            "m/a",
            "m/b",
            "--reasoning-effort",
            "none",
            "minimal",
            "low",
            "--dry-run",
        ]
    )
    assert code == 2


def test_print_report_falls_back_on_console_encoding_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reproduit une console Windows cp1252 qui ne sait pas encoder un caractère comme '○'."""

    class Cp1252Stdout:
        encoding = "cp1252"

        def write(self, text: str) -> int:
            text.encode("cp1252")
            return len(text)

    monkeypatch.setattr(sys, "stdout", Cp1252Stdout())
    tb.print_report("titre normal\n○ puce non encodable en cp1252\n")
