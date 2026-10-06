import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.languages import Language
from app.db.base import Entity, TextEnum
from app.models.enums import WordCategory


class Word(Entity):
    __tablename__ = "words"

    word_fr: Mapped[str] = mapped_column(unique=True)
    category: Mapped[WordCategory] = mapped_column(TextEnum(WordCategory))
    is_core: Mapped[bool] = mapped_column(default=False)
    example_fr: Mapped[str | None]
    audio_fr_key: Mapped[str | None]


class WordTranslation(Entity):
    __tablename__ = "word_translations"
    __table_args__ = (UniqueConstraint("word_id", "language"),)

    word_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("words.id", ondelete="RESTRICT"))
    language: Mapped[Language] = mapped_column(TextEnum(Language))
    meaning: Mapped[str]
    audio_key: Mapped[str]
    validated: Mapped[bool] = mapped_column(default=False)


class DocumentWord(Entity):
    __tablename__ = "document_words"
    __table_args__ = (UniqueConstraint("document_id", "word_id"),)

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    word_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("words.id", ondelete="RESTRICT"))
    sentence_fr: Mapped[str]


class UserWord(Entity):
    __tablename__ = "user_words"
    __table_args__ = (
        UniqueConstraint("user_id", "word_id"),
        Index("ix_user_words_user_next_review", "user_id", "next_review_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    word_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("words.id", ondelete="RESTRICT"))
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    correct_count: Mapped[int] = mapped_column(default=0)
    wrong_count: Mapped[int] = mapped_column(default=0)
    box: Mapped[int] = mapped_column(default=0)
    next_review_at: Mapped[datetime] = mapped_column(server_default=func.now())
    mastered: Mapped[bool] = mapped_column(default=False)


class PracticeSession(Entity):
    __tablename__ = "practice_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    language: Mapped[Language] = mapped_column(TextEnum(Language))
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[datetime | None]
    correct_count: Mapped[int] = mapped_column(default=0)
    total_count: Mapped[int] = mapped_column(default=0)


class PracticeAnswer(Entity):
    __tablename__ = "practice_answers"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("practice_sessions.id", ondelete="CASCADE")
    )
    word_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("words.id", ondelete="RESTRICT"))
    chosen_word_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("words.id", ondelete="RESTRICT"))
    is_correct: Mapped[bool]
