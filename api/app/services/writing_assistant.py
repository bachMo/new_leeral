import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.engine import AiEngine
from app.core.clock import today
from app.core.errors import ERROR_CATALOG, AppError, ErrorCode
from app.integrations.storage import FileStorage
from app.models import Conversation, Message, User, Writing, WritingOutput, WritingStep
from app.models.enums import AiJobType, MessageStatus, WritingOutputKind, WritingStatus
from app.repositories.writings import WritingRepository
from app.services import storage_keys
from app.services.ai_jobs import AiJobRefs, AiJobTracker
from app.services.narrator import Narrator
from app.services.pdf_renderer import render_pdf
from app.services.speech_input import SpeechInput
from app.services.writing_catalog import template_for

logger = logging.getLogger("leeral.writings")

RETRY_PREFIX_FR = "Je n'ai pas bien compris. Réponds encore une fois, s'il te plaît."
NOT_UNDERSTOOD_FR = "Je n'ai pas bien compris ta réponse. Tu peux répéter ?"
READY_FR = "Ton document est prêt. Je te le lis."


def _failure_code(exc: Exception) -> ErrorCode:
    if isinstance(exc, AppError):
        return exc.code
    logger.exception("writing_job_crashed")
    return ErrorCode.INTERNAL_ERROR


def _confirmation_fr(value: str) -> str:
    return f"J'ai compris : {value}. C'est bien ça ?"


