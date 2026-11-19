import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import build_ai_engine
from app.api.deps import AppContainer
from app.core.clock import utcnow
from app.core.config import Settings, get_settings
from app.core.languages import Language
from app.core.passwords import hash_password
from app.core.security import TokenService
from app.db.session import get_engine, get_session_factory
from app.integrations.payments import build_payment_gateway
from app.integrations.storage import LocalStorage
from app.integrations.whatsapp.client import DownloadedMedia, WhatsAppError
from app.main import create_app
from app.models import AdminUser, User, WhatsAppChannel, WhatsAppMessage, WhatsAppThread
from app.models.enums import WhatsAppDirection, WhatsAppMessageStatus, WhatsAppMessageType
from app.services.otp_delivery import build_otp_delivery
from app.workers.jobs import Job

ADMIN_EMAIL = "bachir@example.com"
ADMIN_PASSWORD = "mot-de-passe-solide-123"
TABLES = (
    "whatsapp_messages, whatsapp_threads, whatsapp_sessions, admin_sessions, admin_users, "
    "conversations, documents, users, whatsapp_channels"
)


def _database_available() -> bool:
    async def probe() -> bool:
        try:
            async with get_engine().connect() as connection:
                await connection.execute(text("SELECT 1 FROM admin_users LIMIT 1"))
        except Exception:
            return False
        finally:
            await get_engine().dispose()
        return True

    return asyncio.run(probe())


DATABASE_AVAILABLE = _database_available()


@dataclass
class FakeWhatsApp:
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    fail_with: WhatsAppError | None = None
    media: dict[str, DownloadedMedia] = field(default_factory=dict)
    counter: int = 0

    @property
    def configured(self) -> bool:
        return True

    def _record(self, call: str, /, **payload: Any) -> str:
        if self.fail_with is not None:
            raise self.fail_with
        self.calls.append((call, payload))
        self.counter += 1
        return f"wamid.out.{self.counter}"

    async def send_text(self, phone_number_id: str, to: str, body: str, **kwargs: Any) -> str:
        return self._record("text", to=to, body=body, **kwargs)

    async def send_media(
        self,
        phone_number_id: str,
        to: str,
        kind: str,
        content: bytes,
        mime_type: str,
        filename: str,
        **kwargs: Any,
    ) -> str:
        return self._record(
            "media",
            to=to,
            kind=kind,
            mime_type=mime_type,
            filename=filename,
            size=len(content),
            **kwargs,
        )

    async def send_contact(
        self, phone_number_id: str, to: str, name: str, phone: str, **kwargs: Any
    ) -> str:
        return self._record("contact", to=to, name=name, phone=phone, **kwargs)

    async def send_template(
        self, phone_number_id: str, to: str, name: str, language: str, components: Any = None
    ) -> str:
        return self._record("template", to=to, name=name, language=language)

    async def send_buttons(self, phone_number_id: str, to: str, body: str, buttons: Any) -> str:
        return self._record("buttons", to=to, body=body)

    async def send_audio(
        self, phone_number_id: str, to: str, content: bytes, *args: Any, **kwargs: Any
    ) -> str:
        return self._record("audio", to=to)

    async def mark_as_read(self, phone_number_id: str, message_id: str) -> None:
        self.calls.append(("read", {"message_id": message_id}))

    async def download_media(self, media_id: str) -> DownloadedMedia:
        if media_id not in self.media:
            raise WhatsAppError("media expired", status_code=404)
        return self.media[media_id]

    async def aclose(self) -> None:
        return None


@dataclass
class FakeQueue:
    jobs: list[tuple[Job, dict[str, Any]]] = field(default_factory=list)

    async def enqueue(
        self, job: Job, *, key: str | None = None, defer_by: float | None = None, **kwargs: Any
    ) -> None:
        self.jobs.append((job, kwargs))


