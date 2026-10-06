import asyncio
import io
import logging
from typing import Any, Literal

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, ValidationError

from app.ai.contracts import PageInput
from app.ai.errors import AiError, AiInputError, AiOutputError
from app.ai.real import prompts
from app.ai.real.clients.openrouter import ModelProfile, OpenRouterClient, image_part, text_part
from app.ai.settings import AiSettings

logger = logging.getLogger("leeral.ai.pages")

MAX_TEXT_PAGE_CHARS = 12_000

DocumentType = Literal[
    "prescription",
    "lab_result",
    "invoice",
    "contract",
    "school",
    "bank",
    "administrative",
    "letter",
    "unknown",
]


class Classification(BaseModel):
    document_type: DocumentType = "unknown"
    document_language: Literal["fr", "en", "mixed", "unknown"] = "unknown"
    confident: bool = False


def prepare_image(image: bytes, *, max_side: int, max_bytes: int) -> tuple[bytes, str]:
    try:
        with Image.open(io.BytesIO(image)) as opened:
            picture = ImageOps.exif_transpose(opened).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise AiInputError("image cannot be decoded") from exc
    picture.thumbnail((max_side, max_side))
    for quality in (90, 80, 70, 60):
        buffer = io.BytesIO()
        picture.save(buffer, format="JPEG", quality=quality, optimize=True)
        if buffer.tell() <= max_bytes:
            return buffer.getvalue(), "image/jpeg"
    raise AiInputError("image remains too large after compression")


class PageReader:
    def __init__(
        self,
        client: OpenRouterClient,
        settings: AiSettings,
        model_a: ModelProfile,
        model_b: ModelProfile,
    ) -> None:
        self._client = client
        self._settings = settings
        self._model_a = model_a
        self._model_b = model_b

    def prepare(self, page: PageInput) -> list[dict[str, Any]]:
        if page.image is None:
            raise AiInputError("page has no image")
        image, mime_type = prepare_image(
            page.image,
            max_side=self._settings.reader_max_image_side,
            max_bytes=self._settings.reader_max_image_bytes,
        )
        return [image_part(image, mime_type)]

    def content(
        self, page: PageInput, *, image_prompt: str, text_prompt: str
    ) -> list[dict[str, Any]]:
        if page.image is not None:
            return [text_part(image_prompt), *self.prepare(page)]
        text = (page.text or "")[:MAX_TEXT_PAGE_CHARS]
        return [text_part(text_prompt.format(text=text))]

    async def classify(self, page: PageInput) -> Classification:
        content = self.content(
            page, image_prompt=prompts.CLASSIFY_IMAGE, text_prompt=prompts.CLASSIFY_TEXT
        )
        results = await asyncio.gather(
            self._classify_once(self._model_a, content),
            self._classify_once(self._model_b, content),
            return_exceptions=True,
        )
        readings = [result for result in results if isinstance(result, Classification)]
        if not readings:
            failure = results[0]
            raise (
                failure if isinstance(failure, AiError) else AiOutputError("classification failed")
            )
        if len(readings) == 1:
            return readings[0].model_copy(update={"confident": False})
        first, second = readings
        same_type = first.document_type == second.document_type
        return Classification(
            document_type=first.document_type if same_type else _safest_type(first, second),
            document_language=first.document_language
            if first.document_language == second.document_language
            else "unknown",
            confident=same_type and first.confident and second.confident,
        )

    async def transcribe(self, page: PageInput) -> str:
        content = [text_part(prompts.TRANSCRIBE_PAGE), *self.prepare(page)]
        text = await self._client.complete(
            self._model_a, content, operation="transcribe_page", max_tokens=4000
        )
        return text.strip()

    async def _classify_once(
        self, profile: ModelProfile, content: list[dict[str, Any]]
    ) -> Classification:
        raw = await self._client.complete_json(
            profile, content, operation="classify_page", max_tokens=200
        )
        try:
            return Classification.model_validate(raw)
        except ValidationError as exc:
            logger.warning("classification_invalid", extra={"model": profile.model})
            raise AiOutputError(
                f"classification output invalid: {exc.error_count()} errors"
            ) from exc


def _safest_type(first: Classification, second: Classification) -> DocumentType:
    if "prescription" in (first.document_type, second.document_type):
        return "prescription"
    return "unknown"
