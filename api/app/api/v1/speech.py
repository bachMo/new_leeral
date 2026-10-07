from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from app.api.deps import Container, CurrentUser
from app.api.uploads import read_upload
from app.core.errors import AppError, ErrorCode
from app.schemas.speech import TranscriptionOut
from app.services.media import detect_audio

router = APIRouter(prefix="/speech", tags=["speech"])


@router.post("/transcriptions", response_model=TranscriptionOut)
async def transcribe(
    user: CurrentUser,
    container: Container,
    audio: Annotated[UploadFile, File()],
) -> TranscriptionOut:
    incoming = await read_upload(
        audio, max_bytes=container.settings.max_audio_bytes, default_name="voice"
    )
    detected = detect_audio(incoming.content)
    transcript = await container.ai.transcribe(
        incoming.content, filename=f"voice.{detected.extension}", language=user.language
    )
    text = transcript.text.strip()
    if not text:
        raise AppError(ErrorCode.AUDIO_EMPTY)
    return TranscriptionOut(text=text, text_fr=await container.ai.to_french(text, user.language))
