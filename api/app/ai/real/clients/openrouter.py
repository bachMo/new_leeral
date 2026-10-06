import base64
import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.ai.errors import AiAuthError, AiOutputError
from app.ai.metering import record_usage
from app.ai.real.clients.http import request_with_retry
from app.ai.settings import AiSettings, ReasoningEffort

_CODE_FENCE = re.compile(r"^```(?:json)?|```$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ModelProfile:
    model: str
    reasoning_effort: ReasoningEffort
    timeout_seconds: float
    max_retries: int
    pinned_provider: str | None = None


def image_part(image: bytes, mime_type: str) -> dict[str, Any]:
    encoded = base64.b64encode(image).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}}


def text_part(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def parse_json_object(content: str) -> dict[str, Any]:
    cleaned = _CODE_FENCE.sub("", content.strip()).strip()
    candidates = [cleaned]
    if (start := cleaned.find("{")) != -1 and (end := cleaned.rfind("}")) > start:
        candidates.append(cleaned[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise AiOutputError("model output is not a JSON object")


class OpenRouterClient:
    def __init__(self, settings: AiSettings, http: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http

    async def complete(
        self,
        profile: ModelProfile,
        content: str | list[dict[str, Any]],
        *,
        operation: str,
        max_tokens: int = 2000,
        system: str | None = None,
    ) -> str:
        api_key = self._settings.openrouter_api_key.get_secret_value()
        if not api_key:
            raise AiAuthError("openrouter: OPENROUTER_API_KEY is not configured")
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})
        routing: dict[str, Any] = {"data_collection": "deny"}
        if profile.pinned_provider:
            routing["order"] = [profile.pinned_provider]
            routing["allow_fallbacks"] = False
        payload = {
            "model": profile.model,
            "temperature": 0,
            "max_tokens": max_tokens,
            "messages": messages,
            "provider": routing,
            "reasoning": {"effort": profile.reasoning_effort},
            "usage": {"include": True},
        }
        response = await request_with_retry(
            self._http,
            "POST",
            f"{self._settings.openrouter_base_url.rstrip('/')}/chat/completions",
            service=f"openrouter:{operation}",
            max_retries=profile.max_retries,
            timeout=profile.timeout_seconds,
            headers={"Authorization": f"Bearer {api_key}", "X-Title": "Leeral"},
            json=payload,
        )
        body = response.json()
        record_usage(operation, _cost(body))
        return _message_content(body)

    async def complete_json(
        self,
        profile: ModelProfile,
        content: str | list[dict[str, Any]],
        *,
        operation: str,
        max_tokens: int = 2000,
        system: str | None = None,
    ) -> dict[str, Any]:
        raw = await self.complete(
            profile, content, operation=operation, max_tokens=max_tokens, system=system
        )
        return parse_json_object(raw)


def _message_content(body: Any) -> str:
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AiOutputError("openrouter: response without choices") from exc
    if not isinstance(content, str) or not content.strip():
        raise AiOutputError("openrouter: empty message content")
    return content


def _cost(body: Any) -> float | None:
    if isinstance(body, dict) and isinstance(usage := body.get("usage"), dict):
        cost = usage.get("cost")
        if isinstance(cost, int | float):
            return float(cost)
    return None
