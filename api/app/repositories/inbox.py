import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, and_, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminUser, Document, User, WhatsAppMessage, WhatsAppThread
from app.models.enums import WhatsAppDirection, WhatsAppMessageType

WINDOW = timedelta(hours=24)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class ThreadRow:
    thread: WhatsAppThread
    user: User | None
    last_message: WhatsAppMessage
    last_inbound_at: datetime | None
    unread_count: int


def _same_thread() -> ColumnElement[bool]:
    return and_(
        WhatsAppMessage.channel_id == WhatsAppThread.channel_id,
        WhatsAppMessage.wa_phone == WhatsAppThread.wa_phone,
    )


def _counts_as_inbound() -> ColumnElement[bool]:
    return and_(
        WhatsAppMessage.direction == WhatsAppDirection.INBOUND,
        WhatsAppMessage.type != WhatsAppMessageType.REACTION,
    )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class InboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _thread_columns(self) -> dict[str, Any]:
        last_id = (
            select(WhatsAppMessage.id)
            .where(_same_thread())
            .order_by(WhatsAppMessage.created_at.desc(), WhatsAppMessage.id.desc())
            .limit(1)
            .correlate(WhatsAppThread)
            .scalar_subquery()
        )
        last_at = (
            select(func.max(WhatsAppMessage.created_at))
            .where(_same_thread())
            .correlate(WhatsAppThread)
            .scalar_subquery()
        )
        last_inbound_at = (
            select(func.max(WhatsAppMessage.created_at))
            .where(_same_thread(), _counts_as_inbound())
            .correlate(WhatsAppThread)
            .scalar_subquery()
        )
        unread = (
            select(func.count())
            .where(
                _same_thread(),
                _counts_as_inbound(),
                WhatsAppMessage.created_at > func.coalesce(WhatsAppThread.last_read_at, _EPOCH),
            )
            .correlate(WhatsAppThread)
            .scalar_subquery()
        )
        return {
            "last_id": last_id,
            "last_at": last_at,
            "last_inbound_at": last_inbound_at,
            "unread": unread,
        }

    async def threads(
        self,
        *,
        now: datetime,
        query: str | None,
        thread_filter: str,
        limit: int,
        offset: int,
        thread_id: uuid.UUID | None = None,
    ) -> list[ThreadRow]:
        columns = self._thread_columns()
        statement = (
            select(
                WhatsAppThread,
                User,
                columns["last_id"].label("last_id"),
                columns["last_inbound_at"].label("last_inbound_at"),
                columns["unread"].label("unread"),
            )
            .outerjoin(User, User.id == WhatsAppThread.user_id)
            .where(columns["last_at"].is_not(None))
        )
        if thread_id is not None:
            statement = statement.where(WhatsAppThread.id == thread_id)
        if query:
            pattern = f"%{_escape_like(query.strip())}%"
            digits = "".join(character for character in query if character.isdigit())
            conditions = [
                User.first_name.ilike(pattern, escape="\\"),
                User.whatsapp_name.ilike(pattern, escape="\\"),
            ]
            if digits:
                conditions.append(WhatsAppThread.wa_phone.like(f"%{digits}%"))
            statement = statement.where(or_(*conditions))
        if thread_filter == "unread":
            statement = statement.where(columns["unread"] > 0)
        elif thread_filter == "open":
            statement = statement.where(columns["last_inbound_at"] > now - WINDOW)
        elif thread_filter == "paused":
            statement = statement.where(
                or_(
                    WhatsAppThread.bot_paused.is_(True),
                    WhatsAppThread.bot_paused_until > now,
                )
            )
        statement = (
            statement.order_by(columns["last_at"].desc(), WhatsAppThread.id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.session.execute(statement)).all()
        last_ids = [row.last_id for row in rows]
        messages = {
            message.id: message
            for message in await self.session.scalars(
                select(WhatsAppMessage).where(WhatsAppMessage.id.in_(last_ids))
            )
        }
        return [
            ThreadRow(
                thread=row[0],
                user=row[1],
                last_message=messages[row.last_id],
                last_inbound_at=row.last_inbound_at,
                unread_count=int(row.unread or 0),
            )
            for row in rows
            if row.last_id in messages
        ]

    async def unread_threads(self) -> int:
        unread = self._thread_columns()["unread"]
        result = await self.session.scalar(
            select(func.count()).select_from(WhatsAppThread).where(unread > 0)
        )
        return int(result or 0)

    async def thread(self, thread_id: uuid.UUID) -> WhatsAppThread | None:
        return await self.session.get(WhatsAppThread, thread_id)

    async def messages_before(
        self, thread: WhatsAppThread, before: WhatsAppMessage | None, limit: int
    ) -> list[WhatsAppMessage]:
        statement = select(WhatsAppMessage).where(
            WhatsAppMessage.channel_id == thread.channel_id,
            WhatsAppMessage.wa_phone == thread.wa_phone,
        )
        if before is not None:
            statement = statement.where(
                tuple_(WhatsAppMessage.created_at, WhatsAppMessage.id)
                < tuple_(before.created_at, before.id)
            )
        statement = statement.order_by(
            WhatsAppMessage.created_at.desc(), WhatsAppMessage.id.desc()
        ).limit(limit)
        return list(reversed((await self.session.scalars(statement)).all()))

    async def messages_changed(
        self, thread: WhatsAppThread, updated_after: datetime, limit: int
    ) -> list[WhatsAppMessage]:
        statement = (
            select(WhatsAppMessage)
            .where(
                WhatsAppMessage.channel_id == thread.channel_id,
                WhatsAppMessage.wa_phone == thread.wa_phone,
                or_(
                    WhatsAppMessage.updated_at > updated_after,
                    WhatsAppMessage.created_at > updated_after,
                ),
            )
            .order_by(WhatsAppMessage.created_at, WhatsAppMessage.id)
            .limit(limit)
        )
        return list((await self.session.scalars(statement)).all())

    async def message_in_thread(
        self, thread: WhatsAppThread, message_id: uuid.UUID
    ) -> WhatsAppMessage | None:
        message = await self.session.get(WhatsAppMessage, message_id)
        if (
            message is None
            or message.channel_id != thread.channel_id
            or message.wa_phone != thread.wa_phone
        ):
            return None
        return message

    async def by_wa_ids(
        self, thread: WhatsAppThread, wa_ids: Sequence[str]
    ) -> dict[str, WhatsAppMessage]:
        if not wa_ids:
            return {}
        rows = await self.session.scalars(
            select(WhatsAppMessage).where(
                WhatsAppMessage.channel_id == thread.channel_id,
                WhatsAppMessage.wa_phone == thread.wa_phone,
                WhatsAppMessage.wa_message_id.in_(set(wa_ids)),
            )
        )
        return {message.wa_message_id: message for message in rows}

    async def last_inbound(self, thread: WhatsAppThread) -> WhatsAppMessage | None:
        return await self.session.scalar(
            select(WhatsAppMessage)
            .where(
                WhatsAppMessage.channel_id == thread.channel_id,
                WhatsAppMessage.wa_phone == thread.wa_phone,
                _counts_as_inbound(),
            )
            .order_by(WhatsAppMessage.created_at.desc(), WhatsAppMessage.id.desc())
            .limit(1)
        )

    async def first_message_at(self, thread: WhatsAppThread) -> datetime | None:
        return await self.session.scalar(
            select(func.min(WhatsAppMessage.created_at)).where(
                WhatsAppMessage.channel_id == thread.channel_id,
                WhatsAppMessage.wa_phone == thread.wa_phone,
            )
        )

    async def documents_count(self, user_id: uuid.UUID) -> int:
        result = await self.session.scalar(
            select(func.count()).select_from(Document).where(Document.user_id == user_id)
        )
        return int(result or 0)

    async def admin_names(self, admin_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not admin_ids:
            return {}
        rows = await self.session.execute(
            select(AdminUser.id, AdminUser.name).where(AdminUser.id.in_(set(admin_ids)))
        )
        return {row.id: row.name for row in rows}
