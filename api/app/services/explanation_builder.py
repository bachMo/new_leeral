import asyncio
import logging
from datetime import date
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import DocumentContext
from app.ai.engine import AiEngine
from app.core.languages import Language
from app.core.logging import log_step
from app.integrations.storage import FileStorage
from app.models import (
    Document,
    DocumentExplanation,
    DocumentKeyPoint,
    DocumentSuggestedQuestion,
    User,
)
from app.models.enums import ExplanationVariant, KeyPointKind
from app.services import storage_keys
from app.services.narrator import Narrator

logger = logging.getLogger("leeral.explanations")

_PARALLEL_ITEMS = 4


class ExplanationBuilder:
    def __init__(self, ai: AiEngine, storage: FileStorage) -> None:
        self._ai = ai
        self._storage = storage
        self._narrator = Narrator(ai)
        self._semaphore = asyncio.Semaphore(_PARALLEL_ITEMS)

    async def build(
        self,
        session: AsyncSession,
        user: User,
        document: Document,
        context: DocumentContext,
        language: Language,
        variant: ExplanationVariant,
    ) -> DocumentExplanation:
        with log_step(
            logger, "explanation_built", language=language.value, variant=variant.value
        ) as out:
            text_fr = (
                context.summary_fr
                if variant is ExplanationVariant.STANDARD
                else await self._ai.simplify(context)
            )
            localized, audio = await self._narrator.voice(
                text_fr, language, protected_terms=context.protected_terms
            )
            audio_key = storage_keys.document_audio(
                user, document.id, f"explanation-{language.value}-{variant.value}"
            )
            await self._storage.put(audio_key, audio.content, audio.mime_type)
            await session.execute(
                delete(DocumentExplanation).where(
                    DocumentExplanation.document_id == document.id,
                    DocumentExplanation.language == language,
                    DocumentExplanation.variant == variant,
                )
            )
            explanation = DocumentExplanation(
                document_id=document.id,
                language=language,
                variant=variant,
                text=localized.text,
                text_fr=text_fr,
                audio_key=audio_key,
                audio_duration_s=audio.duration_s,
            )
            session.add(explanation)
            if variant is ExplanationVariant.STANDARD:
                await self._build_companions(session, user, document, context, language)
            out["audio_duration_s"] = audio.duration_s
            return explanation

    async def _build_companions(
        self,
        session: AsyncSession,
        user: User,
        document: Document,
        context: DocumentContext,
        language: Language,
    ) -> None:
        for model in (DocumentKeyPoint, DocumentSuggestedQuestion):
            await session.execute(
                delete(model).where(model.document_id == document.id, model.language == language)
            )
        drafts = (document.extracted_data or {}).get("key_points", [])
        questions = (document.extracted_data or {}).get("suggested_questions", [])

        async def point_audio(index: int, draft: dict[str, Any]) -> DocumentKeyPoint:
            spoken = ". ".join(part for part in (draft["title_fr"], draft.get("detail_fr")) if part)
            due_date = draft.get("due_date")
            key = await self._spoken_asset(
                user, document, f"point-{language.value}-{index}", spoken, language, context
            )
            return DocumentKeyPoint(
                document_id=document.id,
                language=language,
                position=index,
                kind=KeyPointKind(draft["kind"]),
                tag=draft["tag"] or "",
                title_fr=draft["title_fr"] or "",
                detail_fr=draft.get("detail_fr"),
                due_date=date.fromisoformat(due_date) if due_date else None,
                amount_xof=draft.get("amount_xof"),
                audio_key=key,
            )

        async def question_audio(index: int, text_fr: str) -> DocumentSuggestedQuestion:
            key = await self._spoken_asset(
                user, document, f"question-{language.value}-{index}", text_fr, language, context
            )
            return DocumentSuggestedQuestion(
                document_id=document.id,
                language=language,
                position=index,
                text_fr=text_fr,
                audio_key=key,
            )

        rows = await asyncio.gather(
            *(point_audio(index, draft) for index, draft in enumerate(drafts)),
            *(question_audio(index, text) for index, text in enumerate(questions)),
        )
        session.add_all(rows)

    async def _spoken_asset(
        self,
        user: User,
        document: Document,
        name: str,
        text_fr: str,
        language: Language,
        context: DocumentContext,
    ) -> str:
        async with self._semaphore:
            _, audio = await self._narrator.voice(
                text_fr, language, protected_terms=context.protected_terms
            )
        key = storage_keys.document_audio(user, document.id, name)
        await self._storage.put(key, audio.content, audio.mime_type)
        return key
