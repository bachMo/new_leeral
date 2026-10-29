import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Voice:
    code: str
    repo_id: str
    default_speed: float


@dataclass(frozen=True, slots=True)
class Settings:
    models_dir: Path
    hf_token: str | None
    threads: int
    asr_repo_id: str
    asr_beam_size: int
    voices: tuple[Voice, ...]

    @property
    def asr_source_dir(self) -> Path:
        return self.models_dir / "asr-source"

    @property
    def asr_ct2_dir(self) -> Path:
        return self.models_dir / "asr-ct2-int8"

    def voice_dir(self, voice: Voice) -> Path:
        return self.models_dir / f"tts-{voice.code}"


def load_settings() -> Settings:
    return Settings(
        models_dir=Path(os.environ.get("KIRIKU_MODELS_DIR", "/models")),
        hf_token=os.environ.get("HF_TOKEN") or None,
        threads=int(os.environ.get("KIRIKU_THREADS") or os.cpu_count() or 1),
        asr_repo_id=os.environ.get("KIRIKU_ASR_REPO", "AIHubSN/M-Kiriku-ASR"),
        asr_beam_size=int(os.environ.get("KIRIKU_ASR_BEAM_SIZE", "5")),
        voices=(
            Voice("wo", os.environ.get("KIRIKU_TTS_WOLOF_REPO", "AIHubSN/Kiriku-Wolof-TTS"), 1.2),
            Voice("ff", os.environ.get("KIRIKU_TTS_PULAAR_REPO", "AIHubSN/Kiriku-Pulaar-TTS"), 1.0),
        ),
    )
