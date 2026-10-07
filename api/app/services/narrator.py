import logging
from collections.abc import Sequence

from app.ai.contracts import LocalizedText, SpeechAudio
from app.ai.engine import AiEngine
from app.core.languages import Language
from app.core.logging import log_step

logger = logging.getLogger("leeral.narrator")


class Narrator:
    def __init__(self, ai: AiEngine) -> None:
        self._ai = ai

    async def voice(
        self, text_fr: str, language: Language, *, protected_terms: Sequence[str] = ()
    ) -> tuple[LocalizedText, SpeechAudio]:
        with log_step(logger, "narration", language=language.value, length=len(text_fr)) as out:
            localized = await self._ai.localize(
                text_fr, language, protected_terms=protected_terms
            )
            audio = await self._ai.speak(localized.text, language)
            out["audio_duration_s"] = audio.duration_s
            return localized, audio
