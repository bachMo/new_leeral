import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status

from app.api.deps import (
    AdminAuthServiceDep,
    Container,
    CurrentAdmin,
    InboxSenderDep,
    InboxServiceDep,
)
from app.core.errors import AppError, ErrorCode
from app.schemas.inbox import (
    AdminLoginIn,
    AdminOut,
    AdminRefreshIn,
    AdminTokenOut,
    BotStateIn,
    MediaLinkOut,
    MessageOut,
    MessagePageOut,
    ThreadDetailOut,
    ThreadFilter,
    ThreadOut,
    ThreadPageOut,
)
from app.services.admin_auth_service import AdminTokens
from app.services.inbox_media import OutgoingKind
from app.services.inbox_sender import OutgoingMessage, Upload

SEARCH_MAX_LENGTH = 100


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(_no_store)])


def _tokens(result: AdminTokens) -> AdminTokenOut:
    return AdminTokenOut(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
        admin=AdminOut.model_validate(result.admin),
    )


@router.post("/auth/login", response_model=AdminTokenOut)
async def login(
    body: AdminLoginIn, request: Request, service: AdminAuthServiceDep
) -> AdminTokenOut:
    return _tokens(
        await service.login(body.email, body.password, request.headers.get("user-agent"))
    )


@router.post("/auth/refresh", response_model=AdminTokenOut)
async def refresh(body: AdminRefreshIn, service: AdminAuthServiceDep) -> AdminTokenOut:
    return _tokens(await service.refresh(body.refresh_token))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(principal: CurrentAdmin, service: AdminAuthServiceDep) -> None:
    await service.logout(principal.session_id)


@router.get("/me", response_model=AdminOut)
async def me(principal: CurrentAdmin) -> AdminOut:
    return AdminOut.model_validate(principal.admin)


@router.get("/inbox/threads", response_model=ThreadPageOut)
async def list_threads(
    _: CurrentAdmin,
    service: InboxServiceDep,
    q: Annotated[str | None, Query(max_length=SEARCH_MAX_LENGTH)] = None,
    filter: Annotated[ThreadFilter, Query()] = "all",
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> ThreadPageOut:
    return await service.list_threads(query=q or None, thread_filter=filter, offset=offset)


@router.get("/inbox/threads/{thread_id}", response_model=ThreadDetailOut)
async def thread_detail(
    thread_id: uuid.UUID, _: CurrentAdmin, service: InboxServiceDep
) -> ThreadDetailOut:
    return await service.thread_detail(thread_id)


@router.get("/inbox/threads/{thread_id}/messages", response_model=MessagePageOut)
async def thread_messages(
    thread_id: uuid.UUID,
    _: CurrentAdmin,
    service: InboxServiceDep,
    before: uuid.UUID | None = None,
    updated_after: datetime | None = None,
) -> MessagePageOut:
    return await service.messages(thread_id, before_id=before, updated_after=updated_after)


@router.post(
    "/inbox/threads/{thread_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    thread_id: uuid.UUID,
    principal: CurrentAdmin,
    sender: InboxSenderDep,
    container: Container,
    type: Annotated[OutgoingKind, Form()],
    text: Annotated[str | None, Form(max_length=4096)] = None,
    reply_to: Annotated[uuid.UUID | None, Form()] = None,
    contact_name: Annotated[str | None, Form(max_length=100)] = None,
    contact_phone: Annotated[str | None, Form(max_length=32)] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> MessageOut:
    upload = None
    if file is not None:
        limit = container.settings.inbox_max_upload_bytes
        content = await file.read(limit + 1)
        if len(content) > limit:
            raise AppError(ErrorCode.FILE_TOO_LARGE, fields={"max_mb": limit // (1024 * 1024)})
        upload = Upload(content=content, content_type=file.content_type, filename=file.filename)
    return await sender.send(
        principal.admin,
        thread_id,
        OutgoingMessage(
            kind=type,
            text=text,
            upload=upload,
            reply_to=reply_to,
            contact_name=contact_name,
            contact_phone=contact_phone,
        ),
    )


@router.post("/inbox/threads/{thread_id}/read", response_model=ThreadOut)
async def mark_read(thread_id: uuid.UUID, _: CurrentAdmin, service: InboxServiceDep) -> ThreadOut:
    return await service.mark_read(thread_id)


@router.put("/inbox/threads/{thread_id}/bot", response_model=ThreadOut)
async def set_bot(
    thread_id: uuid.UUID, body: BotStateIn, _: CurrentAdmin, service: InboxServiceDep
) -> ThreadOut:
    return await service.set_bot(thread_id, paused=body.paused)


@router.get("/inbox/messages/{message_id}/media", response_model=MediaLinkOut)
async def message_media(
    message_id: uuid.UUID, _: CurrentAdmin, service: InboxServiceDep
) -> MediaLinkOut:
    return await service.media(message_id)
