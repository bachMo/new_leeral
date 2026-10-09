"""Tests du banc d'essai de traduction, contre un faux serveur OpenRouter local (aucun appel réel)."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import translate_bench as tb

CAPTURED: list[dict[str, object]] = []


class FakeOpenRouter(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        CAPTURED.append({"auth": self.headers.get("Authorization"), "body": body})
        reply = {
            "provider": "GoogleAIStudio",
            "choices": [{"message": {"content": "Bonjour le monde"}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 10, "cost": 0.0001},
        }
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def write_sample(tmp_path: Path) -> Path:
    data = {
        "items": [
            {"id": 1, "fr": "Bonjour le monde", "en": "Hello world", "wo": "Salaam", "ff": "Jam"},
            {"id": 2, "fr": "Au revoir", "en": "Goodbye", "wo": "Ba beneen", "ff": "Sellam"},
        ]
    }
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_chrf_identical_strings_is_100() -> None:
    assert tb.chrf("Bonjour le monde", "Bonjour le monde") == pytest.approx(100.0)


def test_chrf_empty_is_zero() -> None:
    assert tb.chrf("", "Bonjour") == 0.0
    assert tb.chrf("Bonjour", "") == 0.0


def test_chrf_partial_overlap_between_zero_and_hundred() -> None:
    score = tb.chrf("Bonjour le monde", "Bonsoir la lune")
    assert 0.0 < score < 100.0


def test_chrf_is_order_sensitive_enough_to_penalise_wrong_text() -> None:
    close = tb.chrf("Bonjour le monde", "Bonjour le monde!")
    far = tb.chrf("Complètement autre chose", "Bonjour le monde")
    assert close > far


def test_load_items(tmp_path: Path) -> None:
    items = tb.load_items(write_sample(tmp_path))
    assert len(items) == 2
    assert items[0].sentence_id == 1
    assert items[0].texts["fr"] == "Bonjour le monde"
    assert items[0].texts["wo"] == "Salaam"


def test_directions_cover_both_ways_for_each_pivot_target_pair() -> None:
    assert ("fr", "wo") in tb.DIRECTIONS
    assert ("wo", "fr") in tb.DIRECTIONS
    assert ("en", "ff") in tb.DIRECTIONS
    assert ("ff", "en") in tb.DIRECTIONS
    assert len(tb.DIRECTIONS) == 8


def test_end_to_end_against_fake_server(tmp_path: Path) -> None:
    CAPTURED.clear()
    os.environ["OPENROUTER_API_KEY"] = "sk-test"
    server = HTTPServer(("127.0.0.1", 0), FakeOpenRouter)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        data_path = write_sample(tmp_path)
        out_dir = tmp_path / "out"
        rc = tb.main(
            [
                "--data",
                str(data_path),
                "--out",
                str(out_dir),
                "--models",
                "fake/model",
                "--directions",
                "fr-wo",
                "wo-fr",
                "--base-url",
                f"http://127.0.0.1:{server.server_port}/v1",
            ]
        )
        assert rc == 0
        assert (out_dir / "report.md").exists()
        report = (out_dir / "report.md").read_text("utf-8")
        assert "fr-wo" in report
        assert "wo-fr" in report
        assert len(CAPTURED) == 4  # 2 phrases x 2 sens x 1 lancement x 1 modèle
        first_body = CAPTURED[0]["body"]
        assert isinstance(first_body, dict)
        assert first_body["model"] == "fake/model"
        assert "Translate" in first_body["messages"][0]["content"]

        # Relancer ne doit pas refaire d'appel (reprise depuis le cache).
        CAPTURED.clear()
        rc2 = tb.main(
            [
                "--data",
                str(data_path),
                "--out",
                str(out_dir),
                "--models",
                "fake/model",
                "--directions",
                "fr-wo",
                "wo-fr",
                "--base-url",
                f"http://127.0.0.1:{server.server_port}/v1",
            ]
        )
        assert rc2 == 0
        assert len(CAPTURED) == 0
    finally:
        server.shutdown()


def test_dry_run_makes_no_call(tmp_path: Path) -> None:
    CAPTURED.clear()
    data_path = write_sample(tmp_path)
    rc = tb.main(
        [
            "--data",
            str(data_path),
            "--out",
            str(tmp_path / "out"),
            "--models",
            "fake/model",
            "--dry-run",
        ]
    )
    assert rc == 0
    assert not (tmp_path / "out").exists()
    assert len(CAPTURED) == 0


def test_max_cost_stops_new_calls_but_keeps_cache_free(tmp_path: Path) -> None:
    CAPTURED.clear()
    os.environ["OPENROUTER_API_KEY"] = "sk-test"
    server = HTTPServer(("127.0.0.1", 0), FakeOpenRouter)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        data_path = write_sample(tmp_path)
        out_dir = tmp_path / "out"
        rc = tb.main(
            [
                "--data",
                str(data_path),
                "--out",
                str(out_dir),
                "--models",
                "fake/model",
                "--directions",
                "fr-wo",
                "--max-cost",
                "0.00005",
                "--base-url",
                f"http://127.0.0.1:{server.server_port}/v1",
            ]
        )
        assert rc == 0
        assert len(CAPTURED) == 1  # un seul appel facturé avant l'arrêt du budget
        report = (out_dir / "report.md").read_text("utf-8")
        assert "ARRET ANTICIPE" in report
    finally:
        server.shutdown()


@pytest.mark.parametrize("env_var", ["OPENROUTER_API_KEY"])
def test_missing_api_key_fails_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, env_var: str) -> None:
    monkeypatch.delenv(env_var, raising=False)
    data_path = write_sample(tmp_path)
    rc = tb.main(["--data", str(data_path), "--out", str(tmp_path / "out"), "--models", "fake/model"])
    assert rc == 2
