import pytest

from app.ai.contracts import Transcript
from app.ai.errors import TranslationError
from app.core.errors import AppError, ErrorCode
from app.core.languages import Language, TextLanguage
from app.models import Message
from app.services.speech_input import SpeechInput


class _FakeAi:
    def __init__(self, *, transcript: str = "", translated: str | None = None) -> None:
        self._transcript = transcript
        self._translated = translated

    async def transcribe(self, audio: bytes, *, filename: str, language: Language) -> Transcript:
        return Transcript(text=self._transcript, language=language)

    async def to_french(self, text: str, language: Language) -> str:
        if self._translated is None:
            raise TranslationError("no sentence could be translated")
        return self._translated


class _FakeStorage:
    def __init__(self, content: bytes = b"audio-bytes") -> None:
        self._content = content

    async def get(self, key: str) -> bytes:
        return self._content


def _message(**overrides: object) -> Message:
    defaults: dict[str, object] = {"text": None, "text_fr": None, "audio_key": None}
    defaults.update(overrides)
    return Message(**defaults)  # type: ignore[arg-type]


async def test_already_french_text_is_returned_without_calling_the_translator() -> None:
    message = _message(text="Combien je dois payer ?", language=TextLanguage.FRENCH)

    result = await SpeechInput(_FakeAi(), _FakeStorage()).to_french(message, Language.WOLOF)

    assert result == "Combien je dois payer ?"


async def test_empty_transcript_raises_audio_empty() -> None:
    message = _message(audio_key="questions/1.ogg", language=TextLanguage.WOLOF)
    speech_input = SpeechInput(_FakeAi(transcript="   "), _FakeStorage())

    with pytest.raises(AppError) as error:
        await speech_input.to_french(message, Language.WOLOF)

    assert error.value.code is ErrorCode.AUDIO_EMPTY


async def test_translation_failure_is_reported_as_a_question_specific_error() -> None:
    message = _message(text="Kañ laa wara fey ?", language=TextLanguage.WOLOF)
    speech_input = SpeechInput(_FakeAi(translated=None), _FakeStorage())

    with pytest.raises(AppError) as error:
        await speech_input.to_french(message, Language.WOLOF)

    assert error.value.code is ErrorCode.QUESTION_TRANSLATION_FAILED
