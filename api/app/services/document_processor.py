import asyncio
import logging
import uuid
from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.contracts import DocumentAnalysis, PageInput
from app.ai.engine import AiEngine
from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError, ErrorCode
from app.core.languages import Language
from app.integrations.storage import FileStorage
from app.models import Document, User
from app.models.enums import (
    AiJobType,
    DocumentCategory,
    DocumentStatus,
    ExplanationVariant,
    Urgency,
)
from app.repositories.documents import DocumentRepository
from app.services.ai_jobs import AiJobRefs, AiJobTracker
from app.services.ai_mapping import document_context, row_from_medication
from app.services.explanation_builder import ExplanationBuilder
from app.services.media import build_pages, detect

logger = logging.getLogger("leeral.documents")


class DocumentProcessor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ai: AiEngine,
        storage: FileStorage,
        tracker: AiJobTracker,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._ai = ai
        self._storage = storage
        self._tracker = tracker
        self._settings = settings
        self._builder = ExplanationBuilder(ai, storage)

    async def process(self, document_id: uuid.UUID) -> DocumentStatus | None:
        async with self._session_factory() as session:
            documents = DocumentRepository(session)
            document = await documents.detailed(document_id)
            if document is None or document.status is DocumentStatus.READY:
                return document.status if document else None
            user = await session.get(User, document.user_id)
            if user is None:
                return None
            document.status = DocumentStatus.PROCESSING
            await session.commit()

            try:
                status = await self._analyze(session, documents, document, user)
            except AppError as exc:
                await session.rollback()
                logger.warning(
                    "document_failed", extra={"document_id": str(document_id), "code": exc.code}
                )
                return await self._mark(session, document_id, DocumentStatus.FAILED, exc.code)
            except Exception:
                await session.rollback()
                logger.exception("document_crashed", extra={"document_id": str(document_id)})
                return await self._mark(
                    session, document_id, DocumentStatus.FAILED, ErrorCode.INTERNAL_ERROR
                )
            await session.commit()
            logger.info(
                "document_processed",
                extra={"document_id": str(document_id), "status": status.value},
            )
            return status

    async def localize(
        self, document_id: uuid.UUID, language: Language, variant: ExplanationVariant
    ) -> None:
        async with self._session_factory() as session:
            document = await DocumentRepository(session).detailed(document_id)
            if document is None or document.status is not DocumentStatus.READY:
                return
            user = await session.get(User, document.user_id)
            if user is None:
                return
            if any(
                item.language == language and item.variant == variant
                for item in document.explanations
            ):
                return
            context = document_context(document, document.prescription_lines)
            async with self._tracker.track(
                AiJobType.LOCALIZE_EXPLANATION,
                AiJobRefs(user_id=user.id, document_id=document.id),
                language=language.value,
                variant=variant.value,
            ):
                await self._builder.build(session, user, document, context, language, variant)
            await session.commit()

    async def _analyze(
        self, session: AsyncSession, documents: DocumentRepository, document: Document, user: User
    ) -> DocumentStatus:
        pages = await self._pages(document)
        async with self._tracker.track(
            AiJobType.EXPLAIN_DOCUMENT,
            AiJobRefs(user_id=user.id, document_id=document.id),
            pages=len(pages),
            language=user.language.value,
        ) as job:
            analysis = await self._ai.analyze_document(pages)
            if not analysis.readable:
                document.status = DocumentStatus.UNREADABLE
                document.failure_reason = ErrorCode.DOCUMENT_UNREADABLE.value
                document.ocr_text = analysis.full_text or None
                job.output = {"readable": False}
                return document.status
            self._apply(document, analysis)
            await documents.clear_analysis(document.id)
            lines = [row_from_medication(document.id, line) for line in analysis.medications]
            session.add_all(lines)
            await session.flush()
            await self._builder.build(
                session,
                user,
                document,
                document_context(document, lines),
                user.language,
                ExplanationVariant.STANDARD,
            )
            document.status = DocumentStatus.READY
            document.failure_reason = None
            document.processed_at = utcnow()
            job.output = {
                "doc_type": analysis.doc_type,
                "pages": len(pages),
                "key_points": len(analysis.key_points),
                "medications": len(analysis.medications),
            }
        return document.status

    async def _pages(self, document: Document) -> list[PageInput]:
        contents = await asyncio.gather(
            *(self._storage.get(file.file_key) for file in document.files)
        )
        files = [
            (detect(content), content, file.original_filename or f"page-{file.position + 1}")
            for file, content in zip(document.files, contents, strict=True)
        ]
        return await asyncio.to_thread(build_pages, files, self._settings.max_pages_per_document)

    @staticmethod
    def _apply(document: Document, analysis: DocumentAnalysis) -> None:
        document.title = analysis.title
        document.doc_type = analysis.doc_type
        document.category = DocumentCategory(analysis.category)
        document.issuer = analysis.issuer
        document.document_date = analysis.document_date
        document.urgency = Urgency(analysis.urgency)
        document.urgency_label = analysis.urgency_label
        document.main_due_date = analysis.main_due_date
        document.main_amount_xof = analysis.main_amount_xof
        document.ocr_text = analysis.full_text
        document.summary_fr = analysis.summary_fr
        if len(document.files) == len(analysis.page_texts):
            for file, text in zip(document.files, analysis.page_texts, strict=True):
                file.ocr_text = text or None
        document.extracted_data = {
            **analysis.extracted_data,
            "key_points": [
                {
                    **asdict(point),
                    "due_date": point.due_date.isoformat() if point.due_date else None,
                }
                for point in analysis.key_points
            ],
            "suggested_questions": list(analysis.suggested_questions_fr),
            "protected_terms": list(analysis.protected_terms),
        }

    async def _mark(
        self,
        session: AsyncSession,
        document_id: uuid.UUID,
        status: DocumentStatus,
        code: ErrorCode,
    ) -> DocumentStatus:
        document = await session.get(Document, document_id, populate_existing=True)
        if document is not None:
            document.status = status
            document.failure_reason = code.value
            await session.commit()
        return status
