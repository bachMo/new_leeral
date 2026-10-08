"""Service-side check for the conversation/account rules (checklist points 8-10: one conversation
holds N documents for an account, a guest's conversation expires after
`guest_session_ttl_hours`, the latest document is the default, an explicit `target_document_id`
disambiguates) plus the audio duration cap (point 3). Runs directly against the real configured
PostgreSQL via `ConversationService` — no uvicorn, no arq worker, no Redis (a no-op queue stands
in for the real one). Creates its own throwaway guest/account users and deletes them at the end.

    cd api
    python -m scripts.conversation_check
"""

import asyncio
import sys
import uuid
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.audio import silent_wav
from app.core.clock import utcnow
from app.core.config import Settings, get_settings
from app.core.errors import AppError, ErrorCode, NotFoundError
from app.core.languages import Language, TextLanguage
from app.db.session import get_engine, get_session_factory
from app.db.unit_of_work import UnitOfWork
from app.models import Conversation, Document, User
from app.models.enums import Channel, DocumentCategory, DocumentStatus
from app.services.conversation_service import ConversationService, Question
from app.services.media import IncomingFile
from app.workers.jobs import Job


class _NoopJobQueue:
    async def enqueue(self, job: Job, *, key: str | None = None, **kwargs: object) -> None:
        return None


class _NoopStorage:
    async def put(self, key: str, content: bytes, content_type: str) -> None:
        return None

    async def get(self, key: str) -> bytes:
        return b""

    async def move(self, source: str, destination: str) -> None:
        return None

    async def delete(self, keys: list[str]) -> None:
        return None

    async def delete_prefix(self, prefix: str) -> None:
        return None

    def signed_url(self, key: str, *, filename: str | None = None) -> str:
        return ""


def _check(label: str, condition: bool) -> bool:
    print(f"[{'ok' if condition else 'ÉCHEC'}] {label}")
    return condition


async def _user(session: AsyncSession, *, is_guest: bool) -> User:
    user = User(id=uuid.uuid4(), language=Language.WOLOF, is_guest=is_guest)
    session.add(user)
    await session.flush()
    return user


async def _ready_document(session: AsyncSession, user: User) -> Document:
    document = Document(
        id=uuid.uuid4(),
        user_id=user.id,
        source=Channel.APP,
        status=DocumentStatus.READY,
        category=DocumentCategory.OTHER,
        summary_fr="Document de test.",
    )
    session.add(document)
    await session.flush()
    return document


async def _check_guest_rules(
    session: AsyncSession, service: ConversationService, settings: Settings, guest: User
) -> bool:
    ok = True
    doc1 = await _ready_document(session, guest)
    conv_a = await service.open_for_document(guest, doc1.id)
    conv_b = await service.open_for_document(guest, doc1.id)
    ok &= _check("invité : même document -> même conversation", conv_a.id == conv_b.id)

    conv_a.last_message_at = utcnow() - timedelta(hours=settings.guest_session_ttl_hours + 1)
    await session.flush()
    conv_c = await service.open_for_document(guest, doc1.id)
    ok &= _check(
        "invité : conversation expirée (5h) -> nouvelle conversation", conv_c.id != conv_a.id
    )

    doc2 = await _ready_document(session, guest)
    conv_d = await service.open_for_document(guest, doc2.id)
    ok &= _check(
        "invité : nouveau document -> nouvelle conversation",
        conv_d.id not in {conv_a.id, conv_c.id},
    )
    return ok


async def _check_account_rules(
    session: AsyncSession, service: ConversationService, account: User
) -> tuple[bool, Conversation]:
    ok = True
    doc3 = await _ready_document(session, account)
    doc4 = await _ready_document(session, account)
    conv_e = await service.open_for_document(account, doc3.id)
    conv_f = await service.open_for_document(account, doc4.id)
    ok &= _check("compte : même conversation entre deux documents", conv_e.id == conv_f.id)

    attached = await service.documents_for(conv_f.id)
    ok &= _check(
        "compte : les deux documents sont attachés à la conversation",
        {doc3.id, doc4.id} <= set(attached),
    )
    ok &= _check(
        "compte : le document le plus récent est le document par défaut",
        conv_f.document_id == doc4.id,
    )

    await service.ask(
        account,
        conv_f,
        Question(text="Une question.", text_language=TextLanguage.FRENCH),
        target_document_id=doc3.id,
    )
    ok &= _check(
        "compte : document_id explicite bascule le document actif",
        conv_f.document_id == doc3.id,
    )
    try:
        await service.ask(
            account,
            conv_f,
            Question(text="Une autre question.", text_language=TextLanguage.FRENCH),
            target_document_id=uuid.uuid4(),
        )
        ok &= _check("compte : document_id inconnu rejeté", False)
    except NotFoundError:
        ok &= _check("compte : document_id inconnu rejeté", True)
    return ok, conv_f


async def _check_audio_cap(
    service: ConversationService, settings: Settings, account: User, conversation: Conversation
) -> bool:
    too_long = silent_wav(settings.max_question_audio_seconds + 10)
    try:
        await service.build_user_message(
            account, conversation, Question(audio=IncomingFile("note.wav", too_long))
        )
        return _check("audio trop long rejeté", False)
    except AppError as exc:
        return _check("audio trop long rejeté", exc.code is ErrorCode.AUDIO_TOO_LONG)


async def _cleanup(session: AsyncSession, user_ids: list[uuid.UUID]) -> None:
    await session.execute(delete(Conversation).where(Conversation.user_id.in_(user_ids)))
    await session.execute(delete(Document).where(Document.user_id.in_(user_ids)))
    await session.execute(delete(User).where(User.id.in_(user_ids)))
    await session.commit()


async def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    settings = get_settings()
    async with get_session_factory()() as session:
        uow = UnitOfWork(session, _NoopJobQueue())
        service = ConversationService(uow, _NoopStorage(), settings)
        guest = await _user(session, is_guest=True)
        account = await _user(session, is_guest=False)
        try:
            guest_ok = await _check_guest_rules(session, service, settings, guest)
            account_ok, conversation = await _check_account_rules(session, service, account)
            audio_ok = await _check_audio_cap(service, settings, account, conversation)
            all_ok = guest_ok and account_ok and audio_ok
        finally:
            await _cleanup(session, [guest.id, account.id])

    await get_engine().dispose()
    print("\n" + ("TOUT EST BON" if all_ok else "DES VÉRIFICATIONS ONT ÉCHOUÉ"))
    if not all_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
