from pathlib import PurePath

import httpx

from app.ai.errors import AiAuthError, AiInputError, AiOutputError
from app.ai.metering import record_usage
from app.ai.real.clients.http import request_with_retry
from app.ai.settings import AiSettings
from app.core.languages import Language

ASR_MAX_AUDIO_BYTES = 25 * 1024 * 1024

_AUDIO_CONTENT_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".webm": "audio/webm",
}

_TTS_VOICES: dict[Language, str] = {Language.WOLOF: "wo", Language.PULAAR: "ff"}
_ASR_LANGUAGES: dict[Language, str] = {
    Language.WOLOF: "wo",
    Language.PULAAR: "ff",
    Language.SERER: "srr",
}


def _safe_filename(filename: str) -> str:
    name = PurePath(filename.replace("\\", "/")).name or "audio"
    return name if PurePath(name).suffix.lower() in _AUDIO_CONTENT_TYPES else f"{name}.ogg"


class KirikuClient:
    def __init__(self, settings: AiSettings, http: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http

    async def transcribe(self, audio: bytes, *, filename: str, language: Language | None) -> str:
        if not audio:
            raise AiInputError("asr: empty audio")
        if len(audio) > ASR_MAX_AUDIO_BYTES:
            raise AiInputError(f"asr: audio of {len(audio)} bytes exceeds the limit")
        settings = self._settings
        if not settings.asr_base_url:
            raise AiAuthError("asr: ASR_BASE_URL is not configured")
        name = _safe_filename(filename)
        data = {"model": settings.asr_model, "response_format": "json"}
        if language is not None:
            data["language"] = _ASR_LANGUAGES[language]
        response = await request_with_retry(
            self._http,
            "POST",
            f"{settings.asr_base_url.rstrip('/')}/v1/audio/transcriptions",
            service="asr",
            max_retries=settings.asr_max_retries,
            timeout=settings.asr_timeout_seconds,
            headers={"Authorization": f"Bearer {settings.asr_api_key.get_secret_value()}"},
            data=data,
            files={"file": (name, audio, _AUDIO_CONTENT_TYPES[PurePath(name).suffix.lower()])},
        )
        record_usage("asr")
        body = response.json()
        text = body.get("text") if isinstance(body, dict) else None
        if not isinstance(text, str):
            raise AiOutputError("asr: response without text")
        return text.strip()

    async def synthesize(self, text: str, language: Language) -> bytes:
        settings = self._settings
        voice = _TTS_VOICES.get(language)
        if voice is None:
            raise AiInputError(f"tts: no voice available for {language.value}")
        if not text.strip():
            raise AiInputError("tts: empty text")
        if len(text) > settings.tts_max_input_chars:
            raise AiInputError(f"tts: text of {len(text)} characters exceeds the limit")
        if not settings.tts_base_url:
            raise AiAuthError("tts: TTS_BASE_URL is not configured")
        payload: dict[str, object] = {
            "model": settings.tts_model,
            "input": text,
            "voice": voice,
            "response_format": "wav",
        }
        speed = (
            settings.tts_speed_wolof if language is Language.WOLOF else settings.tts_speed_pulaar
        )
        if speed is not None:
            payload["speed"] = speed
        response = await request_with_retry(
            self._http,
            "POST",
            f"{settings.tts_base_url.rstrip('/')}/v1/audio/speech",
            service="tts",
            max_retries=settings.tts_max_retries,
            timeout=settings.tts_timeout_seconds,
            headers={"Authorization": f"Bearer {settings.tts_api_key.get_secret_value()}"},
            json=payload,
        )
        record_usage("tts")
        if not response.content:
            raise AiOutputError("tts: empty audio response")
        return response.content
