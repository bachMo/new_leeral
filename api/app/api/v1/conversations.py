import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.deps import Container, ConversationServiceDep, CurrentUser, PresenterDep
from app.api.uploads import read_upload
from app.core.languages import TextLanguage
from app.schemas.conversations import ConversationOut, ExchangeOut, MessageOut
from app.services.conversation_service import Question

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def question_from_form(
    container: Container,
    text: str | None,
    text_language: TextLanguage | None,
    suggested_question_id: uuid.UUID | None,
    audio: UploadFile | None,
) -> Question:
    incoming = (
        await read_upload(
            audio, max_bytes=container.settings.max_audio_bytes, default_name="question.ogg"
        )
        if audio is not None
        else None
    )
    return Question(
        text=text,
        text_language=text_language,
        audio=incoming,
        suggested_question_id=suggested_question_id,
    )


@router.get("/{conversation_id}", response_model=ConversationOut)
async def read_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, service: ConversationServiceDep
) -> ConversationOut:
    conversation = await service.get(user, conversation_id)
    document_ids = await service.documents_for(conversation.id)
    return ConversationOut(
        id=conversation.id,
        kind=conversation.kind,
        document_id=conversation.document_id,
        document_ids=list(document_ids),
        language=conversation.language,
        last_message_at=conversation.last_message_at,
        created_at=conversation.created_at,
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    service: ConversationServiceDep,
    presenter: PresenterDep,
    after: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[MessageOut]:
    messages = await service.messages(user, conversation_id, after=after, limit=limit)
    return [presenter.message(message) for message in messages]


@router.post(
    "/{conversation_id}/messages",
    response_model=ExchangeOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ask(
    conversation_id: uuid.UUID,
    user: CurrentUser,
    service: ConversationServiceDep,
    presenter: PresenterDep,
    container: Container,
    text: Annotated[str | None, Form(max_length=2000)] = None,
    text_language: Annotated[TextLanguage | None, Form()] = None,
    suggested_question_id: Annotated[uuid.UUID | None, Form()] = None,
    audio: Annotated[UploadFile | None, File()] = None,
    document_id: Annotated[uuid.UUID | None, Form()] = None,
) -> ExchangeOut:
    conversation = await service.get(user, conversation_id)
    question = await question_from_form(
        container, text, text_language, suggested_question_id, audio
    )
    exchange = await service.ask(user, conversation, question, target_document_id=document_id)
    return ExchangeOut(
        question=presenter.message(exchange.question), answer=presenter.message(exchange.answer)
    )
