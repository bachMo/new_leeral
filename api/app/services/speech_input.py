from pathlib import PurePosixPath

from app.ai.engine import AiEngine
from app.ai.errors import TranslationError
from app.core.errors import AppError, ErrorCode
from app.core.languages import Language, TextLanguage
from app.integrations.storage import FileStorage
from app.models import Message
from app.models.enums import MessageStatus


class SpeechInput:
    def __init__(self, ai: AiEngine, storage: FileStorage) -> None:
        self._ai = ai
        self._storage = storage

    async def to_french(self, message: Message, language: Language) -> str:
        if message.text_fr:
            message.status = MessageStatus.READY
            return message.text_fr
        if message.audio_key and message.text is None:
            audio = await self._storage.get(message.audio_key)
            transcript = await self._ai.transcribe(
                audio, filename=PurePosixPath(message.audio_key).name, language=language
            )
            if not transcript.text.strip():
                raise AppError(ErrorCode.AUDIO_EMPTY)
            message.text = transcript.text.strip()
        text = (message.text or "").strip()
        if not text:
            raise AppError(ErrorCode.QUESTION_EMPTY)
        if message.language is TextLanguage.FRENCH:
            message.text_fr = text
        else:
            try:
                message.text_fr = await self._ai.to_french(text, Language(message.language.value))
            except TranslationError as exc:
                raise AppError(ErrorCode.QUESTION_TRANSLATION_FAILED) from exc
        message.status = MessageStatus.READY
        return message.text_fr
