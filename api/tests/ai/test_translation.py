import json
import re

import httpx

from app.ai.real.clients.openrouter import ModelProfile, OpenRouterClient
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
