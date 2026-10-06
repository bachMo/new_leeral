import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.deps import Container, CurrentAccount, PresenterDep, WritingServiceDep
from app.api.v1.conversations import question_from_form
from app.core.languages import TextLanguage
from app.schemas.conversations import MessageOut
from app.schemas.writings import (
    WritingConfirmIn,
    WritingOut,
    WritingStartIn,
    WritingStepSpecOut,
    WritingTypeOut,
)
from app.services.writing_catalog import WRITING_TEMPLATES

router = APIRouter(prefix="/writings", tags=["writings"])


@router.get("/types", response_model=list[WritingTypeOut])
async def writing_types() -> list[WritingTypeOut]:
    return [
        WritingTypeOut(
            type=template.type,
            title_fr=template.title_fr,
            description_fr=template.description_fr,
            steps=[
                WritingStepSpecOut(
                    key=step.key, question_fr=step.question_fr, required=step.required
                )
                for step in template.steps
            ],
        )
        for template in WRITING_TEMPLATES.values()
    ]


@router.post("", response_model=WritingOut, status_code=status.HTTP_201_CREATED)
async def start_writing(
    body: WritingStartIn,
    user: CurrentAccount,
    service: WritingServiceDep,
    presenter: PresenterDep,
) -> WritingOut:
    return presenter.writing(await service.start(user, body.type))


@router.get("", response_model=list[WritingOut])
async def list_writings(
    user: CurrentAccount,
    service: WritingServiceDep,
    presenter: PresenterDep,
    before: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[WritingOut]:
    writings = await service.list_writings(user, before=before, limit=limit)
    return [presenter.writing(await service.get(user, writing.id)) for writing in writings]


@router.get("/{writing_id}", response_model=WritingOut)
async def read_writing(
    writing_id: uuid.UUID,
    user: CurrentAccount,
    service: WritingServiceDep,
    presenter: PresenterDep,
) -> WritingOut:
    return presenter.writing(await service.get(user, writing_id))


@router.post(
    "/{writing_id}/answers", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED
)
async def answer_step(
    writing_id: uuid.UUID,
    user: CurrentAccount,
    service: WritingServiceDep,
    presenter: PresenterDep,
    container: Container,
    text: Annotated[str | None, Form(max_length=2000)] = None,
    text_language: Annotated[TextLanguage | None, Form()] = None,
    audio: Annotated[UploadFile | None, File()] = None,
) -> MessageOut:
    question = await question_from_form(container, text, text_language, None, audio)
    return presenter.message(await service.answer(user, writing_id, question))


@router.post("/{writing_id}/confirm", response_model=WritingOut)
async def confirm_step(
    writing_id: uuid.UUID,
    body: WritingConfirmIn,
    user: CurrentAccount,
    service: WritingServiceDep,
    presenter: PresenterDep,
) -> WritingOut:
    return presenter.writing(await service.confirm(user, writing_id, accepted=body.accepted))


@router.post("/{writing_id}/skip", response_model=WritingOut)
async def skip_step(
    writing_id: uuid.UUID,
    user: CurrentAccount,
    service: WritingServiceDep,
    presenter: PresenterDep,
) -> WritingOut:
    return presenter.writing(await service.skip(user, writing_id))
