import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("leeral.whatsapp.voice")

VOICE_MIME_TYPE = "audio/ogg; codecs=opus"
VOICE_BITRATE = "16k"
VOICE_SAMPLE_RATE = 48000
VOICE_TIMEOUT_SECONDS = 60


@dataclass(frozen=True, slots=True)
class OutgoingAudio:
    content: bytes
    mime_type: str
    filename: str
    voice: bool


class VoiceNoteError(Exception):
    pass


async def as_voice_note(*segments: bytes) -> OutgoingAudio:
    if not segments:
        raise ValueError("a voice note needs at least one audio segment")
    fallback = OutgoingAudio(segments[0], "audio/mpeg", "leeral.mp3", voice=False)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        logger.warning("voice_note_unavailable", extra={"reason": "ffmpeg_missing"})
        return fallback
    with tempfile.TemporaryDirectory(prefix="leeral-voice-") as workdir:
        inputs = _write_segments(Path(workdir), segments)
        try:
            ogg = await _encode(ffmpeg, inputs)
        except VoiceNoteError as exc:
            logger.warning("voice_note_failed", extra={"reason": str(exc)})
            return fallback
    return OutgoingAudio(ogg, VOICE_MIME_TYPE, "leeral.ogg", voice=True)


def _write_segments(workdir: Path, segments: tuple[bytes, ...]) -> list[Path]:
    paths = []
    for index, segment in enumerate(segments):
        path = workdir / f"segment-{index}.mp3"
        path.write_bytes(segment)
        paths.append(path)
    return paths


def _command(ffmpeg: str, inputs: list[Path]) -> list[str]:
    command = [ffmpeg, "-hide_banner", "-loglevel", "error"]
    for path in inputs:
        command += ["-i", str(path)]
    resampled = "".join(
        f"[{index}:a]aresample={VOICE_SAMPLE_RATE},aformat=channel_layouts=mono[a{index}];"
        for index in range(len(inputs))
    )
    joined = "".join(f"[a{index}]" for index in range(len(inputs)))
    command += [
        "-filter_complex",
        f"{resampled}{joined}concat=n={len(inputs)}:v=0:a=1[voice]",
        "-map",
        "[voice]",
        "-c:a",
        "libopus",
        "-b:a",
        VOICE_BITRATE,
        "-application",
        "voip",
        "-f",
        "ogg",
        "pipe:1",
    ]
    return command


async def _encode(ffmpeg: str, inputs: list[Path]) -> bytes:
    process = await asyncio.create_subprocess_exec(
        *_command(ffmpeg, inputs),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        ogg, error = await asyncio.wait_for(process.communicate(), VOICE_TIMEOUT_SECONDS)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise VoiceNoteError("timeout") from None
    if process.returncode != 0 or not ogg:
        raise VoiceNoteError(error.decode(errors="replace")[-200:].strip() or "empty output")
    return ogg