@dataclass
class Harness:
    client: httpx.AsyncClient
    whatsapp: FakeWhatsApp
    queue: FakeQueue
    storage: LocalStorage
    settings: Settings
    tokens: TokenService

    async def login(self) -> dict[str, str]:
        response = await self.client.post(
            "/v1/admin/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    if not DATABASE_AVAILABLE:
        pytest.skip("PostgreSQL with migrations is required")
    async with get_session_factory()() as db:
        await db.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        await db.commit()
        yield db
    await get_engine().dispose()


@pytest.fixture
async def harness(session: AsyncSession, tmp_path: Path) -> AsyncIterator[Harness]:
    settings = get_settings().model_copy(
        update={"local_storage_path": tmp_path, "storage_backend": "local"}
    )
    whatsapp = FakeWhatsApp()
    queue = FakeQueue()
    storage = LocalStorage(settings)
    tokens = TokenService(settings)
    app = create_app(settings)
    app.state.container = AppContainer(
        settings=settings,
        ai=build_ai_engine(),
        storage=storage,
        queue=queue,
        tokens=tokens,
        whatsapp=whatsapp,  # type: ignore[arg-type]
        otp_delivery=build_otp_delivery(settings, whatsapp),  # type: ignore[arg-type]
        payments=build_payment_gateway(settings),
    )
    session.add(
        AdminUser(
            email=ADMIN_EMAIL,
            name="Bachir",
            password_hash=hash_password(ADMIN_PASSWORD),
            is_active=True,
            failed_attempts=0,
        )
    )
    await session.commit()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield Harness(client, whatsapp, queue, storage, settings, tokens)


@dataclass
class Conversation:
    channel: WhatsAppChannel
    thread: WhatsAppThread
    user: User | None


async def make_conversation(
    session: AsyncSession,
    *,
    wa_phone: str = "221771112233",
    name: str | None = "Awa",
    channel: WhatsAppChannel | None = None,
) -> Conversation:
    if channel is None:
        channel = WhatsAppChannel(phone_number_id="phone-1", display_number="+221 76 611 10 21")
        session.add(channel)
        await session.flush()
    user = None
    if name is not None:
        user = User(phone_number=f"+{wa_phone}", whatsapp_name=name, language=Language.WOLOF)
        session.add(user)
        await session.flush()
    thread = WhatsAppThread(
        channel_id=channel.id,
        wa_phone=wa_phone,
        user_id=user.id if user else None,
        bot_paused=False,
    )
    session.add(thread)
    await session.commit()
    return Conversation(channel, thread, user)


async def add_message(
    session: AsyncSession,
    conversation: Conversation,
    *,
    direction: WhatsAppDirection = WhatsAppDirection.INBOUND,
    type: WhatsAppMessageType = WhatsAppMessageType.TEXT,
    body: str | None = "Salam",
    ago: timedelta = timedelta(minutes=5),
    meta: dict[str, Any] | None = None,
    wa_media_id: str | None = None,
    media_mime: str | None = None,
    status: WhatsAppMessageStatus | None = None,
) -> WhatsAppMessage:
    created: datetime = utcnow() - ago
    message = WhatsAppMessage(
        id=uuid.uuid4(),
        user_id=conversation.user.id if conversation.user else None,
        wa_phone=conversation.thread.wa_phone,
        channel_id=conversation.channel.id,
        direction=direction,
        wa_message_id=f"wamid.{uuid.uuid4().hex}",
        type=type,
        body_text=body,
        meta=meta,
        wa_media_id=wa_media_id,
        media_mime=media_mime,
        status=status
        or (
            WhatsAppMessageStatus.RECEIVED
            if direction is WhatsAppDirection.INBOUND
            else WhatsAppMessageStatus.SENT
        ),
        created_at=created,
    )
    session.add(message)
    await session.commit()
    await session.execute(text("SET LOCAL session_replication_role = replica"))
    await session.execute(
        text("UPDATE whatsapp_messages SET updated_at = :at WHERE id = :id"),
        {"at": created, "id": message.id},
    )
    await session.commit()
    return message
