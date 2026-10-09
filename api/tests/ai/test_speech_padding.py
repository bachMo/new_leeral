import io
import wave

from app.ai.audio import concat_wav, silent_wav
from app.ai.real.speech import _with_final_stop


def _seconds(wav_bytes: bytes) -> float:
    with wave.open(io.BytesIO(wav_bytes), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def test_padding_surrounds_short_speech_with_silence() -> None:
    word = silent_wav(0.3)

    padded = concat_wav([word], lead_s=0.2, tail_s=0.4)

    assert _seconds(padded) == 0.9


def test_chunks_are_still_separated_by_a_pause() -> None:
    joined = concat_wav([silent_wav(0.5), silent_wav(0.5)], pause_s=0.25)

    assert _seconds(joined) == 1.25


def test_a_lone_word_gets_a_final_stop() -> None:
    assert _with_final_stop("jamono") == "jamono."
    assert _with_final_stop("Am na?") == "Am na?"
    assert _with_final_stop("Waaw.") == "Waaw."
