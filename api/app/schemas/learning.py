import uuid
from datetime import datetime

from app.models.enums import WordCategory
from app.schemas.common import Schema
from app.schemas.users import UsageOut


class LearningOverviewOut(Schema):
    total_words: int
    mastered_words: int
    due_words: int
    usage: UsageOut


class ChoiceOut(Schema):
    word_id: uuid.UUID
    word_fr: str


class ExerciseOut(Schema):
    word_id: uuid.UUID
    word_fr: str
    example_fr: str | None
    meaning: str
    meaning_audio_url: str
    choices: list[ChoiceOut]


class PracticeRoundOut(Schema):
    session_id: uuid.UUID
    exercises: list[ExerciseOut]


class PracticeAnswerIn(Schema):
    word_id: uuid.UUID
    chosen_word_id: uuid.UUID


class PracticeAnswerOut(Schema):
    is_correct: bool
    correct_word_id: uuid.UUID
    correct_word_fr: str
    box: int
    mastered: bool
    correct_count: int
    total_count: int


class PracticeSessionOut(Schema):
    id: uuid.UUID
    correct_count: int
    total_count: int
    started_at: datetime
    finished_at: datetime | None


class WordOut(Schema):
    word_id: uuid.UUID
    word_fr: str
    category: WordCategory
    example_fr: str | None
    meaning: str | None
    meaning_audio_url: str | None
    box: int
    mastered: bool
    next_review_at: datetime
