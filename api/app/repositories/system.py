import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.languages import Language
from app.models import AiJob, UiPrompt, WhatsAppChannel, WhatsAppMessage, WhatsAppSession
from app.models.enums import WhatsAppSessionState
from app.repositories.base import Repository


class AiJobRepository(Repository[AiJob]):
    model = AiJob


class UiPromptRepository(Repository[UiPrompt]):
    model = UiPrompt

    async def for_language(self, language: Language) -> Sequence[UiPrompt]:
        return (
            await self.session.scalars(
                select(UiPrompt).where(UiPrompt.language == language).order_by(UiPrompt.key)
            )
        ).all()

    async def find(self, key: str, language: Language) -> UiPrompt | None:
        return await self.session.scalar(
            select(UiPrompt).where(UiPrompt.key == key, UiPrompt.language == language)
        )


class WhatsAppChannelRepository(Repository[WhatsAppChannel]):
    model = WhatsAppChannel

    async def by_phone_number_id(self, phone_number_id: str) -> WhatsAppChannel | None:
        return await self.session.scalar(
            select(WhatsAppChannel).where(WhatsAppChannel.phone_number_id == phone_number_id)
        )

    async def first_active(self) -> WhatsAppChannel | None:
        return await self.session.scalar(
            select(WhatsAppChannel)
            .where(WhatsAppChannel.is_active.is_(True))
            .order_by(WhatsAppChannel.created_at)
            .limit(1)
        )


class WhatsAppMessageRepository(Repository[WhatsAppMessage]):
    model = WhatsAppMessage

    async def by_wa_id(self, wa_message_id: str) -> WhatsAppMessage | None:
        return await self.session.scalar(
            select(WhatsAppMessage).where(WhatsAppMessage.wa_message_id == wa_message_id)
        )


class WhatsAppSessionRepository(Repository[WhatsAppSession]):
    model = WhatsAppSession

    async def ensure(
        self, user_id: uuid.UUID, channel_id: uuid.UUID, state: WhatsAppSessionState
    ) -> WhatsAppSession:
        await self.session.execute(
            insert(WhatsAppSession)
            .values(user_id=user_id, channel_id=channel_id, state=state)
            .on_conflict_do_nothing(index_elements=["user_id", "channel_id"])
        )
        result = await self.session.scalars(
            select(WhatsAppSession)
            .where(WhatsAppSession.user_id == user_id, WhatsAppSession.channel_id == channel_id)
            .with_for_update()
        )
        return result.one()
