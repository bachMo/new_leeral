from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import build_ai_engine
from app.channels.whatsapp.assistant import WhatsAppAssistant
from app.channels.whatsapp.ingestion import WebhookIngestor
from app.core.clock import utcnow
from app.db.session import get_session_factory
from app.db.unit_of_work import UnitOfWork
from app.integrations.whatsapp.client import DownloadedMedia
from app.integrations.whatsapp.payloads import WebhookPayload
from app.models import WhatsAppChannel, WhatsAppMessage, WhatsAppThread
from app.models.enums import WhatsAppDirection, WhatsAppMessageStatus, WhatsAppMessageType
from app.workers.jobs import Job
from tests.integration.conftest import Harness

PHONE_ID = "phone-1"
SENDER = "221771112233"


def _payload(
    messages: list[dict[str, Any]] | None = None, statuses: list[dict[str, Any]] | None = None
) -> WebhookPayload:
    value: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "metadata": {"phone_number_id": PHONE_ID, "display_phone_number": "221766111021"},
        "contacts": [{"wa_id": SENDER, "profile": {"name": "Awa"}}],
        "messages": messages or [],
        "statuses": statuses or [],
    }
    return WebhookPayload.model_validate(
        {
            "object": "whatsapp_business_account",
            "entry": [{"id": "waba", "changes": [{"field": "messages", "value": value}]}],
        }
    )


async def _channel(session: AsyncSession) -> WhatsAppChannel:
    channel = WhatsAppChannel(phone_number_id=PHONE_ID, display_number="+221 76 611 10 21")
    session.add(channel)
    await session.commit()
    return channel


async def _ingest(harness: Harness, session: AsyncSession, payload: WebhookPayload) -> int:
    return await WebhookIngestor(UnitOfWork(session, harness.queue), harness.settings).ingest(
        payload
    )


def _assistant(harness: Harness) -> WhatsAppAssistant:
    return WhatsAppAssistant(
        get_session_factory(),
        build_ai_engine(),
        harness.storage,
        harness.whatsapp,  # type: ignore[arg-type]
        harness.queue,
        harness.settings,
    )


async def test_new_message_types_create_a_thread(harness: Harness, session: AsyncSession) -> None:
    await _channel(session)

    accepted = await _ingest(
        harness,
        session,
        _payload(
            [
                {
                    "from": SENDER,
                    "id": "wamid.loc",
                    "timestamp": "1",
                    "type": "location",
                    "location": {"latitude": 14.7, "longitude": -17.4, "name": "Sandaga"},
                }
            ]
        ),
    )

    assert accepted == 1
    message = await session.scalar(select(WhatsAppMessage))
    assert message is not None
    assert message.type is WhatsAppMessageType.LOCATION
    assert message.meta == {"location": {"latitude": 14.7, "longitude": -17.4, "name": "Sandaga"}}
    thread = await session.scalar(select(WhatsAppThread))
    assert thread is not None and thread.wa_phone == SENDER
    assert harness.queue.jobs[-1][0] is Job.HANDLE_WHATSAPP_MESSAGE


async def test_late_delivery_status_never_downgrades_a_read_message(
    harness: Harness, session: AsyncSession
) -> None:
    channel = await _channel(session)
    session.add(
        WhatsAppMessage(
            wa_phone=SENDER,
            channel_id=channel.id,
            direction=WhatsAppDirection.OUTBOUND,
            wa_message_id="wamid.out",
            type=WhatsAppMessageType.TEXT,
            status=WhatsAppMessageStatus.SENT,
        )
    )
    await session.commit()

    await _ingest(harness, session, _payload(statuses=[{"id": "wamid.out", "status": "read"}]))
    await _ingest(harness, session, _payload(statuses=[{"id": "wamid.out", "status": "delivered"}]))
    await _ingest(
        harness,
        session,
        _payload(
            statuses=[
                {
                    "id": "wamid.out",
                    "status": "failed",
                    "errors": [{"code": 131047, "title": "Re-engagement message"}],
                }
            ]
        ),
    )

    message = await session.scalar(select(WhatsAppMessage))
    assert message is not None
    await session.refresh(message)
    assert message.status is WhatsAppMessageStatus.FAILED
    assert message.error == "131047 · Re-engagement message"


async def test_paused_bot_stays_silent_and_archives_media(
    harness: Harness, session: AsyncSession
) -> None:
    channel = await _channel(session)
    await _ingest(
        harness,
        session,
        _payload(
            [
                {
                    "from": SENDER,
                    "id": "wamid.photo",
                    "timestamp": "1",
                    "type": "image",
                    "image": {"id": "media-9", "mime_type": "image/jpeg"},
                }
            ]
        ),
    )
    thread = await session.scalar(select(WhatsAppThread))
    assert thread is not None
    thread.bot_paused_until = utcnow() + timedelta(minutes=30)
    await session.commit()
    inbound = await session.scalar(select(WhatsAppMessage))
    assert inbound is not None
    harness.queue.jobs.clear()

    await _assistant(harness).handle(inbound.id, "Awa")

    await session.refresh(inbound)
    assert harness.whatsapp.calls == []
    assert inbound.status is WhatsAppMessageStatus.PROCESSED
    assert inbound.user_id is not None
    assert [job for job, _ in harness.queue.jobs] == [Job.ARCHIVE_WHATSAPP_MEDIA]
    await session.refresh(thread)
    assert thread.user_id == inbound.user_id
    assert channel.id == thread.channel_id


async def test_reaction_gets_no_automatic_reply(harness: Harness, session: AsyncSession) -> None:
    await _channel(session)
    await _ingest(
        harness,
        session,
        _payload(
            [
                {
                    "from": SENDER,
                    "id": "wamid.react",
                    "timestamp": "1",
                    "type": "reaction",
                    "reaction": {"message_id": "wamid.out", "emoji": "🙏"},
                }
            ]
        ),
    )
    reaction = await session.scalar(select(WhatsAppMessage))
    assert reaction is not None
    harness.queue.jobs.clear()

    await _assistant(harness).handle(reaction.id, "Awa")

    assert harness.whatsapp.calls == []
    assert harness.queue.jobs == []


async def test_archive_job_stores_the_media_under_the_user(
    harness: Harness, session: AsyncSession
) -> None:
    await _channel(session)
    await _ingest(
        harness,
        session,
        _payload(
            [
                {
                    "from": SENDER,
                    "id": "wamid.voice",
                    "timestamp": "1",
                    "type": "audio",
                    "audio": {
                        "id": "media-v",
                        "mime_type": "audio/ogg; codecs=opus",
                        "voice": True,
                    },
                }
            ]
        ),
    )
    message = await session.scalar(select(WhatsAppMessage))
    assert message is not None
    harness.whatsapp.media["media-v"] = DownloadedMedia(b"OggS-voice", "audio/ogg")
    thread = await session.scalar(select(WhatsAppThread))
    assert thread is not None
    thread.bot_paused = True
    await session.commit()
    assistant = _assistant(harness)
    await assistant.handle(message.id, "Awa")

    await assistant.archive_media(message.id)

    await session.refresh(message)
    assert message.media_key is not None
    assert message.media_key.startswith(f"users/{message.user_id}/whatsapp/")
    assert message.media_key.endswith(".ogg")
    assert await harness.storage.get(message.media_key) == b"OggS-voice"
