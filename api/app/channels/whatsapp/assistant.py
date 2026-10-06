import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.engine import AiEngine
from app.channels.whatsapp.outbox import WhatsAppOutbox
from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.languages import AVAILABLE_LANGUAGES, LANGUAGE_NAMES, Language
from app.core.phone import normalize_phone_number
from app.db.unit_of_work import UnitOfWork
from app.integrations.storage import FileStorage
from app.integrations.whatsapp.client import ReplyButton, WhatsAppClient, WhatsAppError
from app.models import (
    Conversation,
    Document,
    Message,
    User,
    WhatsAppChannel,
    WhatsAppMessage,
    WhatsAppSession,
)
from app.models.enums import (
    Channel,
    ConversationKind,
    DocumentStatus,
    ExplanationVariant,
    MessageStatus,
    WhatsAppMessageType,
    WhatsAppSessionState,
)
from app.repositories.documents import DocumentRepository
from app.repositories.system import WhatsAppSessionRepository
from app.repositories.users import UserRepository
from app.services.conversation_service import ConversationService, Question
from app.services.document_service import DocumentService
from app.services.media import IncomingFile, safe_filename
from app.workers.queue import JobQueue

logger = logging.getLogger("leeral.whatsapp")

LANGUAGE_REPLY_PREFIX = "lang:"
RENEW_REPLIES = frozenset({"renew", "renouveler"})
LANGUAGE_KEYWORDS = frozenset({"langue", "language", "làkk", "lakk", "demngal"})
LANGUAGE_QUESTION = "Choisis ta langue / Tànnal sa làkk / Suubo ɗemngal maa"


