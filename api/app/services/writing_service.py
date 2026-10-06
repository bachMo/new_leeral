import uuid
from collections.abc import Sequence
from datetime import datetime

from app.core.clock import utcnow
from app.core.errors import AppError, ErrorCode, NotFoundError
from app.core.languages import TextLanguage
from app.db.unit_of_work import UnitOfWork
from app.models import Conversation, Message, User, Writing, WritingStep
from app.models.enums import (
    Channel,
    ContentType,
    ConversationKind,
    MessageRole,
    MessageStatus,
    UsageFeature,
    WritingStatus,
    WritingType,
)
from app.repositories.writings import WritingRepository, WritingStepRepository
from app.services.billing_service import EntitlementService
from app.services.conversation_service import ConversationService, Question
from app.services.writing_catalog import template_for
from app.workers.jobs import Job


class WritingService:
    def __init__(self, uow: UnitOfWork, conversations: ConversationService) -> None:
        self._uow = uow
        self._conversations = conversations
        self._writings = WritingRepository(uow.session)
        self._steps = WritingStepRepository(uow.session)
        self._entitlements = EntitlementService(uow.session)

    async def start(self, user: User, writing_type: WritingType) -> Writing:
        if user.is_guest:
            raise AppError(ErrorCode.ACCOUNT_REQUIRED)
        await self._entitlements.consume(user, UsageFeature.WRITING)
        template = template_for(writing_type)
        conversation = Conversation(
            id=uuid.uuid4(),
            user_id=user.id,
            source=Channel.APP,
            language=user.language,
            kind=ConversationKind.WRITING,
        )
        self._uow.session.add(conversation)
        await self._writings.flush()
        writing = self._writings.add(
            Writing(
                id=uuid.uuid4(),
                user_id=user.id,
                conversation_id=conversation.id,
                type=writing_type,
                status=WritingStatus.COLLECTING,
                current_step=0,
                total_steps=len(template.steps),
                collected_data={},
            )
        )
        await self._writings.flush()
        await self._ask(writing, conversation, position=0)
        await self._uow.commit()
        return await self.get(user, writing.id)

    async def get(self, user: User, writing_id: uuid.UUID) -> Writing:
        writing = await self._writings.owned(user.id, writing_id, detailed=True)
        if writing is None:
            raise NotFoundError("writing")
        return writing

    async def list_writings(
        self, user: User, *, before: datetime | None, limit: int
    ) -> Sequence[Writing]:
        return await self._writings.list_for_user(user.id, before=before, limit=limit)

    async def answer(self, user: User, writing_id: uuid.UUID, question: Question) -> Message:
        writing, step = await self._current_step(user, writing_id)
        conversation = await self._conversations.get(user, writing.conversation_id)
        answer = await self._conversations.build_user_message(user, conversation, question)
        reply = await self._assistant_message(conversation)
        step.answer_message_id = answer.id
        step.understood_value = None
        step.confirmed_at = None
        conversation.last_message_at = utcnow()
        self._uow.defer(
            Job.ANALYZE_WRITING_ANSWER,
            step_id=str(step.id),
            answer_id=str(answer.id),
            reply_id=str(reply.id),
        )
        await self._uow.commit()
        return reply

    async def confirm(self, user: User, writing_id: uuid.UUID, *, accepted: bool) -> Writing:
        writing, step = await self._current_step(user, writing_id)
        if step.answer_message_id is None or step.understood_value is None:
            raise AppError(ErrorCode.WRITING_NO_PENDING_ANSWER)
        conversation = await self._conversations.get(user, writing.conversation_id)
        if accepted:
            writing.collected_data = {
                **writing.collected_data,
                step.field_key: step.understood_value,
            }
            step.confirmed_at = utcnow()
            await self._advance(writing, conversation)
        else:
            step.understood_value = None
            step.answer_message_id = None
            await self._ask(writing, conversation, position=step.position, step=step)
        await self._uow.commit()
        return await self.get(user, writing_id)

    async def skip(self, user: User, writing_id: uuid.UUID) -> Writing:
        writing, step = await self._current_step(user, writing_id)
        spec = template_for(writing.type).steps[step.position]
        if spec.required:
            raise AppError(ErrorCode.VALIDATION_FAILED, fields={"step": "required"})
        conversation = await self._conversations.get(user, writing.conversation_id)
        step.understood_value = None
        step.confirmed_at = utcnow()
        await self._advance(writing, conversation)
        await self._uow.commit()
        return await self.get(user, writing_id)

    async def _current_step(self, user: User, writing_id: uuid.UUID) -> tuple[Writing, WritingStep]:
        writing = await self._writings.owned(user.id, writing_id)
        if writing is None:
            raise NotFoundError("writing")
        if writing.status is not WritingStatus.COLLECTING:
            raise AppError(ErrorCode.WRITING_NOT_COLLECTING)
        step = await self._steps.at(writing.id, writing.current_step)
        if step is None:
            raise AppError(ErrorCode.WRITING_NOT_COLLECTING)
        return writing, step

    async def _advance(self, writing: Writing, conversation: Conversation) -> None:
        writing.current_step += 1
        if writing.current_step < writing.total_steps:
            await self._ask(writing, conversation, position=writing.current_step)
            return
        writing.status = WritingStatus.GENERATING
        message = await self._assistant_message(conversation)
        self._uow.defer(
            Job.GENERATE_WRITING, writing_id=str(writing.id), message_id=str(message.id)
        )

    async def _ask(
        self,
        writing: Writing,
        conversation: Conversation,
        *,
        position: int,
        step: WritingStep | None = None,
    ) -> None:
        message = await self._assistant_message(conversation)
        if step is None:
            spec = template_for(writing.type).steps[position]
            self._steps.add(
                WritingStep(
                    writing_id=writing.id,
                    position=position,
                    field_key=spec.key,
                    question_message_id=message.id,
                )
            )
        else:
            step.question_message_id = message.id
        conversation.last_message_at = utcnow()
        self._uow.defer(
            Job.ASK_WRITING_STEP,
            writing_id=str(writing.id),
            position=position,
            message_id=str(message.id),
            retry=step is not None,
        )

    async def _assistant_message(self, conversation: Conversation) -> Message:
        message = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content_type=ContentType.AUDIO,
            language=TextLanguage(conversation.language.value),
            status=MessageStatus.PENDING,
        )
        self._uow.session.add(message)
        await self._uow.session.flush()
        return message
