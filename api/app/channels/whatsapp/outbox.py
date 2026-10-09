import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.languages import Language
from app.core.logging import mask_phone
from app.integrations.storage import FileStorage
from app.integrations.whatsapp.client import ReplyButton, WhatsAppClient, WhatsAppError
from app.integrations.whatsapp.voice import as_voice_note
from app.models import WhatsAppChannel, WhatsAppMessage
from app.models.enums import WhatsAppDirection, WhatsAppMessageStatus, WhatsAppMessageType
from app.repositories.system import UiPromptRepository
from app.services.ui_prompt_catalog import prompt_catalog

logger = logging.getLogger("leeral.whatsapp.outbox")


class WhatsAppOutbox:
    def __init__(
        self,
        session: AsyncSession,
        client: WhatsAppClient,
        storage: FileStorage,
        channel: WhatsAppChannel,
        recipient: str,
        user_id: uuid.UUID | None,
    ) -> None:
        self._session = session
        self._client = client
        self._storage = storage
        self._channel = channel
        self._recipient = recipient
        self._user_id = user_id

    async def text(self, body: str) -> WhatsAppMessage | None:
        return await self._deliver(
            WhatsAppMessageType.TEXT,
            body,
            lambda: self._client.send_text(self._channel.phone_number_id, self._recipient, body),
        )

    async def buttons(self, body: str, buttons: list[ReplyButton]) -> WhatsAppMessage | None:
        return await self._deliver(
            WhatsAppMessageType.INTERACTIVE,
            body,
            lambda: self._client.send_buttons(
                self._channel.phone_number_id, self._recipient, body, buttons
            ),
        )

    async def audio(
        self, key: str, *extra_keys: str, caption: str | None = None
    ) -> WhatsAppMessage | None:
        segments = await asyncio.gather(*(self._storage.get(item) for item in (key, *extra_keys)))
        outgoing = await as_voice_note(*segments)
        return await self._deliver(
            WhatsAppMessageType.AUDIO,
            caption,
            lambda: self._client.send_audio(
                self._channel.phone_number_id,
                self._recipient,
                outgoing.content,
                outgoing.mime_type,
                outgoing.filename,
                voice=outgoing.voice,
            ),
            media_key=key,
        )

    async def document(self, key: str, filename: str, caption: str) -> WhatsAppMessage | None:
        content = await self._storage.get(key)
        return await self._deliver(
            WhatsAppMessageType.DOCUMENT,
            caption,
            lambda: self._client.send_document(
                self._channel.phone_number_id,
                self._recipient,
                content,
                "application/pdf",
                filename,
                caption,
            ),
            media_key=key,
        )

    async def prompt(self, key: str, language: Language) -> None:
        stored = await self.prompt_audio_key(key, language)
        if stored is not None:
            await self.audio(stored)
            return
        text = prompt_catalog().get(key)
        if text:
            await self.text(text)

    async def prompt_audio_key(self, key: str, language: Language) -> str | None:
        stored = await UiPromptRepository(self._session).find(key, language)
        return stored.audio_key if stored is not None else None

    async def _deliver(
        self,
        message_type: WhatsAppMessageType,
        body: str | None,
        send: Callable[[], Awaitable[str]],
        *,
        media_key: str | None = None,
    ) -> WhatsAppMessage | None:
        try:
            wa_message_id = await send()
        except WhatsAppError as exc:
            logger.warning(
                "whatsapp_send_failed",
                extra={"to": mask_phone(self._recipient), "status": exc.status_code},
            )
            return None
        record = WhatsAppMessage(
            user_id=self._user_id,
            wa_phone=self._recipient,
            channel_id=self._channel.id,
            direction=WhatsAppDirection.OUTBOUND,
            wa_message_id=wa_message_id,
            type=message_type,
            body_text=body,
            media_key=media_key,
            status=WhatsAppMessageStatus.SENT,
        )
        self._session.add(record)
        return record
