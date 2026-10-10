import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.languages import Language
from app.models import (
    DocumentWord,
    PracticeAnswer,
    PracticeSession,
    UserWord,
    Word,
    WordTranslation,
)
from app.repositories.base import Repository


class WordRepository(Repository[Word]):
    model = Word

    async def by_text(self, word_fr: str) -> Word | None:
        return await self.session.scalar(select(Word).where(Word.word_fr == word_fr))

    async def core_words(self) -> Sequence[Word]:
        return (await self.session.scalars(select(Word).where(Word.is_core.is_(True)))).all()

    async def translation(self, word_id: uuid.UUID, language: Language) -> WordTranslation | None:
        return await self.session.scalar(
            select(WordTranslation).where(
                WordTranslation.word_id == word_id, WordTranslation.language == language
            )
        )

    async def translations_for(
        self, word_ids: Sequence[uuid.UUID], language: Language
    ) -> dict[uuid.UUID, WordTranslation]:
        rows = await self.session.scalars(
            select(WordTranslation).where(
                WordTranslation.word_id.in_(word_ids), WordTranslation.language == language
            )
        )
        return {row.word_id: row for row in rows}

    async def translated_words(self, language: Language, *, limit: int) -> Sequence[Word]:
        return (
            await self.session.scalars(
                select(Word)
                .join(WordTranslation, WordTranslation.word_id == Word.id)
                .where(WordTranslation.language == language)
                .order_by(Word.is_core.desc(), Word.word_fr)
                .limit(limit)
            )
        ).all()

    async def link_document(
        self, document_id: uuid.UUID, word_id: uuid.UUID, sentence: str
    ) -> None:
        await self.session.execute(
            insert(DocumentWord)
            .values(document_id=document_id, word_id=word_id, sentence_fr=sentence)
            .on_conflict_do_nothing(index_elements=["document_id", "word_id"])
        )


class UserWordRepository(Repository[UserWord]):
    model = UserWord

    async def ensure(
        self, user_id: uuid.UUID, word_id: uuid.UUID, source_document_id: uuid.UUID | None
    ) -> None:
        await self.session.execute(
            insert(UserWord)
            .values(user_id=user_id, word_id=word_id, source_document_id=source_document_id)
            .on_conflict_do_nothing(index_elements=["user_id", "word_id"])
        )

    async def of_user(self, user_id: uuid.UUID, word_id: uuid.UUID) -> UserWord | None:
        return await self.session.scalar(
            select(UserWord).where(UserWord.user_id == user_id, UserWord.word_id == word_id)
        )

    async def due(
        self, user_id: uuid.UUID, language: Language, now: datetime, limit: int
    ) -> Sequence[UserWord]:
        return (
            await self.session.scalars(
                select(UserWord)
                .join(
                    WordTranslation,
                    (WordTranslation.word_id == UserWord.word_id)
                    & (WordTranslation.language == language),
                )
                .where(UserWord.user_id == user_id, UserWord.next_review_at <= now)
                .order_by(UserWord.next_review_at, func.random())
                .limit(limit)
            )
        ).all()

    async def listing(
        self, user_id: uuid.UUID, *, limit: int, offset: int
    ) -> Sequence[tuple[UserWord, Word]]:
        rows = await self.session.execute(
            select(UserWord, Word)
            .join(Word, Word.id == UserWord.word_id)
            .where(UserWord.user_id == user_id)
            .order_by(UserWord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [(row[0], row[1]) for row in rows.all()]

    async def stats(self, user_id: uuid.UUID, now: datetime) -> tuple[int, int, int]:
        row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.count().filter(UserWord.mastered.is_(True)),
                    func.count().filter(UserWord.next_review_at <= now),
                ).where(UserWord.user_id == user_id)
            )
        ).one()
        return int(row[0]), int(row[1]), int(row[2])


class PracticeSessionRepository(Repository[PracticeSession]):
    model = PracticeSession

    async def owned(self, user_id: uuid.UUID, session_id: uuid.UUID) -> PracticeSession | None:
        return await self.session.scalar(
            select(PracticeSession)
            .where(PracticeSession.id == session_id, PracticeSession.user_id == user_id)
            .with_for_update()
        )

    async def answered_word_ids(self, session_id: uuid.UUID) -> set[uuid.UUID]:
        rows = await self.session.scalars(
            select(PracticeAnswer.word_id).where(PracticeAnswer.session_id == session_id)
        )
        return set(rows)


class PracticeAnswerRepository(Repository[PracticeAnswer]):
    model = PracticeAnswer