class WritingAssistant:
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

    async def ask_step(
        self, writing_id: uuid.UUID, position: int, message_id: uuid.UUID, *, retry: bool
    ) -> None:
        async with self._session_factory() as session:
            writing = await session.get(Writing, writing_id)
            message = await session.get(Message, message_id)
            if writing is None or message is None or message.status is not MessageStatus.PENDING:
                return
            spec = template_for(writing.type).steps[position]
            text_fr = f"{RETRY_PREFIX_FR} {spec.question_fr}" if retry else spec.question_fr
            await self._speak_into(
                session,
                writing,
                message,
                text_fr,
                AiJobType.ASK_WRITING_STEP,
                position=position,
            )

    async def analyze_answer(
        self, step_id: uuid.UUID, answer_id: uuid.UUID, reply_id: uuid.UUID
    ) -> None:
        async with self._session_factory() as session:
            step = await session.get(WritingStep, step_id)
            answer = await session.get(Message, answer_id)
            reply = await session.get(Message, reply_id)
            if step is None or answer is None or reply is None:
                return
            writing = await session.get(Writing, step.writing_id)
            conversation = await session.get(Conversation, reply.conversation_id)
            if writing is None or conversation is None:
                return
            spec = template_for(writing.type).steps[step.position]
            try:
                async with self._tracker.track(
                    AiJobType.ANALYZE_WRITING_ANSWER,
                    AiJobRefs(
                        user_id=writing.user_id,
                        conversation_id=conversation.id,
                        message_id=reply.id,
                        writing_id=writing.id,
                    ),
                    field=spec.key,
                ):
                    answer_fr = await self._speech_input.to_french(answer, conversation.language)
                    value = await self._ai.interpret_writing_answer(spec.as_field(), answer_fr)
                    if step.answer_message_id == answer.id:
                        step.understood_value = value
                    text_fr = _confirmation_fr(value) if value else NOT_UNDERSTOOD_FR
                    await self._fill(
                        session, writing, reply, text_fr, protected=(value,) if value else ()
                    )
            except Exception as exc:
                await session.rollback()
                await self._fail(session, reply_id, _failure_code(exc))
                return
            await session.commit()

    async def generate(self, writing_id: uuid.UUID, message_id: uuid.UUID) -> None:
        async with self._session_factory() as session:
            writings = WritingRepository(session)
            writing = await writings.get(writing_id)
            message = await session.get(Message, message_id)
            if writing is None or message is None or writing.status is not WritingStatus.GENERATING:
                return
            user = await session.get(User, writing.user_id)
            conversation = await session.get(Conversation, writing.conversation_id)
            if user is None or conversation is None:
                return
            template = template_for(writing.type)
            try:
                async with self._tracker.track(
                    AiJobType.GENERATE_WRITING,
                    AiJobRefs(user_id=user.id, writing_id=writing.id, message_id=message.id),
                    writing_type=writing.type.value,
                ):
                    composed = await self._ai.compose_writing(
                        writing.type.value, template.fields(), dict(writing.collected_data)
                    )
                    version = await writings.next_output_version(writing.id)
                    _, readback_audio = await self._narrator.voice(
                        composed.readback_fr, conversation.language
                    )
                    readback_key = storage_keys.writing_file(
                        user, writing.id, f"readback-v{version}", readback_audio.extension
                    )
                    await self._storage.put(
                        readback_key, readback_audio.content, readback_audio.mime_type
                    )
                    pdfs = await asyncio.gather(
                        *(
                            asyncio.to_thread(render_pdf, document, issued_on=today())
                            for document in composed.documents
                        )
                    )
                    for document, pdf in zip(composed.documents, pdfs, strict=True):
                        key = storage_keys.writing_file(
                            user, writing.id, f"{document.kind}-v{version}", "pdf"
                        )
                        await self._storage.put(key, pdf, "application/pdf")
                        session.add(
                            WritingOutput(
                                writing_id=writing.id,
                                version=version,
                                kind=WritingOutputKind(document.kind),
                                content=document.as_text(),
                                pdf_key=key,
                                readback_language=conversation.language,
                                readback_audio_key=readback_key,
                            )
                        )
                    await self._fill(
                        session, writing, message, f"{READY_FR} {composed.readback_fr}"
                    )
                    writing.status = WritingStatus.READY
            except Exception as exc:
                await session.rollback()
                await self._fail(session, message_id, _failure_code(exc), writing_id=writing_id)
                return
            await session.commit()
            logger.info("writing_ready", extra={"writing_id": str(writing_id)})

    async def _speak_into(
        self,
        session: AsyncSession,
        writing: Writing,
        message: Message,
        text_fr: str,
        job_type: AiJobType,
        **job_input: object,
    ) -> None:
        message_id = message.id
        try:
            async with self._tracker.track(
                job_type,
                AiJobRefs(
                    user_id=writing.user_id,
                    conversation_id=message.conversation_id,
                    message_id=message.id,
                    writing_id=writing.id,
                ),
                **job_input,
            ):
                await self._fill(session, writing, message, text_fr)
        except Exception as exc:
            await session.rollback()
            await self._fail(session, message_id, _failure_code(exc))
            return
        await session.commit()

    async def _fill(
        self,
        session: AsyncSession,
        writing: Writing,
        message: Message,
        text_fr: str,
        *,
        protected: tuple[str, ...] = (),
    ) -> None:
        user = await session.get(User, writing.user_id)
        conversation = await session.get(Conversation, message.conversation_id)
        if user is None or conversation is None:
            raise AppError(ErrorCode.NOT_FOUND)
        localized, audio = await self._narrator.voice(
            text_fr, conversation.language, protected_terms=protected
        )
        key = storage_keys.message_media(user, conversation.id, audio.extension)
        await self._storage.put(key, audio.content, audio.mime_type)
        message.text = localized.text
        message.text_fr = text_fr
        message.audio_key = key
        message.audio_duration_s = audio.duration_s
        message.status = MessageStatus.READY

    async def _fail(
        self,
        session: AsyncSession,
        message_id: uuid.UUID,
        code: ErrorCode,
        *,
        writing_id: uuid.UUID | None = None,
    ) -> None:
        message = await session.get(Message, message_id, populate_existing=True)
        if message is not None:
            message.status = MessageStatus.FAILED
            message.text_fr = ERROR_CATALOG[code].message
        if writing_id is not None:
            writing = await session.get(Writing, writing_id, populate_existing=True)
            if writing is not None:
                writing.status = WritingStatus.FAILED
        await session.commit()
        logger.warning("writing_step_failed", extra={"message_id": str(message_id), "code": code})
