import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from app.models import Writing, WritingOutput, WritingStep
from app.repositories.base import Repository


class WritingRepository(Repository[Writing]):
    model = Writing

    async def owned(
        self, user_id: uuid.UUID, writing_id: uuid.UUID, *, detailed: bool = False
    ) -> Writing | None:
        statement = select(Writing).where(Writing.id == writing_id, Writing.user_id == user_id)
        if detailed:
            statement = statement.options(
                selectinload(Writing.steps), selectinload(Writing.outputs)
            )
        return await self.session.scalar(statement.execution_options(populate_existing=True))

    async def detailed(self, writing_id: uuid.UUID) -> Writing | None:
        return await self.session.scalar(
            select(Writing)
            .where(Writing.id == writing_id)
            .options(selectinload(Writing.steps), selectinload(Writing.outputs))
            .execution_options(populate_existing=True)
        )

    async def list_for_user(
        self, user_id: uuid.UUID, *, before: datetime | None, limit: int
    ) -> Sequence[Writing]:
        statement = (
            select(Writing)
            .where(Writing.user_id == user_id)
            .options(selectinload(Writing.outputs))
            .order_by(Writing.created_at.desc())
            .limit(limit)
        )
        if before is not None:
            statement = statement.where(Writing.created_at < before)
        return (await self.session.scalars(statement)).all()

    async def reassign(self, source_user_id: uuid.UUID, target_user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(Writing).where(Writing.user_id == source_user_id).values(user_id=target_user_id)
        )

    async def next_output_version(self, writing_id: uuid.UUID) -> int:
        current = await self.session.scalar(
            select(func.max(WritingOutput.version)).where(WritingOutput.writing_id == writing_id)
        )
        return (current or 0) + 1


class WritingStepRepository(Repository[WritingStep]):
    model = WritingStep

    async def at(self, writing_id: uuid.UUID, position: int) -> WritingStep | None:
        return await self.session.scalar(
            select(WritingStep).where(
                WritingStep.writing_id == writing_id, WritingStep.position == position
            )
        )


class WritingOutputRepository(Repository[WritingOutput]):
    model = WritingOutput
