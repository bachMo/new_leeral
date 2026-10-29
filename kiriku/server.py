import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import PurePath
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from engines import AudioDecodeError, SpeechRecognizer, VoiceSynthesizer, decode_audio
from settings import load_settings

log = logging.getLogger("kiriku")
MAX_INPUT_CHARS = 1000
MAX_AUDIO_BYTES = 25 * 1024 * 1024


class State:
    def __init__(self) -> None:
        self.recognizer: SpeechRecognizer | None = None
        self.voices: dict[str, VoiceSynthesizer] = {}


state = State()


def configure_threads(threads: int) -> None:
    import torch

    torch.set_num_threads(threads)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = load_settings()
    configure_threads(settings.threads)
    for voice in settings.voices:
        state.voices[voice.code] = await asyncio.to_thread(
            VoiceSynthesizer, voice, settings.voice_dir(voice)
        )
        log.info("voice %s loaded", voice.code)
    state.recognizer = await asyncio.to_thread(SpeechRecognizer, settings)
    log.info("asr loaded, %s threads", settings.threads)
    yield


app = FastAPI(title="KIRIKU local", lifespan=lifespan)


class SpeechRequest(BaseModel):
    model: str = "kiriku-tts"
    input: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    voice: str
    response_format: str = "wav"
    speed: float | None = Field(default=None, gt=0, le=3)


@app.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "voices": sorted(state.voices), "asr": state.recognizer is not None}


@app.get("/v1/models")
def models() -> dict[str, object]:
    return {"object": "list", "data": [{"id": "kiriku-tts"}, {"id": "m-kiriku-asr"}]}


@app.post("/v1/audio/speech")
async def speech(request: SpeechRequest) -> Response:
    voice = state.voices.get(request.voice)
    if voice is None:
        raise HTTPException(
            422, f"unknown voice {request.voice!r}, expected one of {sorted(state.voices)}"
        )
    if request.response_format != "wav":
        raise HTTPException(422, "only wav is supported")
    if not request.input.strip():
        raise HTTPException(422, "empty input")
    started = time.perf_counter()
    audio = await asyncio.to_thread(voice.synthesize, request.input, request.speed)
    log.info(
        "tts voice=%s chars=%d ms=%d",
        request.voice,
        len(request.input),
        (time.perf_counter() - started) * 1000,
    )
    return Response(audio, media_type="audio/wav")


@app.post("/v1/audio/transcriptions")
async def transcriptions(
    file: Annotated[UploadFile, File()],
    model: Annotated[str, Form()] = "m-kiriku-asr",
    language: Annotated[str | None, Form()] = None,
    response_format: Annotated[str, Form()] = "json",
) -> dict[str, str]:
    recognizer = state.recognizer
    if recognizer is None:
        raise HTTPException(503, "asr not loaded")
    data = await file.read()
    if not data:
        raise HTTPException(422, "empty audio")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "audio too large")
    started = time.perf_counter()
    try:
        audio = await asyncio.to_thread(decode_audio, data, PurePath(file.filename or "").suffix)
    except AudioDecodeError as exc:
        raise HTTPException(415, f"cannot decode audio: {exc}") from exc
    text = await asyncio.to_thread(recognizer.transcribe, audio, language)
    log.info(
        "asr language=%s seconds=%.1f ms=%d",
        language,
        len(audio) / 16000,
        (time.perf_counter() - started) * 1000,
    )
    return {"text": text}
