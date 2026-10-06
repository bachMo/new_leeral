import asyncio
import re

from app.ai.audio import concat_wav, wav_to_speech
from app.ai.contracts import SpeechAudio
from app.ai.errors import AiInputError
from app.ai.real.clients.kiriku import KirikuClient
from app.core.languages import Language

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?\n])\s+")
_WORD_BOUNDARY = re.compile(r"\s+")


def chunk_text(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for sentence in (part.strip() for part in _SENTENCE_BOUNDARY.split(text)):
        if not sentence:
            continue
        for piece in _split_long(sentence, max_chars):
            candidate = f"{current} {piece}".strip()
            if len(candidate) <= max_chars:
                current = candidate
            else:
                chunks.append(current)
                current = piece
    if current:
        chunks.append(current)
    return chunks


def _split_long(sentence: str, max_chars: int) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence]
    pieces: list[str] = []
    current = ""
    for word in _WORD_BOUNDARY.split(sentence):
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            pieces.append(current)
        current = word[:max_chars]
    if current:
        pieces.append(current)
    return pieces


class SpeechSynthesizer:
    def __init__(
        self, kiriku: KirikuClient, *, max_chars: int, concurrency: int, bitrate_kbps: int
    ) -> None:
        self._kiriku = kiriku
        self._max_chars = max_chars
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self._bitrate_kbps = bitrate_kbps

    async def speak(self, text: str, language: Language) -> SpeechAudio:
        chunks = chunk_text(text, self._max_chars)
        if not chunks:
            raise AiInputError("nothing to speak")
        wavs = await asyncio.gather(*(self._synthesize(chunk, language) for chunk in chunks))
        return wav_to_speech(concat_wav(wavs), bitrate_kbps=self._bitrate_kbps)

    async def _synthesize(self, chunk: str, language: Language) -> bytes:
        async with self._semaphore:
            return await self._kiriku.synthesize(chunk, language)
