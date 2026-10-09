import logging
import uuid
from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.contracts import PRESCRIPTION
from app.ai.engine import AiEngine
from app.ai.errors import TranslationError
from app.channels.whatsapp.outbox import WhatsAppOutbox
from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.languages import AVAILABLE_LANGUAGES, LANGUAGE_NAMES, Language, TextLanguage
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
    WhatsAppDirection,
    WhatsAppMessageStatus,
    WhatsAppMessageType,
    WhatsAppSessionState,
)
from app.repositories.documents import DocumentRepository
from app.repositories.system import WhatsAppSessionRepository
from app.repositories.users import UserRepository
from app.services.conversation_service import ConversationService, Question
from app.services.document_service import DocumentService
from app.services.media import IncomingFile, safe_filename
from app.workers.jobs import Job
from app.workers.queue import JobQueue

logger = logging.getLogger("leeral.whatsapp")

LANGUAGE_REPLY_PREFIX = "lang:"
RENEW_REPLIES = frozenset({"renew", "renouveler"})
LANGUAGE_KEYWORDS = frozenset({"langue", "language", "làkk", "lakk", "demngal"})
LANGUAGE_QUESTION = "Choisis ta langue / Tànnal sa làkk / Suubo ɗemngal maa"
WELCOME_TEXT = (
    "Bienvenue sur Leeral ! Envoie-moi la photo ou le PDF d'un document en français, "
    "je te l'explique à voix haute dans ta langue.\n\n"
    "Dalal ak jàmm ci Leeral ! Yónne ma nataalu ab kayit ci farañse, "
    "ma firi la ko ci sa làkk.\n\n"
    "Bismillah e Leeral ! Neldam natal fiilde winndaande e farayseere, "
    "mi firanoyte ɗum e ɗemngal maa."
)
MEDIA_TYPES = frozenset({WhatsAppMessageType.IMAGE, WhatsAppMessageType.DOCUMENT})
PENDING_MEDIA_WINDOW = timedelta(hours=1)
CONFIRM_YES_REPLY = "confirm:yes"
CONFIRM_NO_REPLY = "confirm:no"


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
            await self._dispatch(uow, outbox, user, channel, wa_session, inbound, is_new=is_new)
            await uow.commit()

    async def collect_media(self, user_id: uuid.UUID, message_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            uow = UnitOfWork(session, self._queue)
            user = await session.get(User, user_id)
            wa_session = await self._latest_session(session, user_id)
            if user is None or wa_session is None:
                return
            if wa_session.state is WhatsAppSessionState.CHOOSING_LANGUAGE:
                return
            pending = await self._pending_media(session, user_id)
            if not pending or pending[-1].id != message_id:
                return
            channel = await session.get(WhatsAppChannel, pending[-1].channel_id)
            if channel is None:
                return
            for message in pending:
                message.status = WhatsAppMessageStatus.PROCESSED
            await uow.commit()
            outbox = WhatsAppOutbox(
                session, self._client, self._storage, channel, _wa_id(user), user.id
            )
            await self._create_document(uow, outbox, user, wa_session, pending)
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
            explanation = await DocumentRepository(session).explanation(
                document.id, user.language, ExplanationVariant.STANDARD
            )
            if explanation is not None and await self._already_sent(
                session, user.id, explanation.audio_key
            ):
                return
            conversation = await ConversationService(
                uow, self._storage, self._settings
            ).open_for_document(user, document.id, source=Channel.WHATSAPP)
            conversation.channel_id = channel.id
            wa_session.state = WhatsAppSessionState.DOCUMENT_QUESTION
            wa_session.active_conversation_id = conversation.id
            invitation = await outbox.prompt_audio_key("whatsapp.ask_question", user.language)
            if explanation is None:
                await outbox.prompt("whatsapp.ask_question", user.language)
            elif invitation is None:
                await outbox.audio(explanation.audio_key, caption=document.title)
            else:
                await outbox.audio(explanation.audio_key, invitation, caption=document.title)
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
        *,
        is_new: bool,
    ) -> None:
        reply = (inbound.body_text or "").strip().lower()
        if inbound.type in {WhatsAppMessageType.INTERACTIVE, WhatsAppMessageType.BUTTON}:
            if reply.startswith(LANGUAGE_REPLY_PREFIX):
                await self._choose_language(uow, outbox, user, wa_session, reply)
                return
            if reply in RENEW_REPLIES:
                await outbox.prompt("whatsapp.renew", user.language)
                return
            if wa_session.state is WhatsAppSessionState.CONFIRMING_QUESTION:
                await self._confirm_question(uow, outbox, user, channel, wa_session, reply)
                return
        is_media = inbound.type in MEDIA_TYPES
        if is_media:
            await self._collect_later(uow, outbox, user, inbound)
        if wa_session.state is WhatsAppSessionState.CHOOSING_LANGUAGE:
            if is_new:
                await outbox.text(WELCOME_TEXT)
            if is_new or not is_media:
                await self._ask_language(outbox, wa_session)
            return
        if is_new and not is_media:
            await outbox.prompt("whatsapp.welcome", user.language)
        if inbound.type is WhatsAppMessageType.TEXT and reply in LANGUAGE_KEYWORDS:
            await self._ask_language(outbox, wa_session)
            return
        if is_media:
            return
        if inbound.type in {WhatsAppMessageType.AUDIO, WhatsAppMessageType.TEXT}:
            await self._receive_question(uow, outbox, user, channel, wa_session, inbound)
            return
        await outbox.prompt("whatsapp.unsupported", user.language)

    async def _choose_language(
        self,
        uow: UnitOfWork,
        outbox: WhatsAppOutbox,
        user: User,
        wa_session: WhatsAppSession,
        reply: str,
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
        pending = await self._pending_media(uow.session, user.id)
        if pending:
            self._schedule_collect(uow, user, pending[-1], immediately=True)
            return
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

    async def _collect_later(
        self, uow: UnitOfWork, outbox: WhatsAppOutbox, user: User, inbound: WhatsAppMessage
    ) -> None:
        if inbound.wa_media_id is None:
            inbound.status = WhatsAppMessageStatus.PROCESSED
            await outbox.prompt("whatsapp.unsupported", user.language)
            return
        self._schedule_collect(uow, user, inbound, immediately=False)

    def _schedule_collect(
        self, uow: UnitOfWork, user: User, latest: WhatsAppMessage, *, immediately: bool
    ) -> None:
        uow.defer(
            Job.COLLECT_WHATSAPP_MEDIA,
            key=f"whatsapp-media:{latest.id}:{'now' if immediately else 'batch'}",
            defer_by=None if immediately else self._settings.whatsapp_media_batch_seconds,
            user_id=str(user.id),
            message_id=str(latest.id),
        )

    async def _create_document(
        self,
        uow: UnitOfWork,
        outbox: WhatsAppOutbox,
        user: User,
        wa_session: WhatsAppSession,
        messages: Sequence[WhatsAppMessage],
    ) -> None:
        language = user.language
        files = await self._download(messages)
        if not files:
            await outbox.prompt("error.document_unreadable", language)
            return
        try:
            await DocumentService(uow, self._ai, self._storage, self._settings).create(
                user, files, source=Channel.WHATSAPP
            )
        except AppError as exc:
            await uow.rollback()
            await outbox.prompt(_error_prompt(exc.code.value), language)
            return
        wa_session.state = WhatsAppSessionState.IDLE
        wa_session.active_conversation_id = None

    async def _download(self, messages: Sequence[WhatsAppMessage]) -> list[IncomingFile]:
        files = []
        for message in messages:
            if message.wa_media_id is None:
                continue
            try:
                media = await self._client.download_media(message.wa_media_id)
            except WhatsAppError:
                logger.warning(
                    "whatsapp_media_download_failed", extra={"message_id": str(message.id)}
                )
                continue
            files.append(IncomingFile(safe_filename(message.body_text, "whatsapp"), media.content))
        return files

    async def _pending_media(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> Sequence[WhatsAppMessage]:
        result = await session.scalars(
            select(WhatsAppMessage)
            .where(
                WhatsAppMessage.user_id == user_id,
                WhatsAppMessage.direction == WhatsAppDirection.INBOUND,
                WhatsAppMessage.type.in_(MEDIA_TYPES),
                WhatsAppMessage.status == WhatsAppMessageStatus.RECEIVED,
                WhatsAppMessage.created_at > utcnow() - PENDING_MEDIA_WINDOW,
            )
            .order_by(WhatsAppMessage.created_at, WhatsAppMessage.id)
            .with_for_update(skip_locked=True)
        )
        return result.all()

    async def _already_sent(
        self, session: AsyncSession, user_id: uuid.UUID, audio_key: str
    ) -> bool:
        sent = await session.scalar(
            select(WhatsAppMessage.id)
            .where(
                WhatsAppMessage.user_id == user_id,
                WhatsAppMessage.direction == WhatsAppDirection.OUTBOUND,
                WhatsAppMessage.media_key == audio_key,
            )
            .limit(1)
        )
        return sent is not None

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
        audio: bytes | None = None
        if inbound.type is WhatsAppMessageType.AUDIO:
            if inbound.wa_media_id is None:
                return
            try:
                media = await self._client.download_media(inbound.wa_media_id)
            except WhatsAppError:
                await outbox.prompt("error.audio_unreadable", language)
                return
            audio = media.content

        if await self._is_prescription_conversation(uow, conversation):
            try:
                question_fr = await self._resolve_question_fr(inbound.body_text, audio, language)
            except AppError as exc:
                await outbox.prompt(_error_prompt(exc.code.value), language)
                return
            rephrased = await self._ai.confirm_question(question_fr)
            wa_session.pending_question_fr = question_fr
            wa_session.state = WhatsAppSessionState.CONFIRMING_QUESTION
            await outbox.buttons(
                rephrased,
                [
                    ReplyButton(id=CONFIRM_YES_REPLY, title="Oui"),
                    ReplyButton(id=CONFIRM_NO_REPLY, title="Non"),
                ],
            )
            return

        question = (
            Question(audio=IncomingFile("voice.ogg", audio))
            if audio is not None
            else Question(text=inbound.body_text)
        )
        try:
            await ConversationService(uow, self._storage, self._settings).ask(
                user, conversation, question, whatsapp_message_id=inbound.id
            )
        except AppError as exc:
            await uow.rollback()
            await outbox.prompt(_error_prompt(exc.code.value), language)

    async def _is_prescription_conversation(
        self, uow: UnitOfWork, conversation: Conversation
    ) -> bool:
        if conversation.document_id is None:
            return False
        document = await uow.session.get(Document, conversation.document_id)
        return document is not None and document.doc_type == PRESCRIPTION

    async def _resolve_question_fr(
        self, text: str | None, audio: bytes | None, language: Language
    ) -> str:
        """Transcribe (if spoken) and translate a question to French, without yet persisting it
        as a `Message` — used to show a confirmation prompt before committing to an answer. The
        regular (non-prescription) path still resolves this lazily inside the worker job via
        `SpeechInput.to_french`; duplicated here deliberately to avoid coupling that module to a
        not-yet-created `Message`."""
        if audio is not None:
            transcript = await self._ai.transcribe(audio, filename="voice.ogg", language=language)
            if not transcript.text.strip():
                raise AppError(ErrorCode.AUDIO_EMPTY)
            text = transcript.text.strip()
        text = (text or "").strip()
        if not text:
            raise AppError(ErrorCode.QUESTION_EMPTY)
        try:
            return await self._ai.to_french(text, language)
        except TranslationError as exc:
            raise AppError(ErrorCode.QUESTION_TRANSLATION_FAILED) from exc

    async def _confirm_question(
        self,
        uow: UnitOfWork,
        outbox: WhatsAppOutbox,
        user: User,
        channel: WhatsAppChannel,
        wa_session: WhatsAppSession,
        reply: str,
    ) -> None:
        pending = wa_session.pending_question_fr
        wa_session.pending_question_fr = None
        wa_session.state = WhatsAppSessionState.DOCUMENT_QUESTION
        if reply != CONFIRM_YES_REPLY or pending is None:
            await outbox.prompt("whatsapp.ask_question", user.language)
            return
        conversation = await self._active_conversation(uow, user, channel, wa_session)
        try:
            await ConversationService(uow, self._storage, self._settings).ask(
                user, conversation, Question(text=pending, text_language=TextLanguage.FRENCH)
            )
        except AppError as exc:
            await uow.rollback()
            await outbox.prompt(_error_prompt(exc.code.value), user.language)

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
