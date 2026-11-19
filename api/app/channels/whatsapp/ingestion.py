import logging
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.channels.whatsapp.inbound_meta import (
    TYPE_MAP,
    inbound_body,
    inbound_meta,
    message_type,
)
from app.channels.whatsapp.threads import ensure_thread
from app.core.config import Settings
from app.db.unit_of_work import UnitOfWork
from app.integrations.whatsapp.payloads import ChangeValue, InboundMessage, WebhookPayload
from app.models import WhatsAppChannel, WhatsAppMessage
from app.models.enums import WhatsAppDirection, WhatsAppMessageStatus
from app.repositories.system import WhatsAppChannelRepository, WhatsAppMessageRepository
from app.workers.jobs import Job

logger = logging.getLogger("leeral.whatsapp.ingestion")

_STATUS_MAP = {
    "sent": WhatsAppMessageStatus.SENT,
    "delivered": WhatsAppMessageStatus.DELIVERED,
    "read": WhatsAppMessageStatus.READ,
    "failed": WhatsAppMessageStatus.FAILED,
}
_STATUS_RANK = {
    WhatsAppMessageStatus.SENT: 1,
    WhatsAppMessageStatus.DELIVERED: 2,
    WhatsAppMessageStatus.READ: 3,
    WhatsAppMessageStatus.FAILED: 4,
}


class WebhookIngestor:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings
        self._channels = WhatsAppChannelRepository(uow.session)
        self._messages = WhatsAppMessageRepository(uow.session)

    async def ingest(self, payload: WebhookPayload) -> int:
        accepted = 0
        for entry in payload.entry:
            for change in entry.changes:
                if change.field != "messages":
                    continue
                channel = await self._channel(change.value)
                if channel is None:
                    continue
                await self._apply_statuses(change.value)
                for message in change.value.messages:
                    accepted += await self._accept(channel, change.value, message)
        await self._uow.commit()
        return accepted

    async def _channel(self, value: ChangeValue) -> WhatsAppChannel | None:
        phone_number_id = value.metadata.phone_number_id
        channel = await self._channels.by_phone_number_id(phone_number_id)
        if channel is None and phone_number_id == self._settings.whatsapp_default_phone_id:
            channel = self._channels.add(
                WhatsAppChannel(
                    phone_number_id=phone_number_id,
                    display_number=value.metadata.display_phone_number or phone_number_id,
                )
            )
            await self._channels.flush()
        if channel is None or not channel.is_active:
            logger.warning("whatsapp_unknown_channel", extra={"phone_number_id": phone_number_id})
            return None
        return channel

    async def _apply_statuses(self, value: ChangeValue) -> None:
        for update in value.statuses:
            status = _STATUS_MAP.get(update.status)
            record = await self._messages.by_wa_id(update.id)
            if record is None or status is None:
                continue
            if _STATUS_RANK.get(status, 0) < _STATUS_RANK.get(record.status, 0):
                continue
            record.status = status
            if update.errors:
                record.error = _status_error(update.errors[0])

    async def _accept(
        self, channel: WhatsAppChannel, value: ChangeValue, message: InboundMessage
    ) -> int:
        if await self._messages.by_wa_id(message.id) is not None:
            return 0
        if message.type not in TYPE_MAP:
            logger.info(
                "whatsapp_unsupported_message",
                extra={
                    "type": message.type,
                    "errors": [
                        {"code": error.get("code"), "title": error.get("title")}
                        for error in message.errors
                    ],
                },
            )
        media = message.any_media
        record = WhatsAppMessage(
            wa_phone=message.sender,
            channel_id=channel.id,
            direction=WhatsAppDirection.INBOUND,
            wa_message_id=message.id,
            type=message_type(message),
            body_text=inbound_body(message),
            wa_media_id=media.id if media else None,
            media_mime=media.mime_type if media else None,
            meta=inbound_meta(message),
            status=WhatsAppMessageStatus.RECEIVED,
        )
        try:
            async with self._uow.session.begin_nested():
                self._messages.add(record)
                await self._messages.flush()
        except IntegrityError:
            return 0
        await ensure_thread(self._uow.session, channel.id, message.sender)
        self._uow.defer(
            Job.HANDLE_WHATSAPP_MESSAGE,
            message_id=str(record.id),
            profile_name=value.contact_name(message.sender),
        )
        return 1


def _status_error(error: dict[str, Any]) -> str:
    title = error.get("title") or error.get("message") or "erreur inconnue"
    code = error.get("code")
    return (f"{code} · {title}" if code is not None else str(title))[:300]
