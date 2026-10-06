import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, LearningServiceDep, PresenterDep
from app.schemas.learning import (
    LearningOverviewOut,
    PracticeAnswerIn,
    PracticeAnswerOut,
    PracticeRoundOut,
    PracticeSessionOut,
    WordOut,
)
from app.schemas.users import UsageOut

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/overview", response_model=LearningOverviewOut)
async def overview(user: CurrentUser, service: LearningServiceDep) -> LearningOverviewOut:
    result = await service.overview(user)
    return LearningOverviewOut(
        total_words=result.total_words,
        mastered_words=result.mastered_words,
        due_words=result.due_words,
        usage=UsageOut.model_validate(result.usage),
    )


@router.get("/words", response_model=list[WordOut])
async def my_words(
    user: CurrentUser,
    service: LearningServiceDep,
    presenter: PresenterDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[WordOut]:
    rows = await service.my_words(user, limit=limit, offset=offset)
    return [presenter.word(user_word, word, translation) for user_word, word, translation in rows]


@router.post("/sessions", response_model=PracticeRoundOut, status_code=status.HTTP_201_CREATED)
async def start_session(
    user: CurrentUser, service: LearningServiceDep, presenter: PresenterDep
) -> PracticeRoundOut:
    return presenter.practice_round(await service.start(user))


@router.post("/sessions/{session_id}/answers", response_model=PracticeAnswerOut)
async def answer(
    session_id: uuid.UUID,
    body: PracticeAnswerIn,
    user: CurrentUser,
    service: LearningServiceDep,
) -> PracticeAnswerOut:
    result = await service.answer(user, session_id, body.word_id, body.chosen_word_id)
    return PracticeAnswerOut(
        is_correct=result.is_correct,
        correct_word_id=result.correct_word.id,
        correct_word_fr=result.correct_word.word_fr,
        box=result.user_word.box,
        mastered=result.user_word.mastered,
        correct_count=result.session.correct_count,
        total_count=result.session.total_count,
    )


@router.post("/sessions/{session_id}/finish", response_model=PracticeSessionOut)
async def finish(
    session_id: uuid.UUID, user: CurrentUser, service: LearningServiceDep
) -> PracticeSessionOut:
    return PracticeSessionOut.model_validate(await service.finish(user, session_id))
