import io
import uuid

import pymupdf
import pytest
from PIL import Image

from app.core.errors import AppError, ErrorCode
from app.integrations.storage import promoted_key
from app.services.media import FileKind, build_pages, detect, safe_filename


def jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buffer, format="JPEG")
    return buffer.getvalue()


def pdf(text: str) -> bytes:
    with pymupdf.open() as document:
        document.new_page().insert_text((50, 80), text)
        return bytes(document.tobytes())


def test_files_are_detected_from_their_content() -> None:
    assert detect(jpeg()).kind is FileKind.IMAGE
    assert detect(pdf("Bonjour")).kind is FileKind.PDF


def test_unknown_content_is_rejected() -> None:
    with pytest.raises(AppError) as error:
        detect(b"MZ\x90\x00")

    assert error.value.code is ErrorCode.FILE_TYPE_NOT_SUPPORTED


def test_text_pdf_pages_keep_their_text() -> None:
    content = pdf("Facture n° 118. Montant à payer : 12 500 F CFA avant le 30/10/2026.")

    pages = build_pages([(detect(content), content, "facture.pdf")], max_pages=5)

    assert len(pages) == 1
    assert pages[0].image is None
    assert "12 500" in (pages[0].text or "")


def test_filenames_cannot_escape_their_folder() -> None:
    assert safe_filename("../../etc/passwd", "file") == "passwd"
    assert safe_filename("..\\..\\boot.ini", "file") == "boot.ini"
    assert safe_filename(None, "file") == "file"


def test_guest_keys_move_under_the_account_prefix() -> None:
    account = uuid.uuid4()
    key = "tmp/1234/documents/abcd/files/00.jpg"

    assert promoted_key(key, account) == f"users/{account}/documents/abcd/files/00.jpg"
    assert promoted_key("shared/words/x.mp3", account) == "shared/words/x.mp3"
