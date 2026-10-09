import asyncio
import logging
import shutil
from dataclasses import dataclass

logger = logging.getLogger("leeral.whatsapp.voice")

VOICE_MIME_TYPE = "audio/ogg; codecs=opus"
VOICE_BITRATE = "16k"
VOICE_TIMEOUT_SECONDS = 60


@dataclass(frozen=True, slots=True)
class OutgoingAudio:
    content: bytes
    mime_type: str
    filename: str
    voice: bool


async def as_voice_note(mp3: bytes) -> OutgoingAudio:
    fallback = OutgoingAudio(mp3, "audio/mpeg", "leeral.mp3", voice=False)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        logger.warning("voice_note_unavailable", extra={"reason": "ffmpeg_missing"})
        return fallback
    process = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "48000",
        "-c:a",
        "libopus",
        "-b:a",
        VOICE_BITRATE,
        "-application",
        "voip",
        "-f",
        "ogg",
        "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        ogg, error = await asyncio.wait_for(process.communicate(mp3), VOICE_TIMEOUT_SECONDS)
    except TimeoutError:
        process.kill()
        await process.wait()
        logger.warning("voice_note_failed", extra={"reason": "timeout"})
        return fallback
    if process.returncode != 0 or not ogg:
        logger.warning(
            "voice_note_failed",
            extra={"reason": error.decode(errors="replace")[-200:].strip()},
        )
        return fallback
    return OutgoingAudio(ogg, VOICE_MIME_TYPE, "leeral.ogg", voice=True)
