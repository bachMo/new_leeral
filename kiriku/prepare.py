import logging
import shutil
import sys

from huggingface_hub import snapshot_download

from settings import Settings, load_settings

log = logging.getLogger("kiriku.prepare")

TTS_FILES = ("model.pth", "config.json")
ASR_PATTERNS = ["*.json", "*.safetensors", "*.txt"]
ASR_KEEP = (".json", ".txt")


def download_voices(settings: Settings) -> None:
    for voice in settings.voices:
        target = settings.voice_dir(voice)
        if all((target / name).exists() for name in TTS_FILES):
            continue
        log.info("downloading %s", voice.repo_id)
        snapshot_download(
            repo_id=voice.repo_id,
            local_dir=target,
            allow_patterns=list(TTS_FILES),
            token=settings.hf_token,
        )


def prepare_asr(settings: Settings) -> None:
    if (settings.asr_ct2_dir / "model.bin").exists():
        return
    source = settings.asr_source_dir
    log.info("downloading %s", settings.asr_repo_id)
    snapshot_download(
        repo_id=settings.asr_repo_id,
        local_dir=source,
        allow_patterns=ASR_PATTERNS,
        token=settings.hf_token,
    )
    from ctranslate2.converters import TransformersConverter

    log.info("converting ASR to CTranslate2 int8")
    tmp = settings.asr_ct2_dir.with_name(settings.asr_ct2_dir.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    TransformersConverter(str(source), load_as_float16=True, low_cpu_mem_usage=True).convert(
        str(tmp), quantization="int8", force=True
    )
    tmp.rename(settings.asr_ct2_dir)
    for path in source.iterdir():
        if path.is_file() and path.suffix not in ASR_KEEP:
            path.unlink()
    log.info("ASR ready")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = load_settings()
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    try:
        download_voices(settings)
        prepare_asr(settings)
    except Exception as exc:
        hint = "" if settings.hf_token else " HF_TOKEN is empty in .env."
        log.error("model preparation failed: %s.%s", exc, hint)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
