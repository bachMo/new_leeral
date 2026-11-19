import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WhatsAppThread


async def ensure_thread(
    session: AsyncSession,
    channel_id: uuid.UUID,
    wa_phone: str,
    user_id: uuid.UUID | None = None,
) -> WhatsAppThread:
    await session.execute(
        insert(WhatsAppThread)
        .values(
            id=uuid.uuid4(),
            channel_id=channel_id,
            wa_phone=wa_phone,
            user_id=user_id,
            bot_paused=False,
        )
        .on_conflict_do_nothing(index_elements=["channel_id", "wa_phone"])
    )
    thread = await session.scalar(
        select(WhatsAppThread).where(
            WhatsAppThread.channel_id == channel_id, WhatsAppThread.wa_phone == wa_phone
        )
    )
    if thread is None:
        raise RuntimeError("whatsapp thread vanished after upsert")
    if user_id is not None and thread.user_id != user_id:
        thread.user_id = user_id
    return thread


def bot_is_paused(thread: WhatsAppThread, now: datetime) -> bool:
    if thread.bot_paused:
        return True
    return thread.bot_paused_until is not None and thread.bot_paused_until > now
