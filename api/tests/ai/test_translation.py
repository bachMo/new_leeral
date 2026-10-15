import json
import re
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.ai.real.clients.openrouter import ModelProfile, OpenRouterClient
from app.ai.real.safety import posology_phrases
from app.ai.real.translation import Translator
from app.ai.settings import AiSettings
from app.core.languages import Language

_TOKEN = re.compile(r"⟦\d+⟧")


def _hostile_translate(request: httpx.Request) -> httpx.Response:
    """A translator that ignores meaning but must still echo tokens, like a real LLM would."""
    payload = json.loads(request.content)
    prompt = payload["messages"][-1]["content"]
    text = prompt.split("Text:\n", 1)[1]
    garbled = " ".join(["XXXX", *_TOKEN.findall(text), "YYYY"])
    return httpx.Response(
        200, json={"choices": [{"message": {"content": garbled}}], "usage": {"cost": 0.0}}
    )


def _translator() -> Translator:
    settings = AiSettings(openrouter_api_key="key")
    client = OpenRouterClient(
        settings, httpx.AsyncClient(transport=httpx.MockTransport(_hostile_translate))
    )
    profile = ModelProfile("primary", "none", 10.0, 0)
    return Translator(client, profile, profile, max_attempts=1)


async def test_month_name_is_protected_even_against_a_hostile_translator() -> None:
    localized = await _translator().localize(
        "La date limite est le 30 octobre 2026.", Language.WOLOF
    )

    assert "oktoobar" in localized.text
    assert "octobre" not in localized.text
    assert localized.complete


async def test_posology_timing_phrase_is_protected_once_the_catalog_is_filled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        posology_phrases.TRANSLATED_TIMING[Language.WOLOF], "avant le repas", "bala lekk"
    )

    localized = await _translator().localize("Prends-le avant le repas.", Language.WOLOF)

    assert "bala lekk" in localized.text
    assert "repas" not in localized.text
    assert localized.complete


def _draft_then_clean_translate(calls: list[int]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            content = "Mauvais essai.\n\nRewrite properly:\n\nBon essai."
        else:
            content = "Bon essai."
        return httpx.Response(
            200, json={"choices": [{"message": {"content": content}}], "usage": {"cost": 0.0}}
        )

    return httpx.MockTransport(handler)


async def test_multiline_draft_output_is_retried_on_the_fallback_model() -> None:
    calls: list[int] = []
    settings = AiSettings(openrouter_api_key="key")
    transport = _draft_then_clean_translate(calls)
    client = OpenRouterClient(settings, httpx.AsyncClient(transport=transport))
    translator = Translator(
        client,
        ModelProfile("primary", "none", 10.0, 0),
        ModelProfile("fallback", "none", 10.0, 0),
        max_attempts=2,
    )

    localized = await translator.localize("Phrase simple.", Language.WOLOF)

    assert localized.text == "Bon essai."
    assert "\n" not in localized.text
    assert localized.complete


def _recording_translator(
    reply: Callable[[dict[str, Any]], str], requests: list[dict[str, Any]]
) -> Translator:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": reply(payload)}}], "usage": {"cost": 0.0}},
        )

    settings = AiSettings(openrouter_api_key="key")
    client = OpenRouterClient(settings, httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    return Translator(
        client,
        ModelProfile("primary", "none", 10.0, 0),
        ModelProfile("fallback", "none", 10.0, 0),
        max_attempts=2,
    )


def _prompt(payload: dict[str, Any]) -> str:
    return str(payload["messages"][-1]["content"])


def _echo_tokens(payload: dict[str, Any]) -> str:
    text = _prompt(payload).split("Text:\n", 1)[1]
    return " ".join(["Traduit", *_TOKEN.findall(text), "ak jàmm."])


_TEXT = "C'est une facture de 12 500 FCFA. Tu dois la payer avant le 30 octobre 2026."


async def test_whole_text_is_translated_in_a_single_call_with_the_listener_prompt() -> None:
    requests: list[dict[str, Any]] = []
    translator = _recording_translator(_echo_tokens, requests)

    localized = await translator.localize(_TEXT, Language.WOLOF)

    assert len(requests) == 1
    assert "read aloud" in _prompt(requests[0])
    assert "12 500" in localized.text
    assert "oktoobar" in localized.text
    assert localized.complete


async def test_whole_text_with_a_lost_token_falls_back_to_sentences() -> None:
    requests: list[dict[str, Any]] = []

    def reply(payload: dict[str, Any]) -> str:
        if "read aloud" in _prompt(payload):
            return "Traduction sans les nombres."
        return _echo_tokens(payload)

    localized = await _recording_translator(reply, requests).localize(_TEXT, Language.WOLOF)

    whole_calls = [request for request in requests if "read aloud" in _prompt(request)]
    assert len(whole_calls) == 2
    assert len(requests) == 2 + 2
    assert "12 500" in localized.text
    assert localized.complete


async def test_whole_text_with_an_implausible_length_falls_back_to_sentences() -> None:
    requests: list[dict[str, Any]] = []

    def reply(payload: dict[str, Any]) -> str:
        if "read aloud" in _prompt(payload):
            return _echo_tokens(payload) + " bla" * 200
        return _echo_tokens(payload)

    localized = await _recording_translator(reply, requests).localize(_TEXT, Language.WOLOF)

    assert "bla" not in localized.text
    assert localized.complete


async def test_empty_answer_from_the_primary_model_is_retried_on_the_fallback() -> None:
    requests: list[dict[str, Any]] = []

    def reply(payload: dict[str, Any]) -> str:
        if payload["model"] == "primary":
            return ""
        return _echo_tokens(payload)

    localized = await _recording_translator(reply, requests).localize(_TEXT, Language.WOLOF)

    assert any(request["model"] == "fallback" for request in requests)
    assert "12 500" in localized.text
    assert localized.complete


async def test_isolated_word_skips_the_whole_text_prompt() -> None:
    requests: list[dict[str, Any]] = []
    translator = _recording_translator(lambda payload: "fay", requests)

    localized = await translator.localize("facture", Language.WOLOF)

    assert localized.text == "fay"
    assert all("read aloud" not in _prompt(request) for request in requests)


async def test_question_is_translated_to_french_in_one_call() -> None:
    requests: list[dict[str, Any]] = []
    translator = _recording_translator(lambda payload: "Combien de jours ?", requests)

    french = await translator.to_french("ñaata fan laa wara naan siro bi", Language.WOLOF)

    assert french == "Combien de jours ?"
    assert len(requests) == 1
    assert "transcribed" in _prompt(requests[0])
