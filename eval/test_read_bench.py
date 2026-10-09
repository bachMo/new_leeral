"""Tests du banc d'essai, contre un faux serveur OpenRouter local (aucun appel réseau réel)."""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import read_bench as rb

CAPTURED: list[dict[str, object]] = []
REPLIES: dict[str, str] = {
    "model/good": json.dumps(
        {
            "document_language": "fr",
            "medications": [
                {
                    "name_read": "Amoxicilline",
                    "strength": "500 mg",
                    "times_per_day": 3,
                    "duration_days": 7,
                    "legible": "yes",
                },
                {
                    "name_read": "Paracétamol",
                    "strength": "1 g",
                    "times_per_day": None,
                    "duration_days": None,
                    "legible": "yes",
                },
            ],
        }
    ),
    "model/bad": "```json\n"
    + json.dumps(
        {
            "medications": [
                {
                    "name_read": "Amoxiciline",
                    "strength": "500 mg",
                    "times_per_day": 2,
                    "duration_days": 7,
                    "legible": "yes",
                },
                {
                    "name_read": "Paracetamol",
                    "strength": None,
                    "times_per_day": None,
                    "duration_days": None,
                    "legible": "no",
                },
                {"name_read": "Inventé", "strength": "5 mg", "legible": "yes"},
            ]
        }
    )
    + "\n```",
}


