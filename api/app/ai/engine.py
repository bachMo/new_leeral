from collections.abc import Sequence
from typing import Protocol

from app.ai.contracts import (
    Answer,
    ComposedWriting,
    DocumentAnalysis,
    DocumentContext,
    ImageQuality,
    LocalizedText,
    PageInput,
    QuestionContext,
    SpeechAudio,
    Transcript,
    VocabularyCandidate,
    WritingField,
)
from app.core.languages import Language


class AiEngine(Protocol):
    @property
    def name(self) -> str: ...

    async def check_image(self, image: bytes) -> ImageQuality: ...

    async def analyze_document(self, pages: Sequence[PageInput]) -> DocumentAnalysis: ...

    async def simplify(self, document: DocumentContext) -> str: ...

    async def localize(
        self, text_fr: str, language: Language, *, protected_terms: Sequence[str] = ()
    ) -> LocalizedText: ...

    async def to_french(self, text: str, language: Language) -> str: ...

    async def speak(self, text: str, language: Language) -> SpeechAudio: ...

    async def transcribe(
        self, audio: bytes, *, filename: str, language: Language | None
    ) -> Transcript: ...

    async def answer(self, context: QuestionContext) -> Answer: ...

    async def interpret_writing_answer(self, field: WritingField, answer_fr: str) -> str | None: ...

    async def compose_writing(
        self, writing_type: str, fields: Sequence[WritingField], values: dict[str, str]
    ) -> ComposedWriting: ...

    async def extract_vocabulary(
        self, text_fr: str, *, limit: int
    ) -> list[VocabularyCandidate]: ...

    async def aclose(self) -> None: ...
