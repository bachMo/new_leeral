import io
import math
import wave
from collections.abc import Sequence

import lameenc

from app.ai.contracts import SpeechAudio
from app.ai.errors import AiOutputError


def silent_wav(duration_s: float, sample_rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * int(sample_rate * duration_s))
    return buffer.getvalue()


def concat_wav(
    chunks: Sequence[bytes], *, pause_s: float = 0.25, lead_s: float = 0.0, tail_s: float = 0.0
) -> bytes:
    if not chunks:
        raise AiOutputError("no audio chunk to concatenate")
    frames: list[bytes] = []
    formats: set[tuple[int, int, int]] = set()
    for chunk in chunks:
        with wave.open(io.BytesIO(chunk), "rb") as handle:
            formats.add((handle.getnchannels(), handle.getsampwidth(), handle.getframerate()))
            frames.append(handle.readframes(handle.getnframes()))
    if len(formats) != 1:
        raise AiOutputError("audio chunks have different formats")
    channels, sample_width, sample_rate = formats.pop()
    frame_size = sample_width * channels

    def silence(seconds: float) -> bytes:
        return b"\x00" * int(sample_rate * seconds) * frame_size

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(sample_width)
        output.setframerate(sample_rate)
        output.writeframes(silence(lead_s) + silence(pause_s).join(frames) + silence(tail_s))
    return buffer.getvalue()


def wav_to_speech(wav_bytes: bytes, *, bitrate_kbps: int) -> SpeechAudio:
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            sample_rate = handle.getframerate()
            frame_count = handle.getnframes()
            pcm = handle.readframes(frame_count)
    except (wave.Error, EOFError) as exc:
        raise AiOutputError(f"invalid wav audio: {exc}") from exc
    if sample_width != 2:
        raise AiOutputError(f"unsupported sample width: {sample_width}")
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(bitrate_kbps)
    encoder.set_in_sample_rate(sample_rate)
    encoder.set_channels(channels)
    encoder.set_quality(2)
    content = bytes(encoder.encode(pcm) + encoder.flush())
    duration_s = max(1, math.ceil(frame_count / sample_rate)) if sample_rate else 1
    return SpeechAudio(content=content, duration_s=duration_s)
