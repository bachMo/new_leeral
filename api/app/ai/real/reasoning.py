import logging
from typing import Any

from app.ai.real.clients.openrouter import ModelProfile, OpenRouterClient

logger = logging.getLogger("leeral.ai.reasoning")

_CHARS_PER_TOKEN = 4


class Reasoner:
    def __init__(
        self,
        client: OpenRouterClient,
        short: ModelProfile,
        long: ModelProfile,
        *,
        long_threshold_tokens: int,
    ) -> None:
        self._client = client
        self._short = short
        self._long = long
        self._threshold = long_threshold_tokens

    def _profile_for(self, prompt: str) -> ModelProfile:
        return self._long if len(prompt) // _CHARS_PER_TOKEN > self._threshold else self._short

    async def complete_json(
        self, prompt: str, *, operation: str, max_tokens: int = 2000
    ) -> dict[str, Any]:
        profile = self._profile_for(prompt)
        logger.info("llm_call", extra={"operation": operation, "model": profile.model})
        return await self._client.complete_json(
            profile, prompt, operation=operation, max_tokens=max_tokens
        )
