import uuid
from collections.abc import Sequence
from datetime import datetime

from app.ai.contracts import QualityIssue
from app.ai.engine import AiEngine
from app.core.config import Settings
from app.core.errors import AppError, ErrorCode, NotFoundError
from app.core.languages import Language, ensure_available
from app.db.unit_of_work import UnitOfWork
from app.integrations.storage import FileStorage, owner_prefix
from app.models import Document, DocumentExplanation, DocumentFile, User
from app.models.enums import (
    Channel,
    DocumentCategory,
    DocumentStatus,
    ExplanationVariant,
    UsageFeature,
)
from app.repositories.documents import DocumentRepository
from app.services import storage_keys
from app.services.billing_service import EntitlementService
from app.services.media import DetectedFile, FileKind, IncomingFile, detect, pdf_page_count
from app.workers.jobs import Job

_QUALITY_ERRORS = {
    QualityIssue.TOO_BLURRY: ErrorCode.IMAGE_TOO_BLURRY,
    QualityIssue.TOO_DARK: ErrorCode.IMAGE_TOO_DARK,
    QualityIssue.UNREADABLE: ErrorCode.IMAGE_UNREADABLE,
}


class DocumentService:
    def __init__(
        self,
        uow: UnitOfWork,
        ai: AiEngine,
        storage: FileStorage,
        settings: Settings,
    ) -> None:
        self._uow = uow
        self._ai = ai
        self._storage = storage
        self._settings = settings
        self._documents = DocumentRepository(uow.session)
        self._entitlements = EntitlementService(uow.session)

    async def create(
        self, user: User, files: Sequence[IncomingFile], *, source: Channel = Channel.APP
    ) -> Document:
        if not files:
            raise AppError(ErrorCode.FILE_MISSING)
        detected = [self._validate(file) for file in files]
        page_count = sum(pages for _, pages in detected)
        if page_count > self._settings.max_pages_per_document:
            raise AppError(
                ErrorCode.TOO_MANY_PAGES,
                fields={"max_pages": self._settings.max_pages_per_document},
            )
        for index, (file, (kind, _)) in enumerate(zip(files, detected, strict=True)):
            if kind.kind is FileKind.IMAGE:
                quality = await self._ai.check_image(file.content)
                if quality.issue is not None:
                    raise AppError(_QUALITY_ERRORS[quality.issue], fields={"page": index})

        document = Document(
            id=uuid.uuid4(),
            user_id=user.id,
            source=source,
            status=DocumentStatus.PENDING,
            page_count=page_count,
        )
        self._documents.add(document)
        for position, (file, (kind, _)) in enumerate(zip(files, detected, strict=True)):
            key = storage_keys.document_file(user, document.id, position, kind.extension)
            await self._storage.put(key, file.content, kind.mime_type)
            self._uow.session.add(
                DocumentFile(
                    document_id=document.id,
                    position=position,
                    file_key=key,
                    mime_type=kind.mime_type,
                    original_filename=file.filename,
                    size_bytes=len(file.content),
                )
            )
        await self._entitlements.consume(user, UsageFeature.DOCUMENT)
        self._uow.defer(
            Job.PROCESS_DOCUMENT, key=f"document:{document.id}", document_id=str(document.id)
        )
        await self._uow.commit()
        return document

    async def get(self, user: User, document_id: uuid.UUID) -> Document:
        document = await self._documents.owned(user.id, document_id, detailed=True)
        if document is None:
            raise NotFoundError("document")
        return document

    async def list_documents(
        self,
        user: User,
        *,
        category: DocumentCategory | None,
        before: datetime | None,
        limit: int,
    ) -> Sequence[Document]:
        return await self._documents.list_for_user(
            user.id, category=category, before=before, limit=limit
        )

    async def delete(self, user: User, document_id: uuid.UUID) -> None:
        document = await self._documents.owned(user.id, document_id)
        if document is None:
            raise NotFoundError("document")
        await self._documents.delete(document)
        prefix = owner_prefix(user.id, is_guest=user.is_guest)
        self._uow.defer(Job.DELETE_STORAGE_PREFIX, prefix=f"{prefix}/documents/{document.id}")
        await self._uow.commit()

    async def retry(self, user: User, document_id: uuid.UUID) -> Document:
        document = await self._documents.owned(user.id, document_id)
        if document is None:
            raise NotFoundError("document")
        if document.status is not DocumentStatus.FAILED:
            raise AppError(ErrorCode.CONFLICT)
        document.status = DocumentStatus.PENDING
        document.failure_reason = None
        self._uow.defer(Job.PROCESS_DOCUMENT, document_id=str(document.id))
        await self._uow.commit()
        return await self.get(user, document.id)

    async def request_explanation(
        self,
        user: User,
        document_id: uuid.UUID,
        variant: ExplanationVariant,
        language: Language | None = None,
    ) -> DocumentExplanation | None:
        document = await self._documents.owned(user.id, document_id)
        if document is None:
            raise NotFoundError("document")
        if document.status is not DocumentStatus.READY:
            raise AppError(ErrorCode.DOCUMENT_NOT_READY)
        target = ensure_available(language or user.language)
        existing = await self._documents.explanation(document.id, target, variant)
        if existing is not None:
            return existing
        self._uow.defer(
            Job.LOCALIZE_EXPLANATION,
            key=f"explanation:{document.id}:{target.value}:{variant.value}",
            document_id=str(document.id),
            language=target.value,
            variant=variant.value,
        )
        await self._uow.commit()
        return None

    def _validate(self, file: IncomingFile) -> tuple[DetectedFile, int]:
        if not file.content:
            raise AppError(ErrorCode.FILE_MISSING)
        detected = detect(file.content)
        limits = {
            FileKind.IMAGE: self._settings.max_image_bytes,
            FileKind.PDF: self._settings.max_pdf_bytes,
            FileKind.DOCX: self._settings.max_docx_bytes,
        }
        limit = limits[detected.kind]
        if len(file.content) > limit:
            raise AppError(ErrorCode.FILE_TOO_LARGE, fields={"max_bytes": limit})
        pages = pdf_page_count(file.content) if detected.kind is FileKind.PDF else 1
        return detected, pages