class WhatsAppAssistant:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ai: AiEngine,
        storage: FileStorage,
        client: WhatsAppClient,
        queue: JobQueue,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._ai = ai
        self._storage = storage
        self._client = client
        self._queue = queue
        self._settings = settings

    async def handle(self, message_id: uuid.UUID, profile_name: str | None) -> None:
        async with self._session_factory() as session:
            uow = UnitOfWork(session, self._queue)
            inbound = await session.get(WhatsAppMessage, message_id)
            if inbound is None:
                return
            channel = await session.get(WhatsAppChannel, inbound.channel_id)
            if channel is None:
                return
            user, is_new = await self._user(session, inbound.wa_phone, channel, profile_name)
            inbound.user_id = user.id
            wa_session = await self._session(session, user, channel, is_new=is_new)
            wa_session.last_inbound_at = utcnow()
            await uow.commit()
            await self._mark_read(channel, inbound)
            outbox = WhatsAppOutbox(
                session, self._client, self._storage, channel, inbound.wa_phone, user.id
            )
            await self._dispatch(uow, outbox, user, channel, wa_session, inbound)
            await uow.commit()

    async def document_finished(self, document_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            uow = UnitOfWork(session, self._queue)
            document = await session.get(Document, document_id)
            if document is None or document.source is not Channel.WHATSAPP:
                return
            user = await session.get(User, document.user_id)
            wa_session = await self._latest_session(session, document.user_id)
            if user is None or wa_session is None or not user.phone_number:
                return
            channel = await session.get(WhatsAppChannel, wa_session.channel_id)
            if channel is None:
                return
            outbox = WhatsAppOutbox(
                session, self._client, self._storage, channel, _wa_id(user), user.id
            )
            if document.status is not DocumentStatus.READY:
                await outbox.prompt(_error_prompt(document.failure_reason), user.language)
                await uow.commit()
                return
            conversation = await ConversationService(
                uow, self._storage, self._settings
            ).open_for_document(user, document.id, source=Channel.WHATSAPP)
            conversation.channel_id = channel.id
            wa_session.state = WhatsAppSessionState.DOCUMENT_QUESTION
            wa_session.active_conversation_id = conversation.id
            explanation = await DocumentRepository(session).explanation(
                document.id, user.language, ExplanationVariant.STANDARD
            )
            if explanation is not None:
                await outbox.audio(explanation.audio_key, caption=document.title)
            await outbox.prompt("whatsapp.ask_question", user.language)
            await uow.commit()

    async def answer_finished(self, answer_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            answer = await session.get(Message, answer_id)
            if answer is None:
                return
            conversation = await session.get(Conversation, answer.conversation_id)
            if conversation is None or conversation.source is not Channel.WHATSAPP:
                return
            user = await session.get(User, conversation.user_id)
            channel = (
                await session.get(WhatsAppChannel, conversation.channel_id)
                if conversation.channel_id
                else None
            )
            if user is None or channel is None or not user.phone_number:
                return
            outbox = WhatsAppOutbox(
                session, self._client, self._storage, channel, _wa_id(user), user.id
            )
            if answer.status is MessageStatus.READY and answer.audio_key:
                await outbox.audio(answer.audio_key)
            else:
                await outbox.prompt("error.ai_provider_unavailable", user.language)
            await session.commit()

    async def _dispatch(
        self,
        uow: UnitOfWork,
        outbox: WhatsAppOutbox,
        user: User,
        channel: WhatsAppChannel,
        wa_session: WhatsAppSession,
        inbound: WhatsAppMessage,
    ) -> None:
        reply = (inbound.body_text or "").strip().lower()
        if inbound.type in {WhatsAppMessageType.INTERACTIVE, WhatsAppMessageType.BUTTON}:
            if reply.startswith(LANGUAGE_REPLY_PREFIX):
                await self._choose_language(outbox, user, wa_session, reply)
                return
            if reply in RENEW_REPLIES:
                await outbox.prompt("whatsapp.renew", user.language)
                return
        if wa_session.state is WhatsAppSessionState.CHOOSING_LANGUAGE or (
            inbound.type is WhatsAppMessageType.TEXT and reply in LANGUAGE_KEYWORDS
        ):
            await self._ask_language(outbox, wa_session)
            return
        if inbound.type in {WhatsAppMessageType.IMAGE, WhatsAppMessageType.DOCUMENT}:
            await self._receive_document(uow, outbox, user, wa_session, inbound)
            return
        if inbound.type in {WhatsAppMessageType.AUDIO, WhatsAppMessageType.TEXT}:
            await self._receive_question(uow, outbox, user, channel, wa_session, inbound)
            return
        await outbox.prompt("whatsapp.unsupported", user.language)

    async def _choose_language(
        self, outbox: WhatsAppOutbox, user: User, wa_session: WhatsAppSession, reply: str
    ) -> None:
        code = reply.removeprefix(LANGUAGE_REPLY_PREFIX)
        try:
            language = Language(code)
        except ValueError:
            await self._ask_language(outbox, wa_session)
            return
        if language not in AVAILABLE_LANGUAGES:
            await outbox.text(f"{LANGUAGE_NAMES[language]} : bientôt disponible.")
            await self._ask_language(outbox, wa_session)
            return
        user.language = language
        wa_session.state = WhatsAppSessionState.IDLE
        await outbox.prompt("whatsapp.welcome", language)

    async def _ask_language(self, outbox: WhatsAppOutbox, wa_session: WhatsAppSession) -> None:
        wa_session.state = WhatsAppSessionState.CHOOSING_LANGUAGE
        await outbox.buttons(
            LANGUAGE_QUESTION,
            [
                ReplyButton(id=f"{LANGUAGE_REPLY_PREFIX}{language.value}", title=name)
                for language, name in LANGUAGE_NAMES.items()
            ],
        )

    async def _receive_document(
        self,
        uow: UnitOfWork,
        outbox: WhatsAppOutbox,
        user: User,
        wa_session: WhatsAppSession,
        inbound: WhatsAppMessage,
    ) -> None:
        if inbound.wa_media_id is None:
            await outbox.prompt("whatsapp.unsupported", user.language)
            return
        try:
            media = await self._client.download_media(inbound.wa_media_id)
        except WhatsAppError:
            await outbox.prompt("error.document_unreadable", user.language)
            return
        language = user.language
        try:
            await DocumentService(uow, self._ai, self._storage, self._settings).create(
                user,
                [IncomingFile(safe_filename(inbound.body_text, "whatsapp"), media.content)],
                source=Channel.WHATSAPP,
            )
        except AppError as exc:
            await uow.rollback()
            await outbox.prompt(_error_prompt(exc.code.value), language)
            return
        wa_session.state = WhatsAppSessionState.IDLE
        wa_session.active_conversation_id = None
        await outbox.prompt("whatsapp.reading", user.language)

    async def _receive_question(
        self,
        uow: UnitOfWork,
        outbox: WhatsAppOutbox,
        user: User,
        channel: WhatsAppChannel,
        wa_session: WhatsAppSession,
        inbound: WhatsAppMessage,
    ) -> None:
        language = user.language
        conversation = await self._active_conversation(uow, user, channel, wa_session)
        await uow.commit()
        if inbound.type is WhatsAppMessageType.AUDIO:
            if inbound.wa_media_id is None:
                return
            try:
                media = await self._client.download_media(inbound.wa_media_id)
            except WhatsAppError:
                await outbox.prompt("error.audio_unreadable", language)
                return
            question = Question(audio=IncomingFile("voice.ogg", media.content))
        else:
            question = Question(text=inbound.body_text)
        try:
            await ConversationService(uow, self._storage, self._settings).ask(
                user, conversation, question, whatsapp_message_id=inbound.id
            )
        except AppError as exc:
            await uow.rollback()
            await outbox.prompt(_error_prompt(exc.code.value), language)

    async def _active_conversation(
        self,
        uow: UnitOfWork,
        user: User,
        channel: WhatsAppChannel,
        wa_session: WhatsAppSession,
    ) -> Conversation:
        if wa_session.active_conversation_id is not None:
            conversation = await uow.session.get(Conversation, wa_session.active_conversation_id)
            if conversation is not None:
                return conversation
        conversation = Conversation(
            id=uuid.uuid4(),
            user_id=user.id,
            source=Channel.WHATSAPP,
            channel_id=channel.id,
            language=user.language,
            kind=ConversationKind.FREE,
        )
        uow.session.add(conversation)
        await uow.session.flush()
        wa_session.active_conversation_id = conversation.id
        return conversation

    async def _user(
        self,
        session: AsyncSession,
        wa_phone: str,
        channel: WhatsAppChannel,
        profile_name: str | None,
    ) -> tuple[User, bool]:
        phone_number = normalize_phone_number(f"+{wa_phone}", self._settings.default_phone_region)
        users = UserRepository(session)
        created = await users.insert_if_absent(
            phone_number=phone_number,
            whatsapp_name=profile_name,
            language=channel.language or Language.WOLOF,
        )
        user = await users.by_phone(phone_number)
        if user is None:
            raise AppError(ErrorCode.NOT_FOUND, detail="whatsapp user")
        user.whatsapp_name = profile_name or user.whatsapp_name
        user.last_seen_at = utcnow()
        return user, created

    async def _session(
        self, session: AsyncSession, user: User, channel: WhatsAppChannel, *, is_new: bool
    ) -> WhatsAppSession:
        state = (
            WhatsAppSessionState.CHOOSING_LANGUAGE
            if is_new and channel.language is None
            else WhatsAppSessionState.IDLE
        )
        return await WhatsAppSessionRepository(session).ensure(user.id, channel.id, state)

    async def _latest_session(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> WhatsAppSession | None:
        return await session.scalar(
            select(WhatsAppSession)
            .where(WhatsAppSession.user_id == user_id)
            .order_by(WhatsAppSession.last_inbound_at.desc())
            .limit(1)
        )

    async def _mark_read(self, channel: WhatsAppChannel, inbound: WhatsAppMessage) -> None:
        try:
            await self._client.mark_as_read(channel.phone_number_id, inbound.wa_message_id)
        except WhatsAppError:
            logger.info("whatsapp_mark_read_failed")


def _wa_id(user: User) -> str:
    return (user.phone_number or "").removeprefix("+")


def _error_prompt(code: str | None) -> str:
    return f"error.{(code or ErrorCode.DOCUMENT_UNREADABLE.value).lower()}"