class FakeOpenRouter(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        CAPTURED.append({"auth": self.headers.get("Authorization"), "body": body})
        reply = {
            "provider": "DeepInfra",
            "choices": [{"message": {"content": REPLIES[body["model"]]}}],
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 200,
                "cost": 0.001,
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


def test_fold_and_normalisers() -> None:
    assert rb.fold("Paracétamol 1 g") == "paracetamol 1 g"
    assert rb.norm_strength("0,5 g") == "0.5g"
    assert rb.norm_strength("500mg") == rb.norm_strength("500 mg")
    assert rb.norm_int("3") == 3 and rb.norm_int(3.0) == 3 and rb.norm_int(True) is None


def test_extract_json_tolerates_code_fences_and_text() -> None:
    assert rb.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert rb.extract_json('Voici : {"a": 1} fin') == {"a": 1}
    assert rb.extract_json("pas de json") is None


def test_unflagged_error_requires_confident_wrong_value() -> None:
    truth: list[rb.JsonObj] = [{"name": "Amoxicilline", "strength": "500 mg", "times_per_day": 3, "duration_days": 7}]
    confident: list[rb.JsonObj] = [
        {
            "name_read": "Amoxicilline",
            "strength": "500 mg",
            "times_per_day": 2,
            "duration_days": 7,
            "legible": "yes",
        }
    ]
    flagged: list[rb.JsonObj] = [
        {
            "name_read": "Amoxicilline",
            "strength": "500 mg",
            "times_per_day": 2,
            "duration_days": 7,
            "legible": "partial",
        }
    ]
    abstain: list[rb.JsonObj] = [
        {
            "name_read": "Amoxicilline",
            "strength": "500 mg",
            "times_per_day": None,
            "duration_days": 7,
            "legible": "partial",
        }
    ]
    assert rb.unflagged_errors(rb.score_run(truth, confident)) == 1
    assert rb.unflagged_errors(rb.score_run(truth, flagged)) == 0
    score = rb.score_run(truth, abstain)
    assert rb.unflagged_errors(score) == 0
    assert score.fields[(0, "times_per_day")].status == "abstain"


def test_missing_and_invented_medications() -> None:
    truth: list[rb.JsonObj] = [
        {"name": "Amoxicilline", "strength": "500 mg"},
        {"name": "Ibuprofène", "strength": "400 mg"},
    ]
    read: list[rb.JsonObj] = [
        {"name_read": "Amoxicilline", "strength": "500 mg", "legible": "yes"},
        {"name_read": "Zzzzz", "strength": "1 mg", "legible": "yes"},
    ]
    score = rb.score_run(truth, read)
    assert score.omitted == 1 and score.invented_confident == 1


def test_end_to_end_against_fake_server(tmp_path: Path) -> None:
    server = HTTPServer(("127.0.0.1", 0), FakeOpenRouter)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    images = tmp_path / "ordonnances"
    images.mkdir()
    (images / "ord_01.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
    (images / "ord_01.truth.json").write_text(
        json.dumps(
            {
                "medications": [
                    {"name": "Amoxicilline", "strength": "500 mg", "times_per_day": 3, "duration_days": 7},
                    {"name": "Paracétamol", "strength": "1 g", "times_per_day": None, "duration_days": None},
                ]
            }
        ),
        encoding="utf-8",
    )
    import os

    os.environ["OPENROUTER_API_KEY"] = "sk-test"
    out = tmp_path / "out"
    code = rb.main(
        [
            "--images",
            str(images),
            "--out",
            str(out),
            "--runs",
            "2",
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
    assert len(CAPTURED) == 4  # 1 image x 2 lancements x 2 modèles
    sent = CAPTURED[0]
    assert sent["auth"] == "Bearer sk-test"
    body = sent["body"]
    assert isinstance(body, dict)
    assert body["provider"] == {"data_collection": "deny", "order": ["deepinfra"], "allow_fallbacks": False}
    assert body["reasoning"] == {"effort": "none"}
    assert body["temperature"] == 0
    content = body["messages"][0]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "model/good" in report and "model/bad" in report
    assert "Accord mais faux" in report
    # relancer ne refacture pas un appel déjà réussi (reprise)
    CAPTURED.clear()
    server2 = HTTPServer(("127.0.0.1", 0), FakeOpenRouter)
    threading.Thread(target=server2.serve_forever, daemon=True).start()
    rb.main(
        [
            "--images",
            str(images),
            "--out",
            str(out),
            "--runs",
            "2",
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
    images = tmp_path / "o"
    images.mkdir()
    (images / "a.jpg").write_bytes(b"x")
    (images / "a.truth.json").write_text('{"medications": []}', encoding="utf-8")
    assert rb.main(["--images", str(images), "--out", str(tmp_path / "r"), "--dry-run"]) == 0


def test_allow_collection_flag_changes_routing(tmp_path: Path) -> None:
    image = tmp_path / "a.jpg"
    image.write_bytes(b"x")
    strict = rb.build_payload("m/x", image, "deepinfra", thinking=False)
    loose = rb.build_payload("m/x", image, "deepinfra", thinking=False, allow_collection=True)
    assert strict["provider"] == {"data_collection": "deny", "order": ["deepinfra"], "allow_fallbacks": False}
    assert loose["provider"] == {"data_collection": "allow", "order": ["deepinfra"], "allow_fallbacks": False}
    assert "reasoning" not in rb.build_payload("m/x", image, None, thinking=True)


def test_max_cost_stops_new_calls_but_keeps_cache_free(tmp_path: Path) -> None:
    """Chaque appel facture 0.001 $ (faux serveur) : un budget de 0.002 $ doit arrêter après 2 appels."""
    server = HTTPServer(("127.0.0.1", 0), FakeOpenRouter)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    images = tmp_path / "ordonnances"
    images.mkdir()
    (images / "ord_01.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
    (images / "ord_01.truth.json").write_text('{"medications": []}', encoding="utf-8")

    import os

    os.environ["OPENROUTER_API_KEY"] = "sk-test"
    out = tmp_path / "out"
    code = rb.main(
        [
            "--images",
            str(images),
            "--out",
            str(out),
            "--runs",
            "2",
            "--provider",
            "deepinfra",
            "--models",
            "model/good",
            "model/bad",
            "--base-url",
            f"http://127.0.0.1:{server.server_port}",
            "--max-cost",
            "0.002",
        ]
    )
    server.shutdown()
    assert code == 0
    # 4 appels possibles (2 lancements x 2 modèles), mais le budget coupe après le 2e (2 x 0.001 $).
    assert len(CAPTURED) == 2
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "ARRET ANTICIPE" in report


def test_print_report_falls_back_on_console_encoding_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reproduit une console Windows cp1252 qui ne sait pas encoder un caractère comme '○'."""

    class Cp1252Stdout:
        encoding = "cp1252"

        def write(self, text: str) -> int:
            text.encode("cp1252")  # lève UnicodeEncodeError comme le ferait sys.stdout.write réel
            return len(text)

    monkeypatch.setattr(sys, "stdout", Cp1252Stdout())
    rb.print_report("titre normal\n○ puce non encodable en cp1252\n")
