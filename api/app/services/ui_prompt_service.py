import logging
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.engine import AiEngine
from app.core.errors import AppError
from app.core.languages import Language
from app.integrations.storage import FileStorage
from app.models import UiPrompt
from app.repositories.system import UiPromptRepository
from app.services import storage_keys
from app.services.narrator import Narrator
from app.services.ui_prompt_catalog import prompt_catalog

logger = logging.getLogger("leeral.prompts")


class UiPromptService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._prompts = UiPromptRepository(session)

    async def for_language(self, language: Language) -> Sequence[UiPrompt]:
        return await self._prompts.for_language(language)

    async def find(self, key: str, language: Language) -> UiPrompt | None:
        return await self._prompts.find(key, language)


class UiPromptSynchronizer:
    def __init__(self, session: AsyncSession, ai: AiEngine, storage: FileStorage) -> None:
        self._session = session
        self._storage = storage
        self._prompts = UiPromptRepository(session)
        self._narrator = Narrator(ai)

    async def sync(self, language: Language, *, force: bool = False) -> tuple[int, int]:
        created = failed = 0
        for key, text_fr in prompt_catalog().items():
            existing = await self._prompts.find(key, language)
            if existing is not None and existing.text_fr == text_fr and not force:
                continue
            try:
                _, audio = await self._narrator.voice(text_fr, language)
            except AppError as exc:
                failed += 1
                logger.warning("prompt_sync_failed", extra={"key": key, "code": exc.code})
                continue
            audio_key = storage_keys.prompt_audio(key, language)
            await self._storage.put(audio_key, audio.content, audio.mime_type)
            if existing is None:
                self._session.add(
                    UiPrompt(key=key, language=language, text_fr=text_fr, audio_key=audio_key)
                )
            else:
                existing.text_fr = text_fr
                existing.audio_key = audio_key
            await self._session.commit()
            created += 1
        return created, failed
