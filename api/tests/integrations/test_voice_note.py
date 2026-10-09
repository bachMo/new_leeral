import io
import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from app.ai.audio import wav_to_speech
from app.integrations.whatsapp import voice
from app.integrations.whatsapp.voice import VOICE_MIME_TYPE, as_voice_note


def _tone_mp3(seconds: float = 1.0, sample_rate: int = 16000) -> bytes:
    frames = b"".join(
        struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / sample_rate)))
        for i in range(int(sample_rate * seconds))
    )
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(frames)
    return wav_to_speech(buffer.getvalue(), bitrate_kbps=64).content


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
async def test_mp3_becomes_an_opus_voice_note() -> None:
    outgoing = await as_voice_note(_tone_mp3())

    assert outgoing.voice
    assert outgoing.mime_type == VOICE_MIME_TYPE
    assert outgoing.filename == "leeral.ogg"
    assert outgoing.content.startswith(b"OggS")
    assert b"OpusHead" in outgoing.content[:200]


async def test_without_ffmpeg_the_mp3_is_sent_as_audio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(voice.shutil, "which", lambda _: None)
    mp3 = _tone_mp3()

    outgoing = await as_voice_note(mp3)

    assert not outgoing.voice
    assert outgoing.content == mp3
    assert outgoing.mime_type == "audio/mpeg"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
async def test_unreadable_audio_falls_back_to_the_original() -> None:
    outgoing = await as_voice_note(b"not an audio file")

    assert not outgoing.voice
    assert outgoing.content == b"not an audio file"


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe is not installed")
async def test_several_segments_become_a_single_voice_note(tmp_path: Path) -> None:
    outgoing = await as_voice_note(_tone_mp3(1.0), _tone_mp3(1.5, sample_rate=22050))
    note = tmp_path / "note.ogg"
    note.write_bytes(outgoing.content)

    assert outgoing.voice
    assert _duration(note) == pytest.approx(2.5, abs=0.2)


async def test_without_segments_nothing_is_sent() -> None:
    with pytest.raises(ValueError, match="at least one"):
        await as_voice_note()


def _duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    assert ffprobe is not None
    result = subprocess.run(  # noqa: S603
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        check=True,
    )
    return float(result.stdout)
