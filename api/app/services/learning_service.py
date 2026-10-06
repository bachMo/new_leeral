import random
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from app.core.clock import utcnow
from app.core.config import Settings
from app.core.errors import AppError, ErrorCode, NotFoundError
from app.db.unit_of_work import UnitOfWork
from app.models import PracticeAnswer, PracticeSession, User, UserWord, Word, WordTranslation
from app.models.enums import UsageFeature
from app.repositories.learning import (
    PracticeAnswerRepository,
    PracticeSessionRepository,
    UserWordRepository,
    WordRepository,
)
from app.services.billing_service import EntitlementService, UsageSnapshot

REVIEW_INTERVALS = (
    timedelta(minutes=10),
    timedelta(days=1),
    timedelta(days=3),
    timedelta(days=7),
    timedelta(days=14),
    timedelta(days=30),
)
MASTERED_BOX = len(REVIEW_INTERVALS) - 1
CHOICES_PER_EXERCISE = 4
CORE_WORDS_FOR_BEGINNERS = 12
_random = random.SystemRandom()


@dataclass(frozen=True, slots=True)
class Exercise:
    word: Word
    translation: WordTranslation
    choices: tuple[Word, ...]


@dataclass(frozen=True, slots=True)
class PracticeRound:
    session: PracticeSession
    exercises: tuple[Exercise, ...]


@dataclass(frozen=True, slots=True)
class AnswerResult:
    is_correct: bool
    correct_word: Word
    user_word: UserWord
    session: PracticeSession


@dataclass(frozen=True, slots=True)
class LearningOverview:
    total_words: int
    mastered_words: int
    due_words: int
    usage: UsageSnapshot


class LearningService:
    def __init__(self, uow: UnitOfWork, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings
        self._words = WordRepository(uow.session)
        self._user_words = UserWordRepository(uow.session)
        self._sessions = PracticeSessionRepository(uow.session)
        self._answers = PracticeAnswerRepository(uow.session)
        self._entitlements = EntitlementService(uow.session)

    async def overview(self, user: User) -> LearningOverview:
        await self._ensure_core_words(user)
        await self._uow.commit()
        total, mastered, due = await self._user_words.stats(user.id, utcnow())
        return LearningOverview(
            total_words=total,
            mastered_words=mastered,
            due_words=due,
            usage=await self._entitlements.usage(user),
        )

    async def my_words(
        self, user: User, *, limit: int, offset: int
    ) -> list[tuple[UserWord, Word, WordTranslation | None]]:
        rows = await self._user_words.listing(user.id, limit=limit, offset=offset)
        translations = await self._words.translations_for(
            [word.id for _, word in rows], user.language
        )
        return [(user_word, word, translations.get(word.id)) for user_word, word in rows]

    async def start(self, user: User) -> PracticeRound:
        await self._ensure_core_words(user)
        now = utcnow()
        due = await self._user_words.due(
            user.id, user.language, now, self._settings.practice_session_size
        )
        if not due:
            raise AppError(ErrorCode.NOT_ENOUGH_WORDS)
        pool = await self._words.translated_words(user.language, limit=200)
        if len(pool) < CHOICES_PER_EXERCISE:
            raise AppError(ErrorCode.NOT_ENOUGH_WORDS)
        await self._entitlements.consume(user, UsageFeature.PRACTICE)

        word_ids = [user_word.word_id for user_word in due]
        words = {word.id: word for word in pool}
        missing = [word_id for word_id in word_ids if word_id not in words]
        for word_id in missing:
            if (word := await self._words.get(word_id)) is not None:
                words[word.id] = word
        translations = await self._words.translations_for(word_ids, user.language)
        session = self._sessions.add(
            PracticeSession(
                id=uuid.uuid4(), user_id=user.id, language=user.language, started_at=now
            )
        )
        exercises = tuple(
            Exercise(
                word=words[word_id],
                translation=translations[word_id],
                choices=self._choices(words[word_id], pool),
            )
            for word_id in word_ids
            if word_id in translations and word_id in words
        )
        await self._uow.commit()
        return PracticeRound(session=session, exercises=exercises)

    async def answer(
        self,
        user: User,
        session_id: uuid.UUID,
        word_id: uuid.UUID,
        chosen_word_id: uuid.UUID,
    ) -> AnswerResult:
        session = await self._sessions.owned(user.id, session_id)
        if session is None:
            raise NotFoundError("practice session")
        if session.finished_at is not None:
            raise AppError(ErrorCode.PRACTICE_SESSION_CLOSED)
        if word_id in await self._sessions.answered_word_ids(session.id):
            raise AppError(ErrorCode.CONFLICT)
        user_word = await self._user_words.of_user(user.id, word_id)
        word = await self._words.get(word_id)
        if user_word is None or word is None or await self._words.get(chosen_word_id) is None:
            raise NotFoundError("word")
        is_correct = chosen_word_id == word_id
        self._answers.add(
            PracticeAnswer(
                session_id=session.id,
                word_id=word_id,
                chosen_word_id=chosen_word_id,
                is_correct=is_correct,
            )
        )
        self._schedule(user_word, is_correct=is_correct)
        session.total_count += 1
        session.correct_count += int(is_correct)
        await self._uow.commit()
        return AnswerResult(
            is_correct=is_correct, correct_word=word, user_word=user_word, session=session
        )

    async def finish(self, user: User, session_id: uuid.UUID) -> PracticeSession:
        session = await self._sessions.owned(user.id, session_id)
        if session is None:
            raise NotFoundError("practice session")
        session.finished_at = session.finished_at or utcnow()
        await self._uow.commit()
        return session

    async def _ensure_core_words(self, user: User) -> None:
        total, _, _ = await self._user_words.stats(user.id, utcnow())
        if total >= CORE_WORDS_FOR_BEGINNERS:
            return
        for word in await self._words.core_words():
            await self._user_words.ensure(user.id, word.id, None)

    @staticmethod
    def _choices(word: Word, pool: Sequence[Word]) -> tuple[Word, ...]:
        same_category = [
            item for item in pool if item.id != word.id and item.category == word.category
        ]
        others = [item for item in pool if item.id != word.id and item.category != word.category]
        _random.shuffle(same_category)
        _random.shuffle(others)
        distractors = (same_category + others)[: CHOICES_PER_EXERCISE - 1]
        choices = [word, *distractors]
        _random.shuffle(choices)
        return tuple(choices)

    @staticmethod
    def _schedule(user_word: UserWord, *, is_correct: bool) -> None:
        now = utcnow()
        if is_correct:
            user_word.correct_count += 1
            user_word.box = min(user_word.box + 1, MASTERED_BOX)
        else:
            user_word.wrong_count += 1
            user_word.box = 0
        user_word.mastered = user_word.box >= MASTERED_BOX
        user_word.next_review_at = now + REVIEW_INTERVALS[user_word.box]
