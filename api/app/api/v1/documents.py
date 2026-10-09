import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from app.api.deps import (
    Container,
    ConversationServiceDep,
    CurrentUser,
    DocumentServiceDep,
    PresenterDep,
    WritingServiceDep,
)
from app.api.uploads import read_upload
from app.models.enums import DocumentCategory
from app.schemas.conversations import ConversationOut
from app.schemas.documents import (
    DocumentOut,
    DocumentPageOut,
    ExplanationRequestIn,
    ExplanationRequestOut,
    LibraryItemOut,
)

router = APIRouter(tags=["documents"])


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    files: Annotated[list[UploadFile], File(description="Photos, PDF or DOCX, in page order")],
    user: CurrentUser,
    service: DocumentServiceDep,
    presenter: PresenterDep,
    container: Container,
) -> DocumentOut:
    max_bytes = max(
        container.settings.max_image_bytes,
        container.settings.max_pdf_bytes,
        container.settings.max_docx_bytes,
    )
    incoming = [
        await read_upload(upload, max_bytes=max_bytes, default_name=f"page-{index + 1}")
        for index, upload in enumerate(files)
    ]
    document = await service.create(user, incoming)
    return presenter.document(await service.get(user, document.id), user.language)


@router.get("/documents", response_model=DocumentPageOut)
async def list_documents(
    user: CurrentUser,
    service: DocumentServiceDep,
    presenter: PresenterDep,
    category: DocumentCategory | None = None,
    before: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> DocumentPageOut:
    documents = await service.list_documents(user, category=category, before=before, limit=limit)
    return DocumentPageOut(
        items=[presenter.document_summary(document) for document in documents],
        next_before=documents[-1].created_at if len(documents) == limit else None,
    )


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def read_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    service: DocumentServiceDep,
    presenter: PresenterDep,
) -> DocumentOut:
    return presenter.document(await service.get(user, document_id), user.language)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID, user: CurrentUser, service: DocumentServiceDep
) -> None:
    await service.delete(user, document_id)


@router.post(
    "/documents/{document_id}/retry",
    response_model=DocumentOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    service: DocumentServiceDep,
    presenter: PresenterDep,
) -> DocumentOut:
    return presenter.document(await service.retry(user, document_id), user.language)


@router.post(
    "/documents/{document_id}/explanations",
    response_model=ExplanationRequestOut,
    responses={202: {"model": ExplanationRequestOut}},
)
async def request_explanation(
    document_id: uuid.UUID,
    body: ExplanationRequestIn,
    user: CurrentUser,
    service: DocumentServiceDep,
    presenter: PresenterDep,
    response: Response,
) -> ExplanationRequestOut:
    explanation = await service.request_explanation(user, document_id, body.variant, body.language)
    if explanation is None:
        response.status_code = status.HTTP_202_ACCEPTED
        return ExplanationRequestOut(status="pending")
    return ExplanationRequestOut(status="ready", explanation=presenter.explanation(explanation))


@router.post("/documents/{document_id}/conversation", response_model=ConversationOut)
async def open_document_conversation(
    document_id: uuid.UUID,
    user: CurrentUser,
    service: ConversationServiceDep,
    presenter: PresenterDep,
) -> ConversationOut:
    conversation = await service.open_for_document(user, document_id)
    return presenter.conversation(conversation, await service.documents_for(conversation.id))


@router.get("/library", response_model=list[LibraryItemOut])
async def library(
    user: CurrentUser,
    documents: DocumentServiceDep,
    writings: WritingServiceDep,
    presenter: PresenterDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[LibraryItemOut]:
    items = presenter.library(
        await documents.list_documents(user, category=None, before=None, limit=limit),
        await writings.list_writings(user, before=None, limit=limit),
    )
    return items[:limit]
