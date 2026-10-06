import logging
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import Result, Update, literal_column, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import ERROR_CATALOG, ErrorCode
from app.core.logging import mask_phone
from app.core.phone import to_whatsapp_id
from app.db.base import Entity
from app.integrations.storage import GUEST_PREFIX, FileStorage, owner_prefix, promoted_key
from app.integrations.whatsapp.client import WhatsAppClient, WhatsAppError
from app.models import (
    AiJob,
    Conversation,
    Document,
    DocumentExplanation,
    DocumentFile,
    DocumentKeyPoint,
    DocumentSuggestedQuestion,
    Message,
    User,
    Writing,
    WritingOutput,
)
from app.models.enums import AiJobStatus, DocumentStatus, MessageStatus, WritingStatus
from app.repositories.billing import SubscriptionRepository
from app.repositories.documents import DocumentRepository
from app.repositories.users import OtpRepository, UserRepository

logger = logging.getLogger("leeral.maintenance")

PURGE_BATCH = 200
STALE_AFTER = timedelta(minutes=20)


class MaintenanceService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: FileStorage,
        settings: Settings,
        whatsapp: WhatsAppClient,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._settings = settings
        self._whatsapp = whatsapp

    async def purge_guest_documents(self) -> int:
        cutoff = utcnow() - timedelta(hours=self._settings.guest_document_ttl_hours)
        async with self._session_factory() as session:
            documents = await DocumentRepository(session).expired_guest_documents(
                cutoff, PURGE_BATCH
            )
            prefixes = [
                f"{owner_prefix(document.user_id, is_guest=True)}/documents/{document.id}"
                for document in documents
            ]
            for document in documents:
                await session.delete(document)
            await session.commit()
        for prefix in prefixes:
            await self._storage.delete_prefix(prefix)
        if prefixes:
            logger.info("guest_documents_purged", extra={"count": len(prefixes)})
        return len(prefixes)

    async def purge_inactive_guests(self) -> int:
        cutoff = utcnow() - timedelta(days=self._settings.guest_inactivity_days)
        async with self._session_factory() as session:
            users = UserRepository(session)
            user_ids = await users.inactive_guest_ids(cutoff, PURGE_BATCH)
            if user_ids:
                await users.delete_by_ids(user_ids)
            await session.commit()
        for user_id in user_ids:
            await self._storage.delete_prefix(owner_prefix(user_id, is_guest=True))
        if user_ids:
            logger.info("inactive_guests_purged", extra={"count": len(user_ids)})
        return len(user_ids)

    async def delete_expired_otps(self) -> int:
        async with self._session_factory() as session:
            deleted = await OtpRepository(session).delete_expired(utcnow() - timedelta(days=1))
            await session.commit()
        return deleted

    async def send_renewal_reminders(self) -> int:
        if not self._whatsapp.configured or not self._settings.whatsapp_default_phone_id:
            return 0
        now = utcnow()
        horizon = now + timedelta(days=self._settings.subscription_reminder_days)
        sent = 0
        async with self._session_factory() as session:
            subscriptions = await SubscriptionRepository(session).expiring_between(
                now, horizon, PURGE_BATCH
            )
            for subscription in subscriptions:
                user = await session.get(User, subscription.user_id)
                if user is None or not user.phone_number:
                    continue
                try:
                    await self._whatsapp.send_template(
                        self._settings.whatsapp_default_phone_id,
                        to_whatsapp_id(user.phone_number),
                        self._settings.whatsapp_reminder_template,
                        self._settings.whatsapp_template_language,
                    )
                except WhatsAppError:
                    logger.warning(
                        "renewal_reminder_failed", extra={"phone": mask_phone(user.phone_number)}
                    )
                    continue
                subscription.reminder_sent_at = now
                sent += 1
            await session.commit()
        return sent

    async def promote_guest_files(self, user_id: uuid.UUID) -> int:
        moved: dict[str, str] = {}
        async with self._session_factory() as session:
            for model, column, owner_filter in self._owned_key_columns(user_id):
                rows = await session.execute(
                    select(model.id, column).where(owner_filter, column.like(f"{GUEST_PREFIX}/%"))
                )
                for row_id, key in rows.all():
                    if key not in moved:
                        moved[key] = promoted_key(key, user_id)
                        await self._storage.move(key, moved[key])
                    await session.execute(
                        update(model).where(model.id == row_id).values({column.key: moved[key]})
                    )
            await session.commit()
        logger.info("guest_files_promoted", extra={"user_id": str(user_id), "files": len(moved)})
        return len(moved)

    async def fail_stale_work(self) -> int:
        cutoff = utcnow() - STALE_AFTER
        message = ERROR_CATALOG[ErrorCode.INTERNAL_ERROR].message
        statements: tuple[Update, ...] = (
            update(Document)
            .where(
                Document.status.in_([DocumentStatus.PENDING, DocumentStatus.PROCESSING]),
                Document.updated_at < cutoff,
            )
            .values(status=DocumentStatus.FAILED, failure_reason=ErrorCode.INTERNAL_ERROR.value),
            update(Message)
            .where(Message.status == MessageStatus.PENDING, Message.updated_at < cutoff)
            .values(status=MessageStatus.FAILED, text_fr=message),
            update(Writing)
            .where(Writing.status == WritingStatus.GENERATING, Writing.updated_at < cutoff)
            .values(status=WritingStatus.FAILED),
            update(AiJob)
            .where(AiJob.status == AiJobStatus.RUNNING, AiJob.updated_at < cutoff)
            .values(status=AiJobStatus.FAILED, error="STALE", finished_at=utcnow()),
        )
        failed = 0
        async with self._session_factory() as session:
            for statement in statements:
                result: Result[Any] = await session.execute(
                    statement.returning(literal_column("1"))
                )
                failed += len(result.all())
            await session.commit()
        if failed:
            logger.warning("stale_work_failed", extra={"rows": failed})
        return failed

    async def delete_prefix(self, prefix: str) -> None:
        await self._storage.delete_prefix(prefix)

    @staticmethod
    def _owned_key_columns(
        user_id: uuid.UUID,
    ) -> list[tuple[type[Entity], InstrumentedAttribute[Any], ColumnElement[bool]]]:
        documents = select(Document.id).where(Document.user_id == user_id)
        conversations = select(Conversation.id).where(Conversation.user_id == user_id)
        writings = select(Writing.id).where(Writing.user_id == user_id)
        return [
            (DocumentFile, DocumentFile.file_key, DocumentFile.document_id.in_(documents)),
            (
                DocumentExplanation,
                DocumentExplanation.audio_key,
                DocumentExplanation.document_id.in_(documents),
            ),
            (
                DocumentKeyPoint,
                DocumentKeyPoint.audio_key,
                DocumentKeyPoint.document_id.in_(documents),
            ),
            (
                DocumentSuggestedQuestion,
                DocumentSuggestedQuestion.audio_key,
                DocumentSuggestedQuestion.document_id.in_(documents),
            ),
            (Message, Message.audio_key, Message.conversation_id.in_(conversations)),
            (Message, Message.media_key, Message.conversation_id.in_(conversations)),
            (WritingOutput, WritingOutput.pdf_key, WritingOutput.writing_id.in_(writings)),
            (
                WritingOutput,
                WritingOutput.readback_audio_key,
                WritingOutput.writing_id.in_(writings),
            ),
        ]
