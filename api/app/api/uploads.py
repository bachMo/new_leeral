from fastapi import UploadFile

from app.core.errors import AppError, ErrorCode
from app.services.media import IncomingFile, safe_filename


async def read_upload(upload: UploadFile, *, max_bytes: int, default_name: str) -> IncomingFile:
    content = await upload.read(max_bytes + 1)
    await upload.close()
    if len(content) > max_bytes:
        raise AppError(ErrorCode.FILE_TOO_LARGE, fields={"max_bytes": max_bytes})
    return IncomingFile(filename=safe_filename(upload.filename, default_name), content=content)
