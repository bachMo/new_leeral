from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import ENV_FILES

ReasoningEffort = Literal["none", "minimal", "low", "medium", "high"]


class AiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    ai_provider: Literal["mock", "real"] = "mock"

    asr_base_url: str = ""
    asr_api_key: SecretStr = SecretStr("")
    asr_model: str = "m-kiriku-asr"
    asr_timeout_seconds: float = 60.0
    asr_max_retries: int = 2

    tts_base_url: str = ""
    tts_api_key: SecretStr = SecretStr("")
    tts_model: str = "kiriku-tts"
    tts_timeout_seconds: float = 30.0
    tts_max_retries: int = 2
    tts_max_input_chars: int = 500
    tts_concurrency: int = 3
    tts_speed: float | None = None

    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: SecretStr = SecretStr("")

    reader_model_a: str = "qwen/qwen3.8-27b"
    reader_model_a_reasoning_effort: ReasoningEffort = "none"
    reader_model_b: str = "meta/muse-glimmer-30b"
    reader_model_b_reasoning_effort: ReasoningEffort = "minimal"
    reader_http_provider: str = "deepinfra"
    reader_timeout_seconds: float = 90.0
    reader_max_retries: int = 2
    reader_max_image_bytes: int = 8_000_000
    reader_max_image_side: int = 2200

    translator_model_primary: str = "google/gemini-2.5-flash-lite"
    translator_model_primary_reasoning_effort: ReasoningEffort = "none"
    translator_model_fallback: str = "openai/gpt-5-mini"
    translator_model_fallback_reasoning_effort: ReasoningEffort = "minimal"
    translator_timeout_seconds: float = 45.0
    translator_max_retries: int = 2
    translator_max_attempts_per_sentence: int = 2

    llm_model_short: str = "qwen/qwen3.8-27b"
    llm_model_short_reasoning_effort: ReasoningEffort = "none"
    llm_model_long: str = "google/gemini-3.1-pro-preview"
    llm_model_long_reasoning_effort: ReasoningEffort = "minimal"
    llm_long_document_token_threshold: int = 8000
    llm_timeout_seconds: float = 90.0
    llm_max_retries: int = 2

    quality_min_width: int = 300
    quality_min_height: int = 300
    quality_blur_threshold: float = 100.0
    quality_min_brightness: float = 40.0

    min_page_text_chars: int = 40
    mp3_bitrate_kbps: int = 64


@lru_cache
def get_ai_settings() -> AiSettings:
    return AiSettings()