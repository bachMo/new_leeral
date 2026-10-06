import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select, update

from app.models import Conversation, Message
from app.models.enums import ConversationKind, MessageStatus
from app.repositories.base import Repository


class ConversationRepository(Repository[Conversation]):
    model = Conversation

    async def owned(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation | None:
        return await self.session.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )

    async def for_document(self, user_id: uuid.UUID, document_id: uuid.UUID) -> Conversation | None:
        return await self.session.scalar(
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.document_id == document_id,
                Conversation.kind == ConversationKind.DOCUMENT,
            )
            .order_by(Conversation.created_at)
            .limit(1)
        )

    async def reassign(self, source_user_id: uuid.UUID, target_user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Conversation)
            .where(Conversation.user_id == source_user_id)
            .values(user_id=target_user_id)
        )


class MessageRepository(Repository[Message]):
    model = Message

    async def in_conversation(
        self, conversation_id: uuid.UUID, *, after: datetime | None, limit: int
    ) -> Sequence[Message]:
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.id)
            .limit(limit)
        )
        if after is not None:
            statement = statement.where(Message.created_at > after)
        return (await self.session.scalars(statement)).all()

    async def recent_ready(self, conversation_id: uuid.UUID, limit: int) -> list[Message]:
        rows = await self.session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.status == MessageStatus.READY,
                Message.text_fr.is_not(None),
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(reversed(rows.all()))
