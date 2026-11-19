import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from app.channels.whatsapp.media_archive import extension_for
from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError, ErrorCode, NotFoundError
from app.core.phone import normalize_phone_number
from app.db.unit_of_work import UnitOfWork
from app.integrations.storage import FileStorage
from app.integrations.whatsapp.client import MAX_TEXT_LENGTH, WhatsAppClient, WhatsAppError
from app.models import AdminUser, User, WhatsAppChannel, WhatsAppMessage, WhatsAppThread
from app.models.enums import WhatsAppDirection, WhatsAppMessageStatus, WhatsAppMessageType
from app.repositories.inbox import WINDOW, InboxRepository
from app.schemas.inbox import MessageOut
from app.services import storage_keys
from app.services.inbox_media import MEDIA_KINDS, OutgoingKind, PreparedMedia, prepare_media
from app.services.inbox_service import InboxService

CONTACT_NAME_MAX_LENGTH = 100

_RECORD_TYPES = {
    "image": WhatsAppMessageType.IMAGE,
    "video": WhatsAppMessageType.VIDEO,
    "audio": WhatsAppMessageType.AUDIO,
    "document": WhatsAppMessageType.DOCUMENT,
}


@dataclass(frozen=True, slots=True)
class Upload:
    content: bytes
    content_type: str | None
    filename: str | None


@dataclass(frozen=True, slots=True)
class OutgoingMessage:
    kind: OutgoingKind
    text: str | None = None
    upload: Upload | None = None
    reply_to: uuid.UUID | None = None
    contact_name: str | None = None
    contact_phone: str | None = None


def _send_failed(exc: WhatsAppError) -> AppError:
    return AppError(
        ErrorCode.WHATSAPP_SEND_FAILED,
        fields={"reason": exc.details, "code": exc.error_code, "status": exc.status_code},
    )


