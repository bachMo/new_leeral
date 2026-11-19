import io
import shutil
import subprocess

import pytest
from PIL import Image

from app.core.errors import AppError, ErrorCode
from app.services.inbox_media import IMAGE_MAX_BYTES, OutgoingKind, prepare_media

LIMIT = 25 * 1024 * 1024


def _image(fmt: str, size: tuple[int, int] = (64, 48)) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", size, (200, 120, 40)).save(output, format=fmt)
    return output.getvalue()


async def test_png_is_sent_as_is() -> None:
    content = _image("PNG")

    prepared = await prepare_media(OutgoingKind.IMAGE, content, "image/png", "photo.png", LIMIT)

    assert prepared.content == content
    assert (prepared.mime_type, prepared.wa_kind) == ("image/png", "image")


async def test_webp_is_converted_to_jpeg() -> None:
    prepared = await prepare_media(
        OutgoingKind.IMAGE, _image("WEBP"), "image/webp", "capture.webp", LIMIT
    )

    assert prepared.mime_type == "image/jpeg"
    assert prepared.filename == "capture.jpg"
    assert prepared.content.startswith(b"\xff\xd8\xff")


async def test_large_photo_is_recompressed_under_the_whatsapp_limit() -> None:
    noisy = Image.effect_noise((3000, 3000), 120).convert("RGB")
    output = io.BytesIO()
    noisy.save(output, format="PNG")
    assert output.tell() > IMAGE_MAX_BYTES

    prepared = await prepare_media(
        OutgoingKind.IMAGE, output.getvalue(), "image/png", "grand.png", LIMIT
    )

    assert len(prepared.content) <= IMAGE_MAX_BYTES
    assert prepared.mime_type == "image/jpeg"


async def test_image_with_wrong_content_is_refused() -> None:
    with pytest.raises(AppError) as error:
        await prepare_media(OutgoingKind.IMAGE, b"not an image", "image/png", "x.png", LIMIT)

    assert error.value.code is ErrorCode.FILE_TYPE_NOT_SUPPORTED


async def test_pdf_document_keeps_its_name() -> None:
    prepared = await prepare_media(
        OutgoingKind.DOCUMENT, b"%PDF-1.4 test", None, "../facture juin.pdf", LIMIT
    )

    assert (prepared.mime_type, prepared.filename, prepared.wa_kind) == (
        "application/pdf",
        "facture juin.pdf",
        "document",
    )


async def test_executable_document_is_refused() -> None:
    with pytest.raises(AppError) as error:
        await prepare_media(
            OutgoingKind.DOCUMENT, b"MZ...", "application/x-msdownload", "a.exe", LIMIT
        )

    assert error.value.code is ErrorCode.FILE_TYPE_NOT_SUPPORTED


async def test_video_must_be_mp4_or_3gp() -> None:
    with pytest.raises(AppError) as error:
        await prepare_media(OutgoingKind.VIDEO, b"....", "video/quicktime", "a.mov", LIMIT)

    assert error.value.code is ErrorCode.FILE_TYPE_NOT_SUPPORTED


async def test_upload_over_the_limit_is_refused() -> None:
    with pytest.raises(AppError) as error:
        await prepare_media(OutgoingKind.DOCUMENT, b"x" * 11, "text/plain", "a.txt", 10)

    assert error.value.code is ErrorCode.FILE_TOO_LARGE


async def test_empty_upload_is_refused() -> None:
    with pytest.raises(AppError) as error:
        await prepare_media(OutgoingKind.IMAGE, b"", "image/png", "a.png", LIMIT)

    assert error.value.code is ErrorCode.FILE_MISSING


FFMPEG = shutil.which("ffmpeg")


@pytest.fixture
def browser_recording() -> bytes:
    assert FFMPEG is not None
    command = [FFMPEG, "-hide_banner", "-loglevel", "error", "-f", "lavfi"]
    command += ["-i", "sine=frequency=440:duration=1", "-c:a", "libopus", "-f", "webm", "pipe:1"]
    return subprocess.run(command, capture_output=True, check=True).stdout  # noqa: S603


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg is required")
async def test_browser_recording_becomes_a_whatsapp_voice_note(browser_recording: bytes) -> None:
    prepared = await prepare_media(
        OutgoingKind.VOICE, browser_recording, "audio/webm", "blob", LIMIT
    )

    assert prepared.voice is True
    assert prepared.mime_type == "audio/ogg"
    assert prepared.content.startswith(b"OggS")
