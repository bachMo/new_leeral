import logging
import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta

from app.channels.whatsapp.media_archive import MediaArchiver
from app.core.clock import utcnow
from app.core.errors import AppError, ErrorCode, NotFoundError
from app.db.unit_of_work import UnitOfWork
from app.integrations.storage import FileStorage
from app.integrations.whatsapp.client import WhatsAppClient, WhatsAppError
from app.models import WhatsAppChannel, WhatsAppMessage, WhatsAppThread
from app.repositories.inbox import InboxRepository
from app.schemas.inbox import (
    MediaLinkOut,
    MessageOut,
    MessagePageOut,
    PlanOut,
    ThreadDetailOut,
    ThreadOut,
    ThreadPageOut,
)
from app.services.billing_service import EntitlementService
from app.services.inbox_presenter import message_out, referenced_wa_ids, thread_fields, thread_out

logger = logging.getLogger("leeral.inbox")

PAGE_SIZE = 30
MESSAGE_PAGE_SIZE = 40
MAX_CHANGED = 200
READ_RECEIPT_MAX_AGE = timedelta(days=30)


class InboxService:
    def __init__(self, uow: UnitOfWork, storage: FileStorage, client: WhatsAppClient) -> None:
        self._uow = uow
        self._storage = storage
        self._client = client
        self._repo = InboxRepository(uow.session)

    async def list_threads(
        self, *, query: str | None, thread_filter: str, offset: int
    ) -> ThreadPageOut:
        now = utcnow()
        rows = await self._repo.threads(
            now=now,
            query=query,
            thread_filter=thread_filter,
            limit=PAGE_SIZE + 1,
            offset=offset,
        )
        return ThreadPageOut(
            items=[thread_out(row, now) for row in rows[:PAGE_SIZE]],
            has_more=len(rows) > PAGE_SIZE,
            unread_threads=await self._repo.unread_threads(),
            server_time=now,
        )

    async def thread_summary(self, thread_id: uuid.UUID) -> ThreadOut:
        now = utcnow()
        rows = await self._repo.threads(
            now=now, query=None, thread_filter="all", limit=1, offset=0, thread_id=thread_id
        )
        if not rows:
            raise NotFoundError("thread")
        return thread_out(rows[0], now)

    async def thread_detail(self, thread_id: uuid.UUID) -> ThreadDetailOut:
        now = utcnow()
        rows = await self._repo.threads(
            now=now, query=None, thread_filter="all", limit=1, offset=0, thread_id=thread_id
        )
        if not rows:
            raise NotFoundError("thread")
        row = rows[0]
        user = row.user
        channel = await self._uow.session.get(WhatsAppChannel, row.thread.channel_id)
        plan = None
        documents = 0
        if user is not None:
            entitlements = await EntitlementService(self._uow.session).for_user(user)
            plan = PlanOut(code=entitlements.plan.code.value, expires_at=entitlements.expires_at)
            documents = await self._repo.documents_count(user.id)
        return ThreadDetailOut(
            **thread_fields(row, now),
            user_id=user.id if user else None,
            whatsapp_name=user.whatsapp_name if user else None,
            first_name=user.first_name if user else None,
            registered=bool(user and user.registered_at),
            plan=plan,
            documents_count=documents,
            first_contact_at=await self._repo.first_message_at(row.thread),
            last_seen_at=user.last_seen_at if user else None,
            channel_number=channel.display_number if channel else "",
        )

    async def messages(
        self,
        thread_id: uuid.UUID,
        *,
        before_id: uuid.UUID | None,
        updated_after: datetime | None,
    ) -> MessagePageOut:
        now = utcnow()
        thread = await self._thread(thread_id)
        if updated_after is not None:
            items = await self._repo.messages_changed(thread, updated_after, MAX_CHANGED + 1)
            has_more = len(items) > MAX_CHANGED
            items = items[-MAX_CHANGED:]
        else:
            before = await self._repo.message_in_thread(thread, before_id) if before_id else None
            if before_id is not None and before is None:
                raise NotFoundError("message")
            items = await self._repo.messages_before(thread, before, MESSAGE_PAGE_SIZE + 1)
            has_more = len(items) > MESSAGE_PAGE_SIZE
            items = items[-MESSAGE_PAGE_SIZE:]
        return MessagePageOut(
            items=await self.present(thread, items), has_more=has_more, server_time=now
        )

    async def present(
        self, thread: WhatsAppThread, messages: Sequence[WhatsAppMessage]
    ) -> list[MessageOut]:
        loaded = {message.wa_message_id: message for message in messages}
        missing = [wa_id for wa_id in referenced_wa_ids(messages) if wa_id not in loaded]
        references = loaded | await self._repo.by_wa_ids(thread, missing)
        admin_names = await self._repo.admin_names(
            [message.admin_id for message in messages if message.admin_id]
        )
        return [message_out(message, references, admin_names) for message in messages]

    async def mark_read(self, thread_id: uuid.UUID) -> ThreadOut:
        thread = await self._thread(thread_id)
        now = utcnow()
        thread.last_read_at = now
        latest = await self._repo.last_inbound(thread)
        await self._uow.commit()
        if latest is not None and latest.created_at > now - READ_RECEIPT_MAX_AGE:
            channel = await self._uow.session.get(WhatsAppChannel, thread.channel_id)
            if channel is not None:
                try:
                    await self._client.mark_as_read(channel.phone_number_id, latest.wa_message_id)
                except WhatsAppError:
                    logger.info("inbox_mark_read_failed")
        return await self.thread_summary(thread_id)

    async def set_bot(self, thread_id: uuid.UUID, *, paused: bool) -> ThreadOut:
        thread = await self._thread(thread_id)
        thread.bot_paused = paused
        if not paused:
            thread.bot_paused_until = None
        await self._uow.commit()
        return await self.thread_summary(thread_id)

    async def media(self, message_id: uuid.UUID) -> MediaLinkOut:
        message = await self._uow.session.get(WhatsAppMessage, message_id)
        if message is None:
            raise NotFoundError("message")
        if message.media_key is None:
            if message.wa_media_id is None:
                raise AppError(ErrorCode.MEDIA_UNAVAILABLE)
            try:
                await MediaArchiver(self._uow.session, self._client, self._storage).archive(message)
            except WhatsAppError as exc:
                raise AppError(ErrorCode.MEDIA_UNAVAILABLE) from exc
            await self._uow.commit()
        if message.media_key is None:
            raise AppError(ErrorCode.MEDIA_UNAVAILABLE)
        filename = (message.meta or {}).get("filename")
        return MediaLinkOut(
            url=self._storage.signed_url(
                message.media_key, filename=str(filename) if filename else None
            ),
            mime_type=message.media_mime,
            filename=str(filename) if filename else None,
        )

    async def _thread(self, thread_id: uuid.UUID) -> WhatsAppThread:
        thread = await self._repo.thread(thread_id)
        if thread is None:
            raise NotFoundError("thread")
        return thread
