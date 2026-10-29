import io
import subprocess
import tempfile
import threading
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from settings import Settings, Voice

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 30 * SAMPLE_RATE
MAX_NEW_TOKENS = 440
ASR_LANGUAGES = {"wo": "wo", "ff": "pu", "pu": "pu", "srr": "se", "sr": "se", "se": "se"}
DEFAULT_ASR_LANGUAGE = "wo"


class AudioDecodeError(ValueError):
    pass


def decode_audio(data: bytes, suffix: str) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=suffix or ".audio") as source:
        source.write(data)
        source.flush()
        result = subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-loglevel",
                "error",
                "-i",
                source.name,
                "-f",
                "s16le",
                "-ac",
                "1",
                "-ar",
                str(SAMPLE_RATE),
                "pipe:1",
            ],
            capture_output=True,
            check=False,
        )
    if result.returncode != 0 or not result.stdout:
        raise AudioDecodeError(result.stderr.decode(errors="replace").strip() or "empty audio")
    return np.frombuffer(result.stdout, np.int16).astype(np.float32) / 32768.0


class SpeechRecognizer:
    def __init__(self, settings: Settings) -> None:
        import ctranslate2
        from transformers import WhisperProcessor

        self._ctranslate2 = ctranslate2
        self._model = ctranslate2.models.Whisper(
            str(settings.asr_ct2_dir),
            device="cpu",
            compute_type="int8",
            intra_threads=settings.threads,
        )
        self._processor = WhisperProcessor.from_pretrained(str(settings.asr_source_dir))
        self._beam_size = settings.asr_beam_size
        self._lock = threading.Lock()
        tokenizer = self._processor.tokenizer
        for code in set(ASR_LANGUAGES.values()):
            token = f"<|{code}|>"
            if tokenizer.convert_tokens_to_ids(token) == tokenizer.unk_token_id:
                raise RuntimeError(f"ASR tokenizer has no {token} token")

    @staticmethod
    def prompt(language: str | None) -> list[str]:
        code = ASR_LANGUAGES.get((language or "").lower(), DEFAULT_ASR_LANGUAGE)
        return ["<|startoftranscript|>", f"<|{code}|>", "<|transcribe|>", "<|notimestamps|>"]

    def transcribe(self, audio: np.ndarray, language: str | None) -> str:
        chunks = [audio[i : i + CHUNK_SAMPLES] for i in range(0, len(audio), CHUNK_SAMPLES)] or [
            audio
        ]
        features = self._processor.feature_extractor(
            chunks, sampling_rate=SAMPLE_RATE, return_tensors="np"
        ).input_features
        batch = self._ctranslate2.StorageView.from_array(
            np.ascontiguousarray(features, dtype=np.float32)
        )
        prompt = self.prompt(language)
        with self._lock:
            results = self._model.generate(
                batch,
                [prompt] * len(chunks),
                beam_size=self._beam_size,
                max_length=len(prompt) + MAX_NEW_TOKENS,
            )
        tokenizer = self._processor.tokenizer
        parts = (
            tokenizer.decode(r.sequences_ids[0], skip_special_tokens=True).strip() for r in results
        )
        return " ".join(part for part in parts if part)


class VoiceSynthesizer:
    def __init__(self, voice: Voice, model_dir: Path) -> None:
        from TTS.utils.synthesizer import Synthesizer

        self.voice = voice
        self._synthesizer = Synthesizer(
            tts_checkpoint=str(model_dir / "model.pth"),
            tts_config_path=str(model_dir / "config.json"),
            use_cuda=False,
        )
        self._model = self._synthesizer.tts_model
        self._base_length_scale = float(getattr(self._model, "length_scale", 1.0))
        self._lock = threading.Lock()

    @property
    def sample_rate(self) -> int:
        return int(self._synthesizer.output_sample_rate)

    def synthesize(self, text: str, speed: float | None) -> bytes:
        rate = speed if speed and speed > 0 else self.voice.default_speed
        with self._lock:
            self._model.length_scale = self._base_length_scale / rate
            try:
                samples = self._synthesizer.tts(text.lower())
            finally:
                self._model.length_scale = self._base_length_scale
        pcm = np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0)
        buffer = io.BytesIO()
        wavfile.write(buffer, self.sample_rate, (pcm * 32767).astype(np.int16))
        return buffer.getvalue()
