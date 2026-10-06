import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.contracts import ConversationTurn, DocumentContext, QuestionContext
from app.ai.engine import AiEngine
from app.core.errors import ERROR_CATALOG, AppError, ErrorCode
from app.integrations.storage import FileStorage
from app.models import Conversation, Message, User
from app.models.enums import AiJobType, MessageRole, MessageStatus
from app.repositories.conversations import MessageRepository
from app.repositories.documents import DocumentRepository
from app.services import storage_keys
from app.services.ai_jobs import AiJobRefs, AiJobTracker
from app.services.ai_mapping import document_context
from app.services.narrator import Narrator
from app.services.speech_input import SpeechInput

logger = logging.getLogger("leeral.answers")

HISTORY_SIZE = 8


class QuestionAnswerer:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ai: AiEngine,
        storage: FileStorage,
        tracker: AiJobTracker,
    ) -> None:
        self._session_factory = session_factory
        self._ai = ai
        self._storage = storage
        self._tracker = tracker
        self._narrator = Narrator(ai)
        self._speech_input = SpeechInput(ai, storage)

    async def answer(self, question_id: uuid.UUID, answer_id: uuid.UUID) -> MessageStatus | None:
        async with self._session_factory() as session:
            question = await session.get(Message, question_id)
            answer = await session.get(Message, answer_id)
            if question is None or answer is None or answer.status is not MessageStatus.PENDING:
                return None
            conversation = await session.get(Conversation, answer.conversation_id)
            user = await session.get(User, conversation.user_id) if conversation else None
            if conversation is None or user is None:
                return None
            try:
                async with self._tracker.track(
                    AiJobType.ANSWER_QUESTION,
                    AiJobRefs(
                        user_id=user.id,
                        document_id=conversation.document_id,
                        conversation_id=conversation.id,
                        message_id=answer.id,
                    ),
                    input_type=question.content_type.value,
                ):
                    await self._answer(session, user, conversation, question, answer)
            except AppError as exc:
                await session.rollback()
                return await self._fail(session, question_id, answer_id, exc.code)
            except Exception:
                await session.rollback()
                logger.exception("answer_crashed", extra={"message_id": str(answer_id)})
                return await self._fail(session, question_id, answer_id, ErrorCode.INTERNAL_ERROR)
            await session.commit()
            return MessageStatus.READY

    async def _answer(
        self,
        session: AsyncSession,
        user: User,
        conversation: Conversation,
        question: Message,
        answer: Message,
    ) -> None:
        language = conversation.language
        question_fr = await self._speech_input.to_french(question, language)
        document = await self._document_context(session, conversation)
        history = await MessageRepository(session).recent_ready(conversation.id, HISTORY_SIZE)
        turns = tuple(
            ConversationTurn(
                role="user" if message.role is MessageRole.USER else "assistant",
                text_fr=message.text_fr or "",
            )
            for message in history
            if message.id not in {question.id, answer.id} and message.text_fr
        )
        reply = await self._ai.answer(
            QuestionContext(question_fr=question_fr, document=document, history=turns)
        )
        localized, audio = await self._narrator.voice(
            reply.text_fr,
            language,
            protected_terms=document.protected_terms if document else (),
        )
        key = storage_keys.message_media(user, conversation.id, audio.extension)
        await self._storage.put(key, audio.content, audio.mime_type)
        answer.text = localized.text
        answer.text_fr = reply.text_fr
        answer.audio_key = key
        answer.audio_duration_s = audio.duration_s
        answer.source_quote = reply.source_quote
        answer.status = MessageStatus.READY

    async def _document_context(
        self, session: AsyncSession, conversation: Conversation
    ) -> DocumentContext | None:
        if conversation.document_id is None:
            return None
        document = await DocumentRepository(session).detailed(conversation.document_id)
        if document is None:
            return None
        return document_context(document, document.prescription_lines)

    async def _fail(
        self,
        session: AsyncSession,
        question_id: uuid.UUID,
        answer_id: uuid.UUID,
        code: ErrorCode,
    ) -> MessageStatus:
        question = await session.get(Message, question_id, populate_existing=True)
        answer = await session.get(Message, answer_id, populate_existing=True)
        if question is not None and question.status is MessageStatus.PENDING:
            question.status = MessageStatus.FAILED
        if answer is not None:
            answer.status = MessageStatus.FAILED
            answer.text_fr = ERROR_CATALOG[code].message
        await session.commit()
        logger.warning("answer_failed", extra={"message_id": str(answer_id), "code": code})
        return MessageStatus.FAILED
