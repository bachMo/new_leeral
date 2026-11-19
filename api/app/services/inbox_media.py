import asyncio
import io
import mimetypes
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePath

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import AppError, ErrorCode
from app.integrations.whatsapp.voice import as_voice_note
from app.services.media import safe_filename

MB = 1024 * 1024
IMAGE_MAX_BYTES = 5 * MB
VIDEO_MAX_BYTES = 16 * MB
AUDIO_MAX_BYTES = 16 * MB
IMAGE_MAX_SIDE = 2560
JPEG_QUALITIES = (85, 75, 65, 55)

IMAGE_TYPES = frozenset({"image/jpeg", "image/png"})
VIDEO_TYPES = frozenset({"video/mp4", "video/3gpp"})
AUDIO_TYPES = frozenset({"audio/aac", "audio/amr", "audio/mpeg", "audio/mp4", "audio/ogg"})
DOCUMENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
    }
)


class OutgoingKind(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    DOCUMENT = "document"
    CONTACT = "contact"
    TEMPLATE = "template"


MEDIA_KINDS = frozenset(
    {
        OutgoingKind.IMAGE,
        OutgoingKind.VIDEO,
        OutgoingKind.AUDIO,
        OutgoingKind.VOICE,
        OutgoingKind.DOCUMENT,
    }
)


@dataclass(frozen=True, slots=True)
class PreparedMedia:
    content: bytes
    mime_type: str
    filename: str
    wa_kind: str
    voice: bool = False


def resolve_mime(declared: str | None, filename: str) -> str:
    base = (declared or "").split(";", maxsplit=1)[0].strip().lower()
    if base and base != "application/octet-stream":
        return base
    guessed = mimetypes.guess_type(filename)[0]
    return (guessed or "application/octet-stream").lower()


def _unsupported(allowed: str) -> AppError:
    return AppError(ErrorCode.FILE_TYPE_NOT_SUPPORTED, fields={"allowed": allowed})


def _too_large(limit: int) -> AppError:
    return AppError(ErrorCode.FILE_TOO_LARGE, fields={"max_mb": limit // MB})


def _is_native_image(content: bytes, mime: str) -> bool:
    if mime == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if mime == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    return False


def _to_jpeg(content: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(content)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise _unsupported("JPEG, PNG, WebP") from exc
    image.thumbnail((IMAGE_MAX_SIDE, IMAGE_MAX_SIDE))
    for quality in JPEG_QUALITIES:
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True)
        if output.tell() <= IMAGE_MAX_BYTES:
            return output.getvalue()
    raise _too_large(IMAGE_MAX_BYTES)


async def _image(content: bytes, mime: str, filename: str) -> PreparedMedia:
    if _is_native_image(content, mime) and len(content) <= IMAGE_MAX_BYTES:
        return PreparedMedia(content, mime, filename, "image")
    converted = await asyncio.to_thread(_to_jpeg, content)
    return PreparedMedia(converted, "image/jpeg", f"{PurePath(filename).stem}.jpg", "image")


async def _voice(content: bytes) -> PreparedMedia:
    encoded = await as_voice_note(content)
    if not encoded.voice:
        raise _unsupported("audio")
    if len(encoded.content) > AUDIO_MAX_BYTES:
        raise _too_large(AUDIO_MAX_BYTES)
    return PreparedMedia(encoded.content, "audio/ogg", "note-vocale.ogg", "audio", voice=True)


async def prepare_media(
    kind: OutgoingKind,
    content: bytes,
    declared_mime: str | None,
    filename: str | None,
    max_upload_bytes: int,
) -> PreparedMedia:
    if not content:
        raise AppError(ErrorCode.FILE_MISSING)
    if len(content) > max_upload_bytes:
        raise _too_large(max_upload_bytes)
    name = safe_filename(filename, "fichier")
    mime = resolve_mime(declared_mime, name)
    if kind is OutgoingKind.IMAGE:
        return await _image(content, mime, name)
    if kind is OutgoingKind.VIDEO:
        if mime not in VIDEO_TYPES:
            raise _unsupported("MP4, 3GP")
        if len(content) > VIDEO_MAX_BYTES:
            raise _too_large(VIDEO_MAX_BYTES)
        return PreparedMedia(content, mime, name, "video")
    if kind is OutgoingKind.AUDIO and mime in AUDIO_TYPES and len(content) <= AUDIO_MAX_BYTES:
        return PreparedMedia(content, mime, name, "audio")
    if kind in {OutgoingKind.AUDIO, OutgoingKind.VOICE}:
        return await _voice(content)
    if kind is OutgoingKind.DOCUMENT:
        if mime not in DOCUMENT_TYPES:
            raise _unsupported("PDF, Word, Excel, PowerPoint, TXT")
        return PreparedMedia(content, mime, name, "document")
    raise _unsupported(kind.value)
