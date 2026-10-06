import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError, ErrorCode, NotFoundError
from app.core.languages import TextLanguage
from app.db.unit_of_work import UnitOfWork
from app.integrations.storage import FileStorage
from app.models import Conversation, DocumentSuggestedQuestion, Message, User
from app.models.enums import (
    Channel,
    ContentType,
    ConversationKind,
    DocumentStatus,
    ExplanationVariant,
    MessageRole,
    MessageStatus,
)
from app.repositories.conversations import ConversationRepository, MessageRepository
from app.repositories.documents import DocumentRepository
from app.services import storage_keys
from app.services.media import IncomingFile, detect_audio
from app.workers.jobs import Job


@dataclass(frozen=True, slots=True)
class Question:
    text: str | None = None
    text_language: TextLanguage | None = None
    audio: IncomingFile | None = None
    suggested_question_id: uuid.UUID | None = None

    def validate(self) -> None:
        provided = [
            value
            for value in (self.text and self.text.strip(), self.audio, self.suggested_question_id)
            if value
        ]
        if len(provided) != 1:
            raise AppError(ErrorCode.QUESTION_EMPTY)


@dataclass(frozen=True, slots=True)
class Exchange:
    question: Message
    answer: Message


class ConversationService:
    def __init__(self, uow: UnitOfWork, storage: FileStorage, settings: Settings) -> None:
        self._uow = uow
        self._storage = storage
        self._settings = settings
        self._conversations = ConversationRepository(uow.session)
        self._messages = MessageRepository(uow.session)
        self._documents = DocumentRepository(uow.session)

    async def open_for_document(
        self, user: User, document_id: uuid.UUID, *, source: Channel = Channel.APP
    ) -> Conversation:
        existing = await self._conversations.for_document(user.id, document_id)
        if existing is not None:
            return existing
        document = await self._documents.owned(user.id, document_id)
        if document is None:
            raise NotFoundError("document")
        if document.status is not DocumentStatus.READY:
            raise AppError(ErrorCode.DOCUMENT_NOT_READY)
        explanation = await self._documents.explanation(
            document.id, user.language, ExplanationVariant.STANDARD
        )
        conversation = self._conversations.add(
            Conversation(
                id=uuid.uuid4(),
                user_id=user.id,
                document_id=document.id,
                source=source,
                language=user.language,
                kind=ConversationKind.DOCUMENT,
                context_summary=document.summary_fr,
            )
        )
        await self._uow.session.flush()
        if explanation is not None:
            self._messages.add(
                Message(
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT,
                    content_type=ContentType.AUDIO,
                    language=TextLanguage(user.language.value),
                    status=MessageStatus.READY,
                    text=explanation.text,
                    text_fr=explanation.text_fr,
                    audio_key=explanation.audio_key,
                    audio_duration_s=explanation.audio_duration_s,
                    explanation_id=explanation.id,
                )
            )
        await self._uow.commit()
        return conversation

    async def get(self, user: User, conversation_id: uuid.UUID) -> Conversation:
        conversation = await self._conversations.owned(user.id, conversation_id)
        if conversation is None:
            raise NotFoundError("conversation")
        return conversation

    async def messages(
        self, user: User, conversation_id: uuid.UUID, *, after: datetime | None, limit: int
    ) -> Sequence[Message]:
        conversation = await self.get(user, conversation_id)
        return await self._messages.in_conversation(conversation.id, after=after, limit=limit)

    async def ask(
        self,
        user: User,
        conversation: Conversation,
        question: Question,
        *,
        whatsapp_message_id: uuid.UUID | None = None,
    ) -> Exchange:
        asked = await self.build_user_message(user, conversation, question)
        asked.whatsapp_message_id = whatsapp_message_id
        answer = self._messages.add(
            Message(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content_type=ContentType.AUDIO,
                language=TextLanguage(conversation.language.value),
                status=MessageStatus.PENDING,
            )
        )
        conversation.last_message_at = utcnow()
        self._uow.defer(Job.ANSWER_MESSAGE, question_id=str(asked.id), answer_id=str(answer.id))
        await self._uow.commit()
        return Exchange(question=asked, answer=answer)

    async def build_user_message(
        self, user: User, conversation: Conversation, question: Question
    ) -> Message:
        question.validate()
        message = Message(id=uuid.uuid4(), conversation_id=conversation.id, role=MessageRole.USER)
        if question.audio is not None:
            if len(question.audio.content) > self._settings.max_audio_bytes:
                raise AppError(ErrorCode.FILE_TOO_LARGE)
            detected = detect_audio(question.audio.content)
            key = storage_keys.message_media(user, conversation.id, detected.extension)
            await self._storage.put(key, question.audio.content, detected.mime_type)
            message.content_type = ContentType.AUDIO
            message.language = TextLanguage(conversation.language.value)
            message.status = MessageStatus.PENDING
            message.audio_key = key
        elif question.suggested_question_id is not None:
            suggestion = await self._uow.session.get(
                DocumentSuggestedQuestion, question.suggested_question_id
            )
            if suggestion is None or suggestion.document_id != conversation.document_id:
                raise NotFoundError("suggested question")
            message.content_type = ContentType.TEXT
            message.language = TextLanguage.FRENCH
            message.status = MessageStatus.READY
            message.text_fr = suggestion.text_fr
            message.audio_key = suggestion.audio_key
            message.suggested_question_id = suggestion.id
        else:
            text = (question.text or "").strip()[: self._settings.max_question_chars]
            language = question.text_language or TextLanguage(conversation.language.value)
            message.content_type = ContentType.TEXT
            message.language = language
            message.status = MessageStatus.READY
            message.text = text
            message.text_fr = text if language is TextLanguage.FRENCH else None
        return self._messages.add(message)
