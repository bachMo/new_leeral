import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.metering import metered
from app.core.clock import utcnow
from app.core.errors import AppError
from app.models import AiJob
from app.models.enums import AiJobStatus, AiJobType

logger = logging.getLogger("leeral.ai_jobs")


@dataclass(slots=True)
class AiJobRefs:
    user_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    writing_id: uuid.UUID | None = None


@dataclass(slots=True)
class AiJobHandle:
    id: uuid.UUID
    output: dict[str, Any] = field(default_factory=dict)


class AiJobTracker:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], provider: str) -> None:
        self._session_factory = session_factory
        self._provider = provider

    @asynccontextmanager
    async def track(
        self, job_type: AiJobType, refs: AiJobRefs, **job_input: Any
    ) -> AsyncIterator[AiJobHandle]:
        job_id = uuid.uuid4()
        async with self._session_factory() as session:
            session.add(
                AiJob(
                    id=job_id,
                    job_type=job_type,
                    provider=self._provider,
                    status=AiJobStatus.RUNNING,
                    input={key: str(value) for key, value in job_input.items()},
                    started_at=utcnow(),
                    user_id=refs.user_id,
                    document_id=refs.document_id,
                    conversation_id=refs.conversation_id,
                    message_id=refs.message_id,
                    writing_id=refs.writing_id,
                )
            )
            await session.commit()

        handle = AiJobHandle(id=job_id)
        started = time.perf_counter()
        with metered() as meter:
            try:
                yield handle
            except BaseException as exc:
                error = exc.code.value if isinstance(exc, AppError) else type(exc).__name__
                await self._finish(
                    job_id, AiJobStatus.FAILED, started, meter.cost_usd, meter.calls, error=error
                )
                raise
            await self._finish(
                job_id,
                AiJobStatus.SUCCEEDED,
                started,
                meter.cost_usd,
                meter.calls,
                output=handle.output,
            )

    async def _finish(
        self,
        job_id: uuid.UUID,
        status: AiJobStatus,
        started: float,
        cost: Any,
        calls: dict[str, int],
        *,
        output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            await session.execute(
                update(AiJob)
                .where(AiJob.id == job_id)
                .values(
                    status=status,
                    output={**(output or {}), "calls": calls},
                    error=error,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    cost_usd=cost or None,
                    finished_at=utcnow(),
                )
            )
            await session.commit()
        logger.info(
            "ai_job_finished",
            extra={"job_id": str(job_id), "status": status.value, "error": error},
        )
