import mimetypes

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.storage import FileStorage
from app.integrations.whatsapp.client import WhatsAppClient
from app.models import User, WhatsAppMessage
from app.services import storage_keys

_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/aac": "aac",
    "audio/amr": "amr",
    "video/mp4": "mp4",
    "video/3gpp": "3gp",
    "application/pdf": "pdf",
    "text/plain": "txt",
}


def extension_for(mime_type: str) -> str:
    base = mime_type.split(";", maxsplit=1)[0].strip().lower()
    if base in _EXTENSIONS:
        return _EXTENSIONS[base]
    guessed = mimetypes.guess_extension(base) if base else None
    return guessed.lstrip(".") if guessed else "bin"


class MediaArchiver:
    def __init__(self, session: AsyncSession, client: WhatsAppClient, storage: FileStorage) -> None:
        self._session = session
        self._client = client
        self._storage = storage

    async def archive(self, message: WhatsAppMessage) -> bool:
        if message.media_key is not None or message.wa_media_id is None:
            return False
        media = await self._client.download_media(message.wa_media_id)
        user = await self._session.get(User, message.user_id) if message.user_id else None
        mime_type = media.mime_type or message.media_mime or "application/octet-stream"
        key = storage_keys.whatsapp_media(user, str(message.id), extension_for(mime_type))
        await self._storage.put(key, media.content, mime_type)
        message.media_key = key
        message.media_mime = mime_type
        return True
