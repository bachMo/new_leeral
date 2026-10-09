import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.engine import AiEngine
from app.core.languages import Language
from app.integrations.storage import FileStorage
from app.models import Document, User, Word, WordTranslation
from app.models.enums import AiJobType, DocumentStatus, WordCategory
from app.repositories.learning import UserWordRepository, WordRepository
from app.services import storage_keys
from app.services.ai_jobs import AiJobRefs, AiJobTracker
from app.services.billing_service import EntitlementService

logger = logging.getLogger("leeral.vocabulary")

WORDS_PER_DOCUMENT = 6
WORD_INTRODUCTIONS: dict[Language, str] = {
    Language.WOLOF: "Baat bi mooy",
    Language.PULAAR: "Konngol ngol ko",
}


def spoken_meaning(meaning: str, language: Language) -> str:
    text = meaning.strip().rstrip(".!?…")
    introduction = WORD_INTRODUCTIONS.get(language)
    return f"{introduction}: {text}." if introduction else f"{text}."


class VocabularyBuilder:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ai: AiEngine,
        storage: FileStorage,
        tracker: AiJobTracker,
    ) -> None:
        self._session_factory = session_factory
        self._ai = ai
        self._storage = storage
        self._tracker = tracker

    async def ensure_translation(
        self, session: AsyncSession, word: Word, language: Language
    ) -> WordTranslation:
        words = WordRepository(session)
        existing = await words.translation(word.id, language)
        if existing is not None:
            return existing
        localized = await self._ai.localize(word.word_fr, language)
        audio = await self._ai.speak(spoken_meaning(localized.text, language), language)
        key = storage_keys.word_audio(word.id, language)
        await self._storage.put(key, audio.content, audio.mime_type)
        translation = WordTranslation(
            word_id=word.id,
            language=language,
            meaning=localized.text,
            audio_key=key,
            validated=False,
        )
        session.add(translation)
        return translation

    async def revoice(self, translation: WordTranslation) -> str:
        audio = await self._ai.speak(
            spoken_meaning(translation.meaning, translation.language), translation.language
        )
        key = storage_keys.word_audio(translation.word_id, translation.language)
        await self._storage.put(key, audio.content, audio.mime_type)
        previous, translation.audio_key = translation.audio_key, key
        return previous

    async def get_or_create_word(
        self,
        session: AsyncSession,
        word_fr: str,
        category: WordCategory,
        example_fr: str | None,
        *,
        is_core: bool = False,
    ) -> Word:
        words = WordRepository(session)
        word = await words.by_text(word_fr)
        if word is None:
            word = Word(
                id=uuid.uuid4(),
                word_fr=word_fr,
                category=category,
                example_fr=example_fr,
                is_core=is_core,
            )
            session.add(word)
            await session.flush()
        elif is_core and not word.is_core:
            word.is_core = True
        return word

    async def extract_from_document(self, document_id: uuid.UUID) -> int:
        async with self._session_factory() as session:
            document = await session.get(Document, document_id)
            if document is None or document.status is not DocumentStatus.READY:
                return 0
            if not document.ocr_text or document.is_prescription:
                return 0
            user = await session.get(User, document.user_id)
            if user is None:
                return 0
            if not await EntitlementService(session).has_document_words(user):
                return 0
            words = WordRepository(session)
            user_words = UserWordRepository(session)
            async with self._tracker.track(
                AiJobType.EXTRACT_WORDS,
                AiJobRefs(user_id=user.id, document_id=document.id),
                limit=WORDS_PER_DOCUMENT,
            ) as job:
                candidates = await self._ai.extract_vocabulary(
                    document.ocr_text, limit=WORDS_PER_DOCUMENT
                )
                for candidate in candidates:
                    word = await self.get_or_create_word(
                        session,
                        candidate.word_fr,
                        WordCategory(candidate.category),
                        None,
                    )
                    await self.ensure_translation(session, word, user.language)
                    await words.link_document(document.id, word.id, candidate.sentence_fr)
                    await user_words.ensure(user.id, word.id, document.id)
                job.output = {"words": len(candidates)}
            await session.commit()
            logger.info(
                "vocabulary_extracted",
                extra={"document_id": str(document_id), "words": len(candidates)},
            )
            return len(candidates)
