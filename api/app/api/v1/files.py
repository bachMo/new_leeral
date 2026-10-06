import mimetypes

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api.deps import Container
from app.core.errors import AppError, ErrorCode
from app.integrations.storage import LocalStorage

router = APIRouter(prefix="/files", tags=["files"], include_in_schema=False)


@router.get("/{key:path}")
async def read_local_file(
    key: str, expires: int, signature: str, container: Container
) -> FileResponse:
    storage = container.storage
    if not isinstance(storage, LocalStorage) or not storage.verify(key, expires, signature):
        raise AppError(ErrorCode.NOT_FOUND)
    path = storage.path_for(key)
    if not path.is_file():
        raise AppError(ErrorCode.NOT_FOUND)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)