class InboxSender:
    def __init__(
        self,
        uow: UnitOfWork,
        storage: FileStorage,
        client: WhatsAppClient,
        settings: Settings,
    ) -> None:
        self._uow = uow
        self._storage = storage
        self._client = client
        self._settings = settings
        self._repo = InboxRepository(uow.session)

    async def send(
        self, admin: AdminUser, thread_id: uuid.UUID, outgoing: OutgoingMessage
    ) -> MessageOut:
        thread = await self._repo.thread(thread_id)
        if thread is None:
            raise NotFoundError("thread")
        channel = await self._uow.session.get(WhatsAppChannel, thread.channel_id)
        if channel is None or not channel.is_active:
            raise NotFoundError("channel")
        now = utcnow()
        if outgoing.kind is not OutgoingKind.TEMPLATE:
            latest = await self._repo.last_inbound(thread)
            if latest is None or latest.created_at + WINDOW <= now:
                raise AppError(ErrorCode.WHATSAPP_WINDOW_CLOSED)
        reply_to = await self._reply_target(thread, outgoing.reply_to)
        record = await self._deliver(admin, thread, channel, outgoing, reply_to)
        pause_until = now + timedelta(minutes=self._settings.inbox_bot_pause_minutes)
        if thread.bot_paused_until is None or thread.bot_paused_until < pause_until:
            thread.bot_paused_until = pause_until
        await self._uow.commit()
        await self._uow.session.refresh(record)
        return (
            await InboxService(self._uow, self._storage, self._client).present(thread, [record])
        )[0]

    async def _reply_target(
        self, thread: WhatsAppThread, message_id: uuid.UUID | None
    ) -> WhatsAppMessage | None:
        if message_id is None:
            return None
        target = await self._repo.message_in_thread(thread, message_id)
        if target is None:
            raise NotFoundError("message")
        return target

    async def _deliver(
        self,
        admin: AdminUser,
        thread: WhatsAppThread,
        channel: WhatsAppChannel,
        outgoing: OutgoingMessage,
        reply_to: WhatsAppMessage | None,
    ) -> WhatsAppMessage:
        meta: dict[str, Any] = {}
        reply_wa_id = reply_to.wa_message_id if reply_to else None
        if reply_wa_id:
            meta["reply_to"] = reply_wa_id
        phone_id = channel.phone_number_id
        to = thread.wa_phone
        kind = outgoing.kind
        text = (outgoing.text or "").strip() or None
        if text and len(text) > MAX_TEXT_LENGTH:
            raise AppError(ErrorCode.VALIDATION_FAILED, fields={"text": "too long"})
        record = WhatsAppMessage(
            id=uuid.uuid4(),
            user_id=thread.user_id,
            wa_phone=to,
            channel_id=channel.id,
            direction=WhatsAppDirection.OUTBOUND,
            status=WhatsAppMessageStatus.SENT,
            admin_id=admin.id,
        )
        if kind is OutgoingKind.TEXT:
            if not text:
                raise AppError(ErrorCode.VALIDATION_FAILED, fields={"text": "required"})
            record.type = WhatsAppMessageType.TEXT
            record.body_text = text
            record.wa_message_id = await self._call(
                self._client.send_text(phone_id, to, text, reply_to=reply_wa_id)
            )
        elif kind is OutgoingKind.CONTACT:
            name, phone = self._contact(outgoing)
            record.type = WhatsAppMessageType.CONTACTS
            record.body_text = name
            meta["contacts"] = [{"name": name, "phones": [phone]}]
            record.wa_message_id = await self._call(
                self._client.send_contact(phone_id, to, name, phone, reply_to=reply_wa_id)
            )
        elif kind is OutgoingKind.TEMPLATE:
            template = self._settings.whatsapp_reminder_template
            record.type = WhatsAppMessageType.TEMPLATE
            record.template_name = template
            record.wa_message_id = await self._call(
                self._client.send_template(
                    phone_id, to, template, self._settings.whatsapp_template_language
                )
            )
        elif kind in MEDIA_KINDS:
            if outgoing.upload is None:
                raise AppError(ErrorCode.FILE_MISSING)
            prepared = await prepare_media(
                kind,
                outgoing.upload.content,
                outgoing.upload.content_type,
                outgoing.upload.filename,
                self._settings.inbox_max_upload_bytes,
            )
            await self._send_media(record, thread, prepared, text, reply_wa_id, phone_id, meta)
        else:
            raise AppError(ErrorCode.VALIDATION_FAILED, fields={"type": "unknown"})
        record.meta = meta or None
        self._uow.session.add(record)
        return record

    async def _send_media(
        self,
        record: WhatsAppMessage,
        thread: WhatsAppThread,
        prepared: PreparedMedia,
        caption: str | None,
        reply_wa_id: str | None,
        phone_id: str,
        meta: dict[str, Any],
    ) -> None:
        user = await self._uow.session.get(User, thread.user_id) if thread.user_id else None
        key = storage_keys.whatsapp_media(user, "admin", extension_for(prepared.mime_type))
        await self._storage.put(key, prepared.content, prepared.mime_type)
        try:
            wa_message_id = await self._client.send_media(
                phone_id,
                thread.wa_phone,
                prepared.wa_kind,
                prepared.content,
                prepared.mime_type,
                prepared.filename,
                caption=caption,
                voice=prepared.voice,
                reply_to=reply_wa_id,
            )
        except WhatsAppError as exc:
            await self._storage.delete([key])
            raise _send_failed(exc) from exc
        record.wa_message_id = wa_message_id
        record.type = _RECORD_TYPES[prepared.wa_kind]
        record.body_text = caption if prepared.wa_kind != "audio" else None
        record.media_key = key
        record.media_mime = prepared.mime_type
        if prepared.wa_kind == "document":
            meta["filename"] = prepared.filename
        if prepared.voice:
            meta["voice"] = True

    def _contact(self, outgoing: OutgoingMessage) -> tuple[str, str]:
        name = (outgoing.contact_name or "").strip()[:CONTACT_NAME_MAX_LENGTH]
        if not name or not outgoing.contact_phone:
            raise AppError(ErrorCode.VALIDATION_FAILED, fields={"contact": "required"})
        phone = normalize_phone_number(outgoing.contact_phone, self._settings.default_phone_region)
        return name, phone

    @staticmethod
    async def _call(request: Awaitable[str]) -> str:
        try:
            result = await request
        except WhatsAppError as exc:
            raise _send_failed(exc) from exc
        return result
