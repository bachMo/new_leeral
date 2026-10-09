import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, exists, select, update
from sqlalchemy.orm import selectinload

from app.core.languages import Language
from app.models import (
    Document,
    DocumentExplanation,
    DocumentFile,
    DocumentKeyPoint,
    DocumentSuggestedQuestion,
    DocumentWord,
    PrescriptionLine,
    User,
)
from app.models.enums import DocumentCategory, DocumentStatus, ExplanationVariant
from app.repositories.base import Repository

_DETAIL_OPTIONS = (
    selectinload(Document.files),
    selectinload(Document.explanations),
    selectinload(Document.key_points),
    selectinload(Document.suggested_questions),
    selectinload(Document.prescription_lines),
)


class DocumentRepository(Repository[Document]):
    model = Document

    async def ready_without_words(self, user_id: uuid.UUID, limit: int) -> Sequence[uuid.UUID]:
        return (
            await self.session.scalars(
                select(Document.id)
                .where(
                    Document.user_id == user_id,
                    Document.status == DocumentStatus.READY,
                    ~exists().where(DocumentWord.document_id == Document.id),
                )
                .order_by(Document.created_at.desc())
                .limit(limit)
            )
        ).all()

    async def owned(
        self, user_id: uuid.UUID, document_id: uuid.UUID, *, detailed: bool = False
    ) -> Document | None:
        statement = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        if detailed:
            statement = statement.options(*_DETAIL_OPTIONS)
        return await self.session.scalar(statement)

    async def detailed(self, document_id: uuid.UUID) -> Document | None:
        return await self.session.scalar(
            select(Document)
            .where(Document.id == document_id)
            .options(*_DETAIL_OPTIONS)
            .execution_options(populate_existing=True)
        )

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        category: DocumentCategory | None,
        before: datetime | None,
        limit: int,
    ) -> Sequence[Document]:
        statement = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
            .limit(limit)
        )
        if category is not None:
            statement = statement.where(Document.category == category)
        if before is not None:
            statement = statement.where(Document.created_at < before)
        return (await self.session.scalars(statement)).all()

    async def explanation(
        self, document_id: uuid.UUID, language: Language, variant: ExplanationVariant
    ) -> DocumentExplanation | None:
        return await self.session.scalar(
            select(DocumentExplanation).where(
                DocumentExplanation.document_id == document_id,
                DocumentExplanation.language == language,
                DocumentExplanation.variant == variant,
            )
        )

    async def clear_analysis(self, document_id: uuid.UUID) -> None:
        for model in (
            DocumentExplanation,
            DocumentKeyPoint,
            DocumentSuggestedQuestion,
            PrescriptionLine,
        ):
            await self.session.execute(delete(model).where(model.document_id == document_id))

    async def expired_guest_documents(
        self, created_before: datetime, limit: int
    ) -> Sequence[Document]:
        return (
            await self.session.scalars(
                select(Document)
                .join(User, User.id == Document.user_id)
                .where(User.is_guest.is_(True), Document.created_at < created_before)
                .order_by(Document.created_at)
                .limit(limit)
            )
        ).all()

    async def ids_for_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return list(
            await self.session.scalars(select(Document.id).where(Document.user_id == user_id))
        )

    async def reassign(self, source_user_id: uuid.UUID, target_user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Document)
            .where(Document.user_id == source_user_id)
            .values(user_id=target_user_id)
        )


class DocumentFileRepository(Repository[DocumentFile]):
    model = DocumentFile
